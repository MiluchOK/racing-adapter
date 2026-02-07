#!/usr/bin/env python3
"""
Simple Button Mapper

Maps buttons/switches on your controller to custom actions.
Uses pygame for easy joystick access - no HID parsing needed.

Usage:
  uv run src/button_mapper.py           # Detect buttons
  uv run src/button_mapper.py --run     # Run your configured actions
"""

import pygame
import time

# ============================================================
# CONFIGURE YOUR ACTIONS HERE
# ============================================================
# Map button numbers to actions (functions or shell commands)
# Run with no args first to see which button is which number

BUTTON_ACTIONS = {
    # Example mappings (uncomment and edit):
    # 0: lambda: print("Button 0 pressed!"),
    # 1: lambda: os.system("open -a Calculator"),
    # 2: lambda: keyboard_press("space"),
}

AXIS_ACTIONS = {
    # Example: axis 0 (like a dial) triggers at thresholds
    # 0: {"threshold": 0.5, "action": lambda v: print(f"Axis 0: {v:.2f}")},
}


def detect_mode():
    """Show all inputs as you press them."""
    pygame.init()
    pygame.joystick.init()

    if pygame.joystick.get_count() == 0:
        print("No controllers found!")
        return

    js = pygame.joystick.Joystick(0)
    js.init()

    print("=" * 50)
    print(f"CONTROLLER: {js.get_name()}")
    print("=" * 50)
    print(f"  Buttons: {js.get_numbuttons()}")
    print(f"  Axes:    {js.get_numaxes()}")
    print(f"  Hats:    {js.get_numhats()}")
    print("=" * 50)
    print("\nPress buttons/move controls to see their numbers.")
    print("Press Ctrl+C to exit.\n")

    # Track state to only show changes
    prev_buttons = [False] * js.get_numbuttons()
    prev_axes = [0.0] * js.get_numaxes()
    prev_hats = [(0, 0)] * js.get_numhats()

    try:
        while True:
            pygame.event.pump()

            # Check buttons
            for i in range(js.get_numbuttons()):
                pressed = js.get_button(i)
                if pressed and not prev_buttons[i]:
                    print(f"  BUTTON {i}: pressed")
                elif not pressed and prev_buttons[i]:
                    print(f"  BUTTON {i}: released")
                prev_buttons[i] = pressed

            # Check axes (with deadzone)
            for i in range(js.get_numaxes()):
                value = js.get_axis(i)
                if abs(value - prev_axes[i]) > 0.1:
                    bar = "=" * int((value + 1) * 10)
                    print(f"  AXIS {i}: {value:+.2f} [{bar:<20}]")
                    prev_axes[i] = value

            # Check hats (d-pads)
            for i in range(js.get_numhats()):
                value = js.get_hat(i)
                if value != prev_hats[i]:
                    print(f"  HAT {i}: {value}")
                    prev_hats[i] = value

            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\n\nDone!")

    pygame.quit()


def run_mode():
    """Run configured button actions."""
    if not BUTTON_ACTIONS and not AXIS_ACTIONS:
        print("No actions configured!")
        print("Edit BUTTON_ACTIONS in this file first.")
        print("Run without --run to discover button numbers.")
        return

    pygame.init()
    pygame.joystick.init()

    if pygame.joystick.get_count() == 0:
        print("No controllers found!")
        return

    js = pygame.joystick.Joystick(0)
    js.init()

    print(f"Running actions for: {js.get_name()}")
    print(f"Configured: {len(BUTTON_ACTIONS)} button(s), {len(AXIS_ACTIONS)} axis(es)")
    print("Press Ctrl+C to stop.\n")

    prev_buttons = [False] * js.get_numbuttons()

    try:
        while True:
            pygame.event.pump()

            # Handle button presses
            for i in range(js.get_numbuttons()):
                pressed = js.get_button(i)
                if pressed and not prev_buttons[i]:
                    if i in BUTTON_ACTIONS:
                        print(f"Button {i} → running action")
                        BUTTON_ACTIONS[i]()
                prev_buttons[i] = pressed

            # Handle axes
            for axis_num, config in AXIS_ACTIONS.items():
                if axis_num < js.get_numaxes():
                    value = js.get_axis(axis_num)
                    if abs(value) > config.get("threshold", 0.5):
                        config["action"](value)

            time.sleep(0.02)

    except KeyboardInterrupt:
        print("\nStopped.")

    pygame.quit()


if __name__ == "__main__":
    import sys
    if "--run" in sys.argv:
        run_mode()
    else:
        detect_mode()
