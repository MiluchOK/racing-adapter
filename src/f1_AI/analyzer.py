"""F1 Screenshot Analyzer using OpenAI Vision API."""

import base64
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from .ps5_actions import PS5Action, PS5ActionType, PS5Button

# Load environment variables from .env file
load_dotenv()

# Re-export for convenience
__all__ = ["F1ScreenAnalyzer", "PS5Action"]

SYSTEM_PROMPT = """You are an AI assistant that analyzes F1 video game screenshots and determines
the next PS5 controller action needed to navigate to a flying lap in time trial mode.

Your goal is to help the user navigate through menus and loading screens to start a flying lap.
A "flying lap" is a timed lap in time trial mode where the car is already at speed.

TARGET CONFIGURATION:
- Track: BELGIUM (Spa-Francorchamps)
- Team/Car: McLAREN

Analyze the screenshot and determine what screen/state the game is in, then provide the
single next action needed to progress toward starting a flying lap.

PS5 System screens:
- PS5 Home Screen: Navigate to the F1 game icon using dpad_left/dpad_right, then press cross to launch
- PS5 Game Library: Find F1 game and press cross to launch
- PS5 Quick Menu: Press circle to close and return to home screen

F1 Game Menu Navigation (FOLLOW THIS PATH):
1. Main Menu: Select "F1 WORLD" option (NOT Career, NOT Grand Prix - specifically "F1 World")
2. F1 World Menu: Navigate RIGHT using dpad_right repeatedly - "TIME TRIAL" is all the way to the RIGHT side of the menu. Keep pressing dpad_right until you see "Time Trial", then press cross to select.
3. Time Trial Menu: Start or continue time trial session
4. Track Selection: Navigate to and select BELGIUM (Spa-Francorchamps). NOTE: There are MORE tracks if you scroll RIGHT - keep pressing dpad_right to find Belgium/Spa.
5. Car/Team Selection: Navigate to and select McLAREN
6. Session Setup: Configure session and press START/CONFIRM
7. Loading Screen: Wait for loading to complete
8. Pre-Race/Pit Screen: Start the session / Exit pit
9. In-Car/On-Track: If already on track in time trial, the goal is achieved

IMPORTANT: Time Trial is found INSIDE "F1 World", not on the main menu directly!

Available PS5 buttons:
- cross: Confirm/Select (X button)
- circle: Back/Cancel (O button)
- square: Square button
- triangle: Triangle button
- dpad_up, dpad_down, dpad_left, dpad_right: D-pad navigation
- l1, r1, l2, r2: Shoulder buttons
- options: Options/Pause button
- touchpad: Touchpad press

IMPORTANT: Respond with ONLY a valid JSON object (no markdown, no code blocks):
{
    "screen_state": "Brief description of what's on screen",
    "action_type": "button_press",
    "button": "dpad_right",
    "duration_ms": 100,
    "reason": "Why this specific button press is needed",
    "progress": "ps5_home|game_menu|mode_select|track_select|loading|on_track"
}

CRITICAL RULES:
- action_type MUST be exactly one of: "button_press", "button_hold", "wait", "none"
- button MUST be exactly one of: cross, circle, square, triangle, dpad_up, dpad_down, dpad_left, dpad_right, l1, r1, l2, r2, options, touchpad
- For ANY navigation or selection, use action_type="button_press" with the appropriate button
- action_type="none" ONLY when already on track doing a flying lap
- action_type="wait" ONLY during loading screens (set duration_ms to wait time)

Example for PS5 home screen needing to navigate right:
{"screen_state": "PS5 home screen, F1 game icon is to the right", "action_type": "button_press", "button": "dpad_right", "duration_ms": 100, "reason": "Navigate right to reach F1 game icon", "progress": "ps5_home"}"""


