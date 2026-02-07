"""Panel class for reading button states from PXN-CB1 device."""

import pygame

from .button import Button


class Panel:
    """Low-level interface for reading button states from the PXN-CB1 control panel."""

    def __init__(self):
        pygame.init()
        pygame.joystick.init()

        self._js = pygame.joystick.Joystick(0)
        self._js.init()

        num_buttons = self._js.get_numbuttons()
        self._buttons: list[Button] = []

        for i in range(num_buttons):
            btn = Button(i, f"button_{i}")
            self._buttons.append(btn)

    @property
    def name(self) -> str:
        """Returns the controller name."""
        return self._js.get_name()

    @property
    def num_buttons(self) -> int:
        """Returns the number of buttons."""
        return len(self._buttons)

    @property
    def buttons(self) -> list[Button]:
        """Returns all buttons."""
        return self._buttons

    def update(self):
        """Poll device and update all button states."""
        pygame.event.pump()
        for btn in self._buttons:
            btn._update(self._js.get_button(btn.index))

    def close(self):
        """Clean up pygame resources."""
        pygame.quit()
