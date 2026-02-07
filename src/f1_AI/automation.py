"""
F1 AI Automation Loop

Launches Chiaki, captures screenshots, analyzes with AI, and sends controller inputs.
Runs automatically every 10 seconds until F1 telemetry data is detected on port 20777.

Usage:
    uv run python -m src.f1_AI.automation
"""

import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Add src to path for f1_telemetry import
sys.path.insert(0, str(Path(__file__).parent.parent))

from f1_telemetry import F1TelemetryClient

from .analyzer import F1ScreenAnalyzer
from .ps5_actions import PS5ActionType
from .screenshot import capture_chiaki_screenshot, find_chiaki_window, wait_for_chiaki_window

# Chiaki configuration
CHIAKI_APP = "/Users/alexeymilyukov/Development/chiaki/build/gui/chiaki.app"
CHIAKI_BIN = f"{CHIAKI_APP}/Contents/MacOS/chiaki"
PS5_IP = "192.168.68.53"
PS5_NICKNAME = "PS5-021"

# Only import keyboard on macOS
if sys.platform == "darwin":
    from .keyboard import send_ps5_button, get_key_for_button, CHIAKI_KEY_MAP


def log(msg: str, level: str = "INFO"):
    """Print timestamped log message."""
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{ts}] [{level}] {msg}")


# Telemetry detection
TELEMETRY_PORT = 20777


