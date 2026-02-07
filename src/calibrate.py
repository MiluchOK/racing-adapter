#!/usr/bin/env python3
"""Calibration wizard for Fanatec wheel."""

import hid
import json
import time
from pathlib import Path

FANATEC_VENDOR_ID = 0x0EB7
FANATEC_PRODUCT_ID = 0x0E07
PROFILE_PATH = Path(__file__).parent.parent / "calibration_profile.json"


def read_current(device, count: int = 5) -> list[int] | None:
    """Read current device state (average of a few samples)."""
    samples = []
    for _ in range(count):
        data = device.read(64, timeout_ms=50)
        if data:
            samples.append(list(data))
    return samples[-1] if samples else None


def find_changed_byte(baseline: list[int], sample: list[int], threshold: int = 10) -> int:
    """Find the byte that changed most from baseline."""
    max_diff = 0
    best_byte = -1

    for i, (base, curr) in enumerate(zip(baseline, sample)):
        diff = abs(curr - base)
        if diff > max_diff and diff >= threshold:
            max_diff = diff
            best_byte = i

    return best_byte


def find_axis_config(baseline: list[int], min_sample: list[int], max_sample: list[int]) -> dict:
    """Determine axis configuration from baseline, min and max samples."""
    # Find which byte changed most
    byte_idx = find_changed_byte(baseline, min_sample, threshold=3)
    if byte_idx < 0:
        byte_idx = find_changed_byte(baseline, max_sample, threshold=3)

    if byte_idx < 0:
        return {"byte": -1, "is_16bit": False, "min": 0, "max": 255}

    # Check if it's 16-bit by looking at next byte
    is_16bit = False
    if byte_idx < 63:
        next_diff_min = abs(baseline[byte_idx + 1] - min_sample[byte_idx + 1])
        next_diff_max = abs(baseline[byte_idx + 1] - max_sample[byte_idx + 1])
        if next_diff_min > 2 or next_diff_max > 2:
            is_16bit = True

    if is_16bit:
        min_val = min_sample[byte_idx] | (min_sample[byte_idx + 1] << 8)
        max_val = max_sample[byte_idx] | (max_sample[byte_idx + 1] << 8)
    else:
        min_val = min_sample[byte_idx]
        max_val = max_sample[byte_idx]

    return {
        "byte": byte_idx,
        "is_16bit": is_16bit,
        "min": min_val,
        "max": max_val,
    }


def wait_for_enter(prompt: str = "Press Enter to continue..."):
    """Wait for user to press Enter."""
    input(prompt)


