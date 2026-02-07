#!/usr/bin/env python3
"""
Controller State Reader

Simple API to read button/axis states on demand.
"""

import pygame


class Controller:
    def __init__(self, index=0):
        pygame.init()
        pygame.joystick.init()

        if pygame.joystick.get_count() == 0:
            raise RuntimeError("No controller found")

        self.js = pygame.joystick.Joystick(index)
        self.js.init()
        self.name = self.js.get_name()

    def update(self):
        """Call this before reading state to get fresh data."""
        pygame.event.pump()

    def get_button(self, num: int) -> bool:
        """Get state of a single button. True = pressed."""
        return self.js.get_button(num)

    def get_all_buttons(self) -> list[bool]:
        """Get state of all buttons as a list."""
        return [self.js.get_button(i) for i in range(self.js.get_numbuttons())]

    def get_axis(self, num: int) -> float:
        """Get axis value (-1.0 to 1.0)."""
        return self.js.get_axis(num)

    def get_all_axes(self) -> list[float]:
        """Get all axis values."""
        return [self.js.get_axis(i) for i in range(self.js.get_numaxes())]

    def get_state(self) -> dict:
        """Get complete controller state as a dict."""
        self.update()
        return {
            "buttons": self.get_all_buttons(),
            "axes": self.get_all_axes(),
        }

    def close(self):
        pygame.quit()


# Quick demo
if __name__ == "__main__":
    ctrl = Controller()
    print(f"Controller: {ctrl.name}")
    print(f"Buttons: {ctrl.js.get_numbuttons()}")
    print(f"Axes: {ctrl.js.get_numaxes()}")

    print("\nPolling state every second. Press Ctrl+C to stop.\n")

    import time
    try:
        while True:
            state = ctrl.get_state()

            # Show pressed buttons
            pressed = [i for i, v in enumerate(state["buttons"]) if v]
            if pressed:
                print(f"Pressed: {pressed}")
            else:
                print("No buttons pressed")

            time.sleep(1)
    except KeyboardInterrupt:
        print("\nDone")
        ctrl.close()
