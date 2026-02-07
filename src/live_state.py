#!/usr/bin/env python3
"""Live display of all button/axis states."""

import pygame
import time

pygame.init()
pygame.joystick.init()

js = pygame.joystick.Joystick(0)
js.init()

print(f"Controller: {js.get_name()}")
print(f"Buttons: {js.get_numbuttons()}, Axes: {js.get_numaxes()}")
print("Press Ctrl+C to exit\n")

prev_states = [False] * js.get_numbuttons()

try:
    while True:
        pygame.event.pump()

        # Detect button presses and print info
        for i in range(js.get_numbuttons()):
            pressed = js.get_button(i)
            if pressed and not prev_states[i]:
                print(f"\nButton {i} pressed")
            prev_states[i] = pressed

        # Buttons: ○ = off, ● = on
        buttons = "".join("●" if js.get_button(i) else "○" for i in range(js.get_numbuttons()))

        # Axes: show values
        axes = " ".join(f"{js.get_axis(i):+.1f}" for i in range(js.get_numaxes()))

        print(f"\rButtons: {buttons}  Axes: [{axes}]", end="", flush=True)

        time.sleep(0.05)

except KeyboardInterrupt:
    print("\n")

pygame.quit()