class F1ScreenAnalyzer:
    """Analyzes F1 game screenshots to determine next navigation action."""

    def __init__(self, api_key: str | None = None, model: str = "gpt-4o"):
        """
        Initialize the analyzer.
        
        Args:
            api_key: OpenAI API key. If not provided, uses OPENAI_API_KEY env var.
            model: OpenAI model to use (must support vision). Default: gpt-4o
        """
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key required. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )
        
        self.client = OpenAI(api_key=self.api_key)
        self.model = model
    
    def _encode_image(self, image_path: str | Path) -> str:
        """Encode image to base64 for API request."""
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Screenshot not found: {path}")
        
        with open(path, "rb") as f:
            return base64.standard_b64encode(f.read()).decode("utf-8")
    
    def _get_image_media_type(self, image_path: str | Path) -> str:
        """Determine the media type based on file extension."""
        path = Path(image_path)
        suffix = path.suffix.lower()
        media_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        return media_types.get(suffix, "image/png")
    
    def _parse_response(self, response_text: str) -> PS5Action:
        """Parse the OpenAI response into a PS5Action."""
        # Try to extract JSON from response
        try:
            # Handle case where response might have markdown code blocks
            text = response_text.strip()
            if text.startswith("```"):
                # Remove markdown code block
                lines = text.split("\n")
                text = "\n".join(lines[1:-1])
            
            data = json.loads(text)
        except json.JSONDecodeError as e:
            return PS5Action.none(f"Failed to parse AI response: {e}")
        
        # Extract action details
        action_type_str = data.get("action_type", "none")
        button_str = data.get("button")
        duration_ms = data.get("duration_ms", 100)
        reason = data.get("reason") or data.get("description", "")
        screen_state = data.get("screen_state", "")
        progress = data.get("progress", "")

        # Build full description
        full_description = f"[{progress}] {screen_state}: {reason}"
        
        # Convert to enum types
        try:
            action_type = PS5ActionType(action_type_str)
        except ValueError:
            return PS5Action.none(f"Unknown action type: {action_type_str}")
        
        # Handle different action types
        if action_type == PS5ActionType.NONE:
            return PS5Action.none(full_description)
        
        if action_type == PS5ActionType.WAIT:
            return PS5Action.wait(duration_ms, full_description)
        
        # Button actions require a valid button
        if not button_str:
            return PS5Action.none(f"No button specified for {action_type_str}")
        
        try:
            button = PS5Button(button_str)
        except ValueError:
            return PS5Action.none(f"Unknown button: {button_str}")
        
        if action_type == PS5ActionType.BUTTON_HOLD:
            return PS5Action.hold(button, duration_ms, full_description)
        
        return PS5Action.press(button, full_description)
    
    def analyze(self, screenshot_path: str | Path) -> PS5Action:
        """
        Analyze a screenshot and return the next PS5 action.
        
        Args:
            screenshot_path: Path to the screenshot image file.
            
        Returns:
            PS5Action representing the next action to take.
        """
        image_data = self._encode_image(screenshot_path)
        media_type = self._get_image_media_type(screenshot_path)
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Analyze this F1 game screenshot and tell me the next PS5 action to get to a flying lap.",
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{media_type};base64,{image_data}",
                            },
                        },
                    ],
                },
            ],
            max_tokens=500,
        )
        
        response_text = response.choices[0].message.content
        return self._parse_response(response_text)
    
    def analyze_with_raw_response(self, screenshot_path: str | Path) -> tuple[PS5Action, str]:
        """
        Analyze a screenshot and return both the action and raw AI response.
        
        Useful for debugging or logging.
        
        Args:
            screenshot_path: Path to the screenshot image file.
            
        Returns:
            Tuple of (PS5Action, raw_response_text)
        """
        image_data = self._encode_image(screenshot_path)
        media_type = self._get_image_media_type(screenshot_path)
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Analyze this F1 game screenshot and tell me the next PS5 action to get to a flying lap.",
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{media_type};base64,{image_data}",
                            },
                        },
                    ],
                },
            ],
            max_tokens=500,
        )
        
        response_text = response.choices[0].message.content
        action = self._parse_response(response_text)
        return action, response_text


# CLI for testing
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m f1_AI.analyzer <screenshot_path>")
        print("\nAnalyzes an F1 game screenshot and outputs the next PS5 action.")
        print("\nRequires OPENAI_API_KEY in .env file or environment.")
        sys.exit(1)
    
    screenshot_path = sys.argv[1]
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    
    try:
        analyzer = F1ScreenAnalyzer()
        action = analyzer.analyze(screenshot_path)
        
        if verbose:
            print(f"Screenshot: {screenshot_path}")
            print(f"Action: {action}")
            print(f"Details: {action.to_dict()}")
        else:
            # Simple output: just the button to press
            if action.button:
                print(action.button.value)
            else:
                print(action.action_type.value)
        
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