def check_telemetry_data(timeout: float = 0.5) -> tuple[bool, str | None, str | None]:
    """
    Check if F1 telemetry data is arriving on port 20777.

    Args:
        timeout: How long to wait for data (seconds)

    Returns:
        Tuple of (data_received, track_name, car/team_name)
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Allow multiple processes to bind to same port
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        sock.settimeout(timeout)
        sock.bind(("", TELEMETRY_PORT))

        try:
            data, _ = sock.recvfrom(2048)
            sock.close()
            return (len(data) > 0, None, None)
        except socket.timeout:
            sock.close()
            return (False, None, None)
    except OSError as e:
        # Port might be in use - try connecting to see if data flows
        log(f"Could not bind to port {TELEMETRY_PORT}: {e}", "DEBUG")
        return (False, None, None)


# Global telemetry client for track/car info
_telemetry_client: F1TelemetryClient | None = None


def get_telemetry_info() -> tuple[str | None, str | None]:
    """
    Get current track and car/team from telemetry.

    Returns:
        Tuple of (track_name, tyre_compound as proxy for car info)
    """
    global _telemetry_client

    if _telemetry_client is None:
        _telemetry_client = F1TelemetryClient()
        _telemetry_client.start()
        # Give it a moment to receive data
        time.sleep(0.5)

    data = _telemetry_client.data
    track = data.track if data.track else None
    tyre = data.tyre_compound if data.tyre_compound else None

    return (track, tyre)


def is_chiaki_running() -> bool:
    """Check if Chiaki is already running."""
    result = subprocess.run(["pgrep", "-x", "chiaki"], capture_output=True)
    return result.returncode == 0


def launch_chiaki() -> subprocess.Popen | None:
    """
    Launch Chiaki streaming session.

    Returns:
        Popen process if launched, None if already running.
    """
    if is_chiaki_running():
        log("Chiaki is already running")
        return None

    if not Path(CHIAKI_BIN).exists():
        log(f"Chiaki binary not found at: {CHIAKI_BIN}", "ERROR")
        return None

    log(f"Launching Chiaki stream to {PS5_NICKNAME} at {PS5_IP}...")
    cmd = [CHIAKI_BIN, "stream", PS5_NICKNAME, PS5_IP]
    log(f"Command: {' '.join(cmd)}")

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    log(f"Chiaki launched with PID: {process.pid}")
    return process


# Human-readable button names
BUTTON_DISPLAY = {
    "cross": "X (Cross)",
    "circle": "O (Circle)",
    "square": "Square",
    "triangle": "Triangle",
    "dpad_up": "D-Pad Up",
    "dpad_down": "D-Pad Down",
    "dpad_left": "D-Pad Left",
    "dpad_right": "D-Pad Right",
    "l1": "L1",
    "r1": "R1",
    "l2": "L2",
    "r2": "R2",
    "options": "Options",
    "touchpad": "Touchpad",
}


def print_separator(char: str = "=", width: int = 60):
    """Print a separator line."""
    print(char * width)




def run_automation_loop(
    interval: float = 0.0001,
    save_screenshots: bool = False,
    screenshot_dir: str = "screenshots",
):
    """
    Main automation loop.

    Args:
        interval: Seconds between each cycle
        save_screenshots: Whether to save screenshots to disk
        screenshot_dir: Directory to save screenshots
    """
    if sys.platform != "darwin":
        log("This automation only works on macOS", "ERROR")
        sys.exit(1)

    print_separator()
    print("  F1 AI AUTOMATION")
    print_separator()
    print(f"  Interval: {interval}s between actions")
    print(f"  Save screenshots: {save_screenshots}")
    print(f"  Goal: Telemetry on port {TELEMETRY_PORT}")
    print(f"  Mode: AUTOMATIC")
    print_separator()
    print()

    # Launch Chiaki if not running
    log("Checking for Chiaki...")
    chiaki_process = None
    window_id, name, width, height = find_chiaki_window()

    if window_id is None:
        log("Chiaki window not found, launching...")
        chiaki_process = launch_chiaki()

        if chiaki_process is None and not is_chiaki_running():
            log("Failed to launch Chiaki", "ERROR")
            sys.exit(1)

        # Wait for streaming window to appear
        log("Waiting for Chiaki streaming window (up to 120s)...")
        window_id, status = wait_for_chiaki_window(timeout=120)

        if window_id is None:
            log(f"Timeout: {status}", "ERROR")
            sys.exit(1)
        log(status)

        # Give stream a moment to render
        log("Waiting 5s for stream to render...")
        time.sleep(5)

        # Re-fetch window info
        window_id, name, width, height = find_chiaki_window()

    log(f"Chiaki ready: '{name}' ({width}x{height})")

    # Initialize analyzer
    log("Initializing AI analyzer...")
    try:
        analyzer = F1ScreenAnalyzer()
        log("Analyzer ready (using OpenAI)")
    except ValueError as e:
        log(f"Failed to initialize analyzer: {e}", "ERROR")
        sys.exit(1)

    # Create screenshot directory if saving
    if save_screenshots:
        screenshot_path = Path(screenshot_dir)
        screenshot_path.mkdir(parents=True, exist_ok=True)
        log(f"Screenshots will be saved to: {screenshot_path.absolute()}")

    print()
    log("Starting automation loop. Press Ctrl+C to stop.")
    print_separator("-")
    print()

    cycle = 0
    try:
        while True:
            cycle += 1
            print_separator()
            log(f"CYCLE {cycle}", "INFO")
            print_separator()

            # Check for F1 telemetry data - if present, goal achieved!
            log("Checking for F1 telemetry data on port 20777...")
            has_telemetry, _, _ = check_telemetry_data(timeout=1.0)

            # Print track and car info every cycle when telemetry is available
            if has_telemetry:
                track, tyres = get_telemetry_info()

                # Get full telemetry data for validation
                data = _telemetry_client.data if _telemetry_client else None

                print()
                print_separator("-")
                print("  TELEMETRY DATA RECEIVED")
                print_separator("-")
                print(f"  Track:    {track or 'Unknown'}")
                print(f"  Tyres:    {tyres or 'Unknown'}")
                if data:
                    print(f"  Speed:    {data.speed} km/h")
                    print(f"  Gear:     {data.gear}")
                    print(f"  RPM:      {data.rpm}")
                    print(f"  Throttle: {data.throttle}%")
                    print(f"  Brake:    {data.brake}%")
                    print(f"  Lap:      {data.current_lap}")
                    print(f"  Position: P{data.position}")
                    print(f"  Lap Time: {data.lap_time}")
                print_separator("-")
                print()

                # Validate we're actually on track (speed > 0 or lap distance > 0)
                is_on_track = False
                if data and (data.speed > 0 or (data.lap and data.lap.lap_distance > 0)):
                    is_on_track = True

                if is_on_track:
                    print_separator("=")
                    print("  GOAL ACHIEVED!")
                    print("  F1 telemetry data detected - on track!")
                    print_separator("=")
                    print()
                    log("Telemetry data flowing - flying lap started!")

                    # Stop telemetry client
                    if _telemetry_client:
                        _telemetry_client.stop()
                    return
                else:
                    log("Telemetry received but not on track yet (speed=0), continuing...")

            log("No telemetry yet, continuing navigation...")

            # Step 1: Capture screenshot
            log("Capturing screenshot from Chiaki...")
            if save_screenshots:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_path = Path(screenshot_dir) / f"capture_{ts}.png"
            else:
                save_path = Path("/tmp/f1_ai_capture.png")

            frame, status = capture_chiaki_screenshot(save_path)
            if frame is None:
                log(f"Screenshot failed: {status}", "ERROR")
                log(f"Waiting {interval}s before retry...")
                time.sleep(interval)
                continue

            log(f"Screenshot: {status}")

            # Step 2: Analyze with AI
            log("Sending to OpenAI for analysis...")
            try:
                action = analyzer.analyze(str(save_path))
            except Exception as e:
                log(f"Analysis failed: {e}", "ERROR")
                log(f"Waiting {interval}s before retry...")
                time.sleep(interval)
                continue

            # Step 4: Display the result
            print()
            print_separator("-")
            print("  AI ANALYSIS RESULT")
            print_separator("-")
            print(f"  {action.description}")
            print()

            if action.action_type == PS5ActionType.NONE:
                # Unknown state (black screen, loading, etc.) - wait and retry
                print("  No action needed, waiting...")
                print_separator("-")
                print()
                log(f"Waiting {interval}s before retry...")
                time.sleep(interval)
                continue

            if action.action_type == PS5ActionType.WAIT:
                print(f"  Recommended action: WAIT {action.duration_ms}ms")
                print_separator("-")
                print()
                log(f"Waiting {action.duration_ms}ms as recommended...")
                time.sleep(action.duration_ms / 1000.0)
                continue

            if action.button:
                button_name = BUTTON_DISPLAY.get(action.button.value, action.button.value)
                keyboard_key = get_key_for_button(action.button.value)
                print(f"  Action: Press [{button_name}] (key: {keyboard_key})")
                if action.action_type == PS5ActionType.BUTTON_HOLD:
                    print(f"  Hold duration: {action.duration_ms}ms")
                print_separator("-")

                # Execute the action
                log(f"Sending button press: {action.button.value}")
                try:
                    send_ps5_button(action.button.value, action.duration_ms)
                    log("Button press sent successfully")
                except Exception as e:
                    log(f"Failed to send button: {e}", "ERROR")

            print()
            log(f"Cycle complete. Waiting {interval}s...")
            time.sleep(interval)

    except KeyboardInterrupt:
        print()
        print_separator()
        log("Automation stopped by user")
        print_separator()


def main():
    """Entry point for automation module."""
    import argparse

    parser = argparse.ArgumentParser(
        description="F1 AI Automation - Capture, analyze, and control"
    )
    parser.add_argument(
        "--interval", "-i",
        type=float,
        default=0.0001,
        help="Seconds between each cycle (default: 0.0001)"
    )
    parser.add_argument(
        "--save-screenshots", "-s",
        action="store_true",
        help="Save all screenshots to disk"
    )
    parser.add_argument(
        "--screenshot-dir",
        default="screenshots",
        help="Directory to save screenshots (default: screenshots)"
    )

    args = parser.parse_args()

    run_automation_loop(
        interval=args.interval,
        save_screenshots=args.save_screenshots,
        screenshot_dir=args.screenshot_dir,
    )


if __name__ == "__main__":
    main()
