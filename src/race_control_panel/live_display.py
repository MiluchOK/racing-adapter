#!/usr/bin/env python3
"""Live display of button states using the RaceControlPanel API."""

import time

from race_control_panel import RaceControlPanel


def main():
    panel = RaceControlPanel()

    print(f"Controller: {panel.name}")
    print(f"Buttons: {panel.num_buttons}")
    print("Press Ctrl+C to exit\n")

    try:
        while True:
            panel.update()
            states = "".join("●" if b.is_pressed else "○" for b in panel.buttons)
            print(f"\rButtons: {states}", end="", flush=True)
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\n")
    finally:
        panel.close()


if __name__ == "__main__":
    main()
