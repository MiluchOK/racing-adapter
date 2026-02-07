#!/usr/bin/env python3
"""Detect which bytes change when inputs are used."""

import hid
import os

FANATEC_VENDOR_ID = 0x0EB7
FANATEC_PRODUCT_ID = 0x0E07


def main():
    """Detect changing bytes to help map inputs."""
    print(f"Opening Fanatec wheel...")

    try:
        device = hid.device()
        device.open(FANATEC_VENDOR_ID, FANATEC_PRODUCT_ID)
        device.set_nonblocking(False)

        print("Connected! Recording baseline (don't touch anything)...")

        # Record baseline
        baseline = None
        for _ in range(10):
            data = device.read(64, timeout_ms=100)
            if data:
                baseline = list(data)
                break

        if not baseline:
            print("Failed to read baseline data")
            return

        print("Baseline recorded. Now press pedals/buttons to see which bytes change.\n")
        print("Press Ctrl+C to stop.\n")

        while True:
            data = device.read(64, timeout_ms=100)
            if data:
                os.system('clear' if os.name == 'posix' else 'cls')

                print("BYTE CHANGE DETECTOR - Press pedals/buttons to find mappings")
                print("=" * 70)
                print("\nChanging bytes (highlighted):\n")

                changes = []
                for i, (base, curr) in enumerate(zip(baseline, data)):
                    if base != curr:
                        changes.append((i, base, curr))

                if changes:
                    print(f"{'Byte':<6} {'Baseline':<10} {'Current':<10} {'Diff':<10} {'As 16-bit (with next byte)'}")
                    print("-" * 70)
                    for idx, base, curr in changes:
                        diff = curr - base
                        # Show 16-bit value if this byte + next byte
                        if idx < 63:
                            val_16 = data[idx] | (data[idx + 1] << 8)
                            print(f"{idx:<6} {base:<10} {curr:<10} {diff:+<10} {val_16}")
                        else:
                            print(f"{idx:<6} {base:<10} {curr:<10} {diff:+<10}")
                else:
                    print("No changes detected - press a pedal or button!")

                print("\n" + "=" * 70)
                print("\nFull data (64 bytes):")
                print("      " + "  ".join(f"{i:2d}" for i in range(16)))
                print("      " + "-" * 47)
                for row in range(4):
                    start = row * 16
                    end = start + 16
                    row_data = data[start:end]
                    prefix = f"{start:2d}:  "
                    hex_vals = "  ".join(f"{b:02x}" for b in row_data)
                    print(f"{prefix}{hex_vals}")

    except OSError as e:
        print(f"Error: {e}")
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        if 'device' in locals():
            device.close()


if __name__ == "__main__":
    main()
