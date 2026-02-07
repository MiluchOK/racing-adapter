#!/usr/bin/env python3
"""Read data from Fanatec wheel using calibration profile."""

import hid
import json
import os
import sys
from pathlib import Path

FANATEC_VENDOR_ID = 0x0EB7
FANATEC_PRODUCT_ID = 0x0E07
PROFILE_PATH = Path(__file__).parent.parent / "calibration_profile.json"


def load_profile() -> dict | None:
    """Load calibration profile."""
    if not PROFILE_PATH.exists():
        return None
    with open(PROFILE_PATH) as f:
        return json.load(f)


def read_axis(data: list[int], config: dict) -> tuple[int, float]:
    """Read an axis value and return (raw, normalized 0-100%)."""
    byte_idx = config.get("byte", -1)
    if byte_idx < 0 or byte_idx >= len(data):
        return (0, 0.0)

    if config.get("is_16bit", False):
        raw = data[byte_idx] | (data[byte_idx + 1] << 8)
    else:
        raw = data[byte_idx]

    min_val = config.get("min", 0)
    max_val = config.get("max", 255 if not config.get("is_16bit") else 65535)

    if max_val == min_val:
        normalized = 0.0
    else:
        normalized = ((raw - min_val) / (max_val - min_val)) * 100
        normalized = max(0.0, min(100.0, normalized))

    return (raw, normalized)


def read_buttons(data: list[int], buttons: list[dict]) -> list[str]:
    """Read button states."""
    pressed = []
    for btn in buttons:
        byte_idx = btn.get("byte", -1)
        bit = btn.get("bit", 0)
        if byte_idx >= 0 and byte_idx < len(data):
            if data[byte_idx] & (1 << bit):
                pressed.append(btn["name"])
    return pressed


def make_bar(percent: float, width: int = 20) -> str:
    """Create a visual bar representation."""
    filled = int((percent / 100) * width)
    return "█" * filled + "░" * (width - filled)


def make_steering_bar(percent: float, width: int = 40) -> str:
    """Create a centered steering bar."""
    center = width // 2
    pos = int((percent / 100) * width)

    bar = list("─" * width)
    bar[center] = "│"

    if pos < center:
        for i in range(pos, center):
            bar[i] = "◀"
    elif pos > center:
        for i in range(center + 1, min(pos + 1, width)):
            bar[i] = "▶"
    else:
        bar[center] = "◆"

    return "".join(bar)


def main():
    """Read and display data from Fanatec wheel."""
    profile = load_profile()

    if not profile:
        print("No calibration profile found!")
        print(f"Expected at: {PROFILE_PATH}")
        print()
        print("Run calibration first:")
        print("  uv run python src/calibrate.py")
        sys.exit(1)

    print(f"Loaded profile for: {profile['device'].get('name', 'Unknown')}")
    print(f"Opening Fanatec wheel...")

    try:
        device = hid.device()
        device.open(FANATEC_VENDOR_ID, FANATEC_PRODUCT_ID)
        device.set_nonblocking(False)

        manufacturer = device.get_manufacturer_string()
        product = device.get_product_string()
        print(f"Connected to: {manufacturer} - {product}")
        print("Reading data (press Ctrl+C to stop)...\n")

        has_clutch = profile.get("clutch", {}).get("byte", -1) >= 0

        while True:
            data = device.read(64, timeout_ms=100)
            if data:
                # Read axes using calibration
                steering_raw, steering_pct = read_axis(data, profile.get("steering", {}))
                throttle_raw, throttle_pct = read_axis(data, profile.get("throttle", {}))
                brake_raw, brake_pct = read_axis(data, profile.get("brake", {}))
                clutch_raw, clutch_pct = read_axis(data, profile.get("clutch", {}))

                # Read buttons
                buttons = read_buttons(data, profile.get("buttons", []))

                # Clear and display
                os.system('clear' if os.name == 'posix' else 'cls')

                print("╔════════════════════════════════════════════════════╗")
                print("║          FANATEC WHEEL - LIVE DATA                 ║")
                print("╠════════════════════════════════════════════════════╣")
                print(f"║  STEERING: {steering_raw:5d} ({steering_pct:5.1f}%)                    ║")
                print(f"║  [{make_steering_bar(steering_pct)}] ║")
                print("╠════════════════════════════════════════════════════╣")
                print(f"║  THROTTLE: {throttle_pct:5.1f}%  [{make_bar(throttle_pct)}]       ║")
                print(f"║  BRAKE:    {brake_pct:5.1f}%  [{make_bar(brake_pct)}]       ║")
                if has_clutch:
                    print(f"║  CLUTCH:   {clutch_pct:5.1f}%  [{make_bar(clutch_pct)}]       ║")
                print("╠════════════════════════════════════════════════════╣")
                btn_str = ', '.join(buttons) if buttons else 'None'
                # Truncate if too long
                if len(btn_str) > 40:
                    btn_str = btn_str[:37] + "..."
                print(f"║  BUTTONS: {btn_str:<40} ║")
                print("╠════════════════════════════════════════════════════╣")
                print(f"║  RAW: {' '.join(f'{b:02x}' for b in data[:16])}   ║")
                print(f"║       {' '.join(f'{b:02x}' for b in data[16:32])}   ║")
                print(f"║       {' '.join(f'{b:02x}' for b in data[32:48])}   ║")
                print(f"║       {' '.join(f'{b:02x}' for b in data[48:64])}   ║")
                print("╚════════════════════════════════════════════════════╝")

    except OSError as e:
        print(f"Error opening device: {e}")
        print("Make sure the wheel is connected and you have permissions.")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        if 'device' in locals():
            device.close()


if __name__ == "__main__":
    main()
