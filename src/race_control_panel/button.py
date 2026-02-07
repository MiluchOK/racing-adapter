"""Button base class for race control panel."""


class Button:
    """Represents a single button on the control panel."""

    def __init__(self, index: int, name: str):
        self.index = index
        self.name = name
        self._state = False
        self._prev_state = False

    @property
    def is_pressed(self) -> bool:
        """Returns True if the button is currently pressed."""
        return self._state

    @property
    def is_released(self) -> bool:
        """Returns True if the button is currently released."""
        return not self._state

    @property
    def just_pressed(self) -> bool:
        """Returns True if the button was just pressed this frame."""
        return self._state and not self._prev_state

    @property
    def just_released(self) -> bool:
        """Returns True if the button was just released this frame."""
        return not self._state and self._prev_state

    def _update(self, state: bool):
        """Update the button state. Called internally by RaceControlPanel."""
        self._prev_state = self._state
        self._state = state
