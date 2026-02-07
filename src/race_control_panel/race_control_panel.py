"""RaceControlPanel wrapper class with semantic methods."""

import subprocess
import time
from pathlib import Path

import pygame.mixer

from .panel import Panel

IGNITION_HOLD_DURATION = 1.0  # seconds
ENGINE_START_SOUND = Path("/Users/alexeymilyukov/Downloads/car-engine-start-44357.mp3")
RADIO_SOUND = Path("/Users/alexeymilyukov/Development/racing-adapter/assets/f1_radio_sound-293747.mp3")
PS5_F1_AUTOMATION_SCRIPT = Path("/Users/alexeymilyukov/Development/chiaki/run_f1_automation.sh")


class Buttons:
    RADIO = 3
    IGNITION = 10
    LAUNCH_CONTROL = 11


class RaceControlPanel:
    """High-level wrapper for the Panel with semantic button methods."""

    def __init__(self):
        self._panel = Panel()
        self._race_mode = False
        self._launch_control_on = False  # Assumes toggle starts in "down" position
        self._ignition_held_since: float | None = None

        pygame.mixer.init()
        self._engine_sound = pygame.mixer.Sound(ENGINE_START_SOUND)
        self._radio_sound = pygame.mixer.Sound(RADIO_SOUND)

    def update(self):
        """Poll device and update all button states."""
        self._panel.update()
        now = time.time()

        launch_btn = self._panel.buttons[Buttons.LAUNCH_CONTROL]
        ignition_btn = self._panel.buttons[Buttons.IGNITION]
        radio_btn = self._panel.buttons[Buttons.RADIO]

        # Play radio sound when pressed
        if radio_btn.just_pressed:
            self._radio_sound.play()

        # Toggle launch control state on each flip
        if launch_btn.just_pressed:
            self._launch_control_on = not self._launch_control_on
            if not self._launch_control_on:
                self._race_mode = False
                self._ignition_held_since = None

        # Only track ignition if launch control is on
        if self._launch_control_on and ignition_btn.is_pressed:
            if self._ignition_held_since is None:
                self._ignition_held_since = now
                self._engine_sound.play(maxtime=10000)

            # Activate race mode after holding ignition
            if (now - self._ignition_held_since) >= IGNITION_HOLD_DURATION:
                if not self._race_mode:
                    self._race_mode = True
                    subprocess.Popen([str(PS5_F1_AUTOMATION_SCRIPT)])
        else:
            self._ignition_held_since = None

    def isInRaceMode(self) -> bool:
        """Returns True if race mode is active."""
        return self._race_mode

    def close(self):
        """Clean up pygame resources."""
        self._panel.close()