def main():
    print("=" * 60)
    print("       FANATEC WHEEL CALIBRATION WIZARD")
    print("=" * 60)
    print()

    try:
        device = hid.device()
        device.open(FANATEC_VENDOR_ID, FANATEC_PRODUCT_ID)
        device.set_nonblocking(False)

        manufacturer = device.get_manufacturer_string()
        product = device.get_product_string()
        print(f"Connected to: {manufacturer} - {product}")
        print()
    except OSError as e:
        print(f"Error opening device: {e}")
        return

    profile = {
        "device": {
            "vendor_id": FANATEC_VENDOR_ID,
            "product_id": FANATEC_PRODUCT_ID,
            "name": product or "Fanatec Wheel",
        },
        "steering": {},
        "throttle": {},
        "brake": {},
        "clutch": {},
        "buttons": [],
    }

    try:
        # Step 1: Baseline
        print("-" * 60)
        print("STEP 1: BASELINE")
        print("-" * 60)
        print("Release all pedals and center the steering wheel.")
        wait_for_enter()

        print("Recording baseline...")
        baseline = read_current(device)
        if not baseline:
            print("Failed to read baseline!")
            return
        print("Baseline recorded.\n")

        # Step 2: Steering LEFT
        print("-" * 60)
        print("STEP 2: STEERING - LEFT POSITION")
        print("-" * 60)
        print("Turn the wheel ALL THE WAY LEFT.")
        wait_for_enter("Press Enter when wheel is fully left...")

        steering_left = read_current(device)
        if not steering_left:
            print("Failed to read!")
            return
        print("Left position recorded.\n")

        # Step 3: Steering RIGHT
        print("-" * 60)
        print("STEP 3: STEERING - RIGHT POSITION")
        print("-" * 60)
        print("Turn the wheel ALL THE WAY RIGHT.")
        wait_for_enter("Press Enter when wheel is fully right...")

        steering_right = read_current(device)
        if not steering_right:
            print("Failed to read!")
            return
        print("Right position recorded.\n")

        # Determine steering config
        steering_config = find_axis_config(baseline, steering_left, steering_right)
        profile["steering"] = steering_config
        print(f"  Steering: byte {steering_config['byte']} ({'16-bit' if steering_config['is_16bit'] else '8-bit'})")
        print(f"  Left={steering_config['min']}, Right={steering_config['max']}")
        print()

        # Step 4: Throttle
        print("-" * 60)
        print("STEP 4: THROTTLE PEDAL")
        print("-" * 60)
        print("Press the THROTTLE pedal ALL THE WAY DOWN.")
        wait_for_enter("Press Enter when throttle is fully pressed...")

        throttle_pressed = read_current(device)
        if not throttle_pressed:
            print("Failed to read!")
            return
        print("Throttle recorded.\n")

        throttle_config = find_axis_config(baseline, baseline, throttle_pressed)
        profile["throttle"] = throttle_config
        print(f"  Throttle: byte {throttle_config['byte']} ({'16-bit' if throttle_config['is_16bit'] else '8-bit'})")
        print(f"  Released={throttle_config['min']}, Pressed={throttle_config['max']}")
        print()

        # Step 5: Brake
        print("-" * 60)
        print("STEP 5: BRAKE PEDAL")
        print("-" * 60)
        print("Press the BRAKE pedal ALL THE WAY DOWN.")
        wait_for_enter("Press Enter when brake is fully pressed...")

        brake_pressed = read_current(device)
        if not brake_pressed:
            print("Failed to read!")
            return
        print("Brake recorded.\n")

        brake_config = find_axis_config(baseline, baseline, brake_pressed)
        profile["brake"] = brake_config
        print(f"  Brake: byte {brake_config['byte']} ({'16-bit' if brake_config['is_16bit'] else '8-bit'})")
        print(f"  Released={brake_config['min']}, Pressed={brake_config['max']}")
        print()

        # Step 6: Clutch (optional)
        print("-" * 60)
        print("STEP 6: CLUTCH PEDAL (optional)")
        print("-" * 60)
        response = input("Do you have a clutch pedal? [y/N]: ").strip().lower()

        if response == 'y':
            print("Press the CLUTCH pedal ALL THE WAY DOWN.")
            wait_for_enter("Press Enter when clutch is fully pressed...")

            clutch_pressed = read_current(device)
            if clutch_pressed:
                clutch_config = find_axis_config(baseline, baseline, clutch_pressed)
                profile["clutch"] = clutch_config
                print(f"  Clutch: byte {clutch_config['byte']} ({'16-bit' if clutch_config['is_16bit'] else '8-bit'})")
                print(f"  Released={clutch_config['min']}, Pressed={clutch_config['max']}")
        else:
            profile["clutch"] = {"byte": -1, "is_16bit": False, "min": 0, "max": 255}
            print("  Clutch skipped.")
        print()

        # Step 7: Buttons
        print("-" * 60)
        print("STEP 7: BUTTON MAPPING (optional)")
        print("-" * 60)
        print("For each button: press and HOLD it, then press Enter.")
        print()

        button_names = [
            "Square/X", "Cross/A", "Circle/B", "Triangle/Y",
            "L1/LB", "R1/RB", "Share/Back", "Options/Start",
            "PS/Xbox", "Left Paddle", "Right Paddle",
        ]

        for btn_name in button_names:
            response = input(f"Map '{btn_name}'? [y/N/q to quit]: ").strip().lower()

            if response == 'q':
                break
            elif response != 'y':
                continue

            print(f"  Press and HOLD '{btn_name}'...")
            wait_for_enter("  Press Enter while holding the button...")

            pressed = read_current(device)
            if pressed:
                for i, (base, curr) in enumerate(zip(baseline, pressed)):
                    if base != curr:
                        diff = base ^ curr
                        for bit in range(8):
                            if diff & (1 << bit):
                                profile["buttons"].append({
                                    "name": btn_name,
                                    "byte": i,
                                    "bit": bit,
                                })
                                print(f"    Mapped: byte {i}, bit {bit}")

            print(f"  Release '{btn_name}' now.\n")
            time.sleep(0.2)

        # Save profile
        print()
        print("-" * 60)
        print("CALIBRATION COMPLETE")
        print("-" * 60)

        with open(PROFILE_PATH, 'w') as f:
            json.dump(profile, f, indent=2)

        print(f"Profile saved to: {PROFILE_PATH}")
        print()
        print("Summary:")
        print(f"  Steering: byte {profile['steering'].get('byte', 'N/A')}")
        print(f"  Throttle: byte {profile['throttle'].get('byte', 'N/A')}")
        print(f"  Brake:    byte {profile['brake'].get('byte', 'N/A')}")
        print(f"  Clutch:   byte {profile['clutch'].get('byte', 'N/A')}")
        print(f"  Buttons:  {len(profile['buttons'])} mapped")
        print()
        print("Run 'uv run python src/read_fanatec.py' to use this profile.")

    except KeyboardInterrupt:
        print("\n\nCalibration cancelled.")
    finally:
        device.close()


if __name__ == "__main__":
    main()
