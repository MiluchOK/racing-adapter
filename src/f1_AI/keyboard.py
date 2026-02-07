"""Keyboard input simulation for sending controls to Chiaki on macOS."""

import subprocess
import sys
import time

if sys.platform != "darwin":
    raise ImportError("Keyboard simulation only supported on macOS")

import Quartz
from Quartz import (
    CGEventCreateKeyboardEvent,
    CGEventPost,
    kCGHIDEventTap,
)


def focus_chiaki_window():
    """Bring Chiaki window to foreground."""
    script = '''
    tell application "System Events"
        set chiakiProcs to every process whose name contains "chiaki"
        if (count of chiakiProcs) > 0 then
            set frontmost of item 1 of chiakiProcs to true
            return true
        end if
    end tell
    return false
    '''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=2
        )
        return "true" in result.stdout.lower()
    except Exception:
        return False

# macOS virtual key codes
# Reference: https://stackoverflow.com/questions/3202629/where-can-i-find-a-list-of-mac-virtual-key-codes
KEY_CODES = {
    # Arrow keys
    "up": 126,
    "down": 125,
    "left": 123,
    "right": 124,
    # Common keys
    "return": 36,
    "escape": 53,
    "space": 49,
    "tab": 48,
    "backspace": 51,
    "minus": 27,
    "equals": 24,
    # Letter keys
    "a": 0, "s": 1, "d": 2, "f": 3,
    "h": 4, "g": 5, "z": 6, "x": 7,
    "c": 8, "v": 9, "b": 11, "q": 12,
    "w": 13, "e": 14, "r": 15, "y": 16,
    "t": 17, "1": 18, "2": 19, "3": 20,
    "4": 21, "6": 22, "5": 23, "9": 25,
    "7": 26, "8": 28, "0": 29, "o": 31,
    "u": 32, "i": 34, "p": 35, "l": 37,
    "j": 38, "k": 40, "n": 45, "m": 46,
    # Function keys
    "f1": 122, "f2": 120, "f3": 99, "f4": 118,
    "f5": 96, "f6": 97, "f7": 98, "f8": 100,
    # Modifier keys
    "shift": 56, "ctrl": 59, "alt": 58, "cmd": 55,
}

# Chiaki (PS5) → Mac Keyboard Mapping
CHIAKI_KEY_MAP = {
    # D-pad / Navigation
    "dpad_up": "up",
    "dpad_down": "down",
    "dpad_left": "left",       # Arrow left
    "dpad_right": "right",     # Arrow right
    # Face buttons
    "cross": "return",         # X button - confirm (Enter key)
    "circle": "backspace",     # O button - back/cancel
    "triangle": "t",           # Triangle
    "square": "v",             # Square
    # Shoulder & Trigger buttons
    "l1": "2",
    "l2": "4",
    "r1": "3",
    "r2": "1",
    # System buttons
    "options": "return",       # Options → Enter
    "touchpad": "space",       # Touchpad → Space
    "ps": "escape",            # PS Button → Esc
}


def press_key(key_code: int, duration: float = 0.1):
    """
    Simulate a key press and release.

    Args:
        key_code: macOS virtual key code
        duration: How long to hold the key (seconds)
    """
    # Key down
    event = CGEventCreateKeyboardEvent(None, key_code, True)
    CGEventPost(kCGHIDEventTap, event)

    time.sleep(duration)

    # Key up
    event = CGEventCreateKeyboardEvent(None, key_code, False)
    CGEventPost(kCGHIDEventTap, event)


def press_key_by_name(key_name: str, duration: float = 0.1):
    """
    Press a key by its name.

    Args:
        key_name: Name of the key (e.g., "return", "up", "a")
        duration: How long to hold the key (seconds)
    """
    key_code = KEY_CODES.get(key_name.lower())
    if key_code is None:
        raise ValueError(f"Unknown key: {key_name}")
    press_key(key_code, duration)


def send_ps5_button(button: str, duration_ms: int = 100):
    """
    Send a PS5 button press to Chiaki.

    Args:
        button: PS5 button name (e.g., "cross", "dpad_up")
        duration_ms: How long to hold the button in milliseconds
    """
    key_name = CHIAKI_KEY_MAP.get(button.lower())
    if key_name is None:
        raise ValueError(f"Unknown PS5 button: {button}. Valid buttons: {list(CHIAKI_KEY_MAP.keys())}")

    key_code = KEY_CODES.get(key_name)
    if key_code is None:
        raise ValueError(f"Unknown key mapping: {key_name}")

    # Focus Chiaki window before sending key
    focus_chiaki_window()
    time.sleep(0.1)  # Brief pause to ensure focus

    press_key(key_code, duration_ms / 1000.0)


def get_key_for_button(button: str) -> str:
    """Get the keyboard key name for a PS5 button."""
    return CHIAKI_KEY_MAP.get(button.lower(), "unknown")


# Quick test
if __name__ == "__main__":
    print("Keyboard simulation test")
    print(f"Key codes loaded: {len(KEY_CODES)}")
    print(f"PS5 button mappings: {len(CHIAKI_KEY_MAP)}")
    print("\nPS5 -> Keyboard mappings:")
    for ps5_btn, key in CHIAKI_KEY_MAP.items():
        print(f"  {ps5_btn:12} -> {key}")
