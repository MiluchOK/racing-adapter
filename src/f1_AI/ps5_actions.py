"""PS5 Controller Actions for F1 game navigation."""

from dataclasses import dataclass
from enum import Enum


class PS5Button(Enum):
    """PS5 DualSense controller buttons."""
    CROSS = "cross"           # X button - Confirm/Select
    CIRCLE = "circle"         # O button - Back/Cancel
    SQUARE = "square"         # Square button
    TRIANGLE = "triangle"     # Triangle button
    L1 = "l1"
    R1 = "r1"
    L2 = "l2"
    R2 = "r2"
    L3 = "l3"                 # Left stick press
    R3 = "r3"                 # Right stick press
    DPAD_UP = "dpad_up"
    DPAD_DOWN = "dpad_down"
    DPAD_LEFT = "dpad_left"
    DPAD_RIGHT = "dpad_right"
    OPTIONS = "options"
    SHARE = "share"
    PS = "ps"
    TOUCHPAD = "touchpad"


class PS5ActionType(Enum):
    """Types of PS5 actions."""
    BUTTON_PRESS = "button_press"
    BUTTON_HOLD = "button_hold"
    WAIT = "wait"
    NONE = "none"


@dataclass
class PS5Action:
    """Represents a PS5 controller action."""
    action_type: PS5ActionType
    button: PS5Button | None = None
    duration_ms: int = 100  # Duration for button hold or wait
    description: str = ""   # Human-readable description of the action
    
    def __str__(self) -> str:
        if self.action_type == PS5ActionType.NONE:
            return f"NO_ACTION: {self.description}"
        elif self.action_type == PS5ActionType.WAIT:
            return f"WAIT {self.duration_ms}ms: {self.description}"
        elif self.action_type == PS5ActionType.BUTTON_HOLD:
            return f"HOLD {self.button.value} for {self.duration_ms}ms: {self.description}"
        else:
            return f"PRESS {self.button.value}: {self.description}"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "action_type": self.action_type.value,
            "button": self.button.value if self.button else None,
            "duration_ms": self.duration_ms,
            "description": self.description,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "PS5Action":
        """Create PS5Action from dictionary."""
        action_type = PS5ActionType(data["action_type"])
        button = PS5Button(data["button"]) if data.get("button") else None
        return cls(
            action_type=action_type,
            button=button,
            duration_ms=data.get("duration_ms", 100),
            description=data.get("description", ""),
        )
    
    @classmethod
    def press(cls, button: PS5Button, description: str = "") -> "PS5Action":
        """Create a button press action."""
        return cls(PS5ActionType.BUTTON_PRESS, button, description=description)
    
    @classmethod
    def hold(cls, button: PS5Button, duration_ms: int, description: str = "") -> "PS5Action":
        """Create a button hold action."""
        return cls(PS5ActionType.BUTTON_HOLD, button, duration_ms, description)
    
    @classmethod
    def wait(cls, duration_ms: int, description: str = "") -> "PS5Action":
        """Create a wait action."""
        return cls(PS5ActionType.WAIT, duration_ms=duration_ms, description=description)
    
    @classmethod
    def none(cls, description: str = "") -> "PS5Action":
        """Create a no-action response."""
        return cls(PS5ActionType.NONE, description=description)
