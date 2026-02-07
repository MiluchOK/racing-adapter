"""CLI entry point for F1 AI analyzer."""

import sys
import tempfile
from pathlib import Path

from .analyzer import F1ScreenAnalyzer
from .ps5_actions import PS5ActionType

# Human-readable button names
BUTTON_NAMES = {
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


def print_usage():
    print("Usage: python -m src.f1_AI [OPTIONS] [screenshot_path]")
    print("\nAnalyzes an F1 game screenshot and outputs the next PS5 action.")
    print("\nOptions:")
    print("  --live         Capture directly from Chiaki window (macOS only)")
    print("  --raw          Output only the button name (machine-readable)")
    print("  --save <path>  Save captured screenshot to path (with --live)")
    print("\nExamples:")
    print("  python -m src.f1_AI screenshot.png       # Analyze a file")
    print("  python -m src.f1_AI --live               # Capture from Chiaki")
    print("  python -m src.f1_AI --live --save out.png")
    print("\nRequires OPENAI_API_KEY in .env file or environment.")


def capture_from_chiaki(save_path: str | None = None) -> str:
    """Capture screenshot from Chiaki window and return temp file path."""
    from .screenshot import capture_chiaki_screenshot

    if save_path:
        output_path = Path(save_path)
    else:
        output_path = Path(tempfile.gettempdir()) / "f1_ai_capture.png"

    frame, status = capture_chiaki_screenshot(output_path)

    if frame is None:
        print(f"Error: {status}", file=sys.stderr)
        sys.exit(1)

    print(f"Captured: {status}")
    return str(output_path)


def print_action(action, raw_output: bool):
    """Print the action in human or machine readable format."""
    if raw_output:
        if action.button:
            print(action.button.value)
        else:
            print(action.action_type.value)
    else:
        print(f"\n{action.description}\n")

        if action.action_type == PS5ActionType.NONE:
            print("Action: None needed (goal achieved or waiting)")
        elif action.action_type == PS5ActionType.WAIT:
            print(f"Action: Wait {action.duration_ms}ms")
        elif action.button:
            button_name = BUTTON_NAMES.get(action.button.value, action.button.value)
            if action.action_type == PS5ActionType.BUTTON_HOLD:
                print(f"Action: Hold [{button_name}] for {action.duration_ms}ms")
            else:
                print(f"Action: Press [{button_name}]")


def main():
    args = sys.argv[1:]

    if not args or "-h" in args or "--help" in args:
        print_usage()
        sys.exit(0 if "-h" in args or "--help" in args else 1)

    live_mode = "--live" in args
    raw_output = "--raw" in args

    # Parse --save argument
    save_path = None
    if "--save" in args:
        save_idx = args.index("--save")
        if save_idx + 1 < len(args):
            save_path = args[save_idx + 1]
        else:
            print("Error: --save requires a path argument", file=sys.stderr)
            sys.exit(1)

    # Get screenshot path
    if live_mode:
        if sys.platform != "darwin":
            print("Error: --live mode only works on macOS", file=sys.stderr)
            sys.exit(1)
        screenshot_path = capture_from_chiaki(save_path)
    else:
        # Find the first non-flag argument as screenshot path
        screenshot_path = None
        for arg in args:
            if not arg.startswith("-") and arg != save_path:
                screenshot_path = arg
                break

        if not screenshot_path:
            print("Error: No screenshot path provided", file=sys.stderr)
            print_usage()
            sys.exit(1)

    try:
        analyzer = F1ScreenAnalyzer()
        action = analyzer.analyze(screenshot_path)
        print_action(action, raw_output)

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
