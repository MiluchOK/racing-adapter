#!/usr/bin/env python3
"""Debug console view for race control panel status."""

import time

from race_control_panel import RaceControlPanel

panel = RaceControlPanel()

print("Debug Console Controller View")
print("Press Ctrl+C to exit\n")

try:
    while True:
        panel.update()

        race_mode = "On" if panel.isInRaceMode() else "Off"

        print(f"\rRace Mode: {race_mode}", end="", flush=True)

        time.sleep(0.05)

except KeyboardInterrupt:
    print("\n")

panel.close()
