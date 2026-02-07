#!/usr/bin/env python3
"""Live display of race control panel status."""

import time

from race_control_panel import RaceControlPanel

panel = RaceControlPanel()

print("Race Control Panel")
print("Press Ctrl+C to exit\n")

try:
    while True:
        panel.update()
        status = "ON" if panel.isInRaceMode() else "OFF"
        print(f"\rRace Mode: {status}", end="", flush=True)
        time.sleep(0.05)

except KeyboardInterrupt:
    print("\n")

panel.close()
