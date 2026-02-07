#!/usr/bin/env python3
"""
Simple servo control script for Arduino Uno R4.
Sends servo angles over serial to move a servo connected to pin D9.
"""

import time
import serial

# Configuration
SERIAL_PORT = "/dev/cu.usbmodem3CDC75EDAA6C2"  # Change this to match your Arduino port
BAUD_RATE = 115200
RESET_DELAY = 2.0  # Seconds to wait for Arduino reset after opening port
ANGLE_DELAY = 1.0  # Seconds between angle commands

# Servo angles to cycle through
ANGLES = [0, 45, 90, 135, 180]


def main():
    print(f"Opening serial port {SERIAL_PORT} at {BAUD_RATE} baud...", flush=True)

    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)

    print(f"Waiting {RESET_DELAY}s for Arduino to reset...", flush=True)
    time.sleep(RESET_DELAY)

    print("Starting servo control loop. Press Ctrl+C to stop.", flush=True)

    try:
        while True:
            for angle in ANGLES:
                command = f"{angle}\n"
                ser.write(command.encode("utf-8"))
                print(f"Sent angle: {angle}", flush=True)
                time.sleep(ANGLE_DELAY)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        ser.close()
        print("Serial port closed.")


if __name__ == "__main__":
    main()
