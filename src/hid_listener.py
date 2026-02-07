#!/usr/bin/env python3
"""
Generic HID Device Listener

Connects to a HID device and displays raw input data in real-time.

Usage:
  uv run src/hid_listener.py                      # Auto-detect or list devices
  uv run src/hid_listener.py --vid 0x0EB7 --pid 0x0E07  # Specific device
  uv run src/hid_listener.py --list               # List all HID devices
"""

import argparse
import curses
import hid


def list_devices():
    """List all connected HID devices."""
    devices = hid.enumerate()

    if not devices:
        print("No HID devices found.")
        return []

    print(f"Found {len(devices)} HID device(s):\n")

    # Group by vendor_id + product_id
    seen = {}
    for device in devices:
        key = (device['vendor_id'], device['product_id'])
        if key not in seen:
            seen[key] = device

    unique_devices = list(seen.values())

    for i, device in enumerate(unique_devices, 1):
        name = device['product_string'] or device['manufacturer_string'] or 'Unknown'
        print(f"  [{i}] {name}")
        print(f"      VID: 0x{device['vendor_id']:04X}  PID: 0x{device['product_id']:04X}")
        print(f"      Manufacturer: {device['manufacturer_string'] or 'N/A'}")
        print()

    return unique_devices


def select_device(devices):
    """Let user select a device from the list."""
    if not devices:
        return None, None

    if len(devices) == 1:
        d = devices[0]
        print(f"Auto-selecting: {d['product_string'] or 'Unknown'}")
        return d['vendor_id'], d['product_id']

    try:
        choice = input("Select device number (or press Enter to cancel): ").strip()
        if not choice:
            return None, None
        idx = int(choice) - 1
        if 0 <= idx < len(devices):
            d = devices[idx]
            return d['vendor_id'], d['product_id']
    except (ValueError, KeyboardInterrupt):
        pass

    return None, None


def listen_to_device(vid: int, pid: int):
    """Listen to HID device and display data."""
    print(f"\nOpening device VID=0x{vid:04X} PID=0x{pid:04X}...")

    try:
        device = hid.device()
        device.open(vid, pid)
        device.set_nonblocking(False)

        info = device.get_product_string() or "Unknown Device"
        print(f"Connected to: {info}")
        print("\nRecording baseline (don't touch anything)...")

        # Record baseline
        baseline = None
        for _ in range(20):
            data = device.read(64, timeout_ms=100)
            if data:
                baseline = list(data)
                break

        if not baseline:
            print("Failed to read data from device")
            return

        print("Baseline recorded! Starting display...")

        # Use curses for flicker-free display
        def curses_main(stdscr):
            curses.curs_set(0)  # Hide cursor
            stdscr.nodelay(True)  # Non-blocking input

            while True:
                data = device.read(64, timeout_ms=50)
                if not data:
                    continue

                stdscr.erase()

                stdscr.addstr(0, 0, "╔══════════════════════════════════════════════════════════════════╗")
                stdscr.addstr(1, 0, f"║  HID LISTENER - {info:<47} ║")
                stdscr.addstr(2, 0, f"║  VID: 0x{vid:04X}  PID: 0x{pid:04X}                                       ║")
                stdscr.addstr(3, 0, "╠══════════════════════════════════════════════════════════════════╣")

                # Find changes
                changes = []
                for i, (base, curr) in enumerate(zip(baseline, data)):
                    if base != curr:
                        changes.append((i, base, curr))

                row = 4
                if changes:
                    stdscr.addstr(row, 0, "║  CHANGED BYTES:                                                  ║"); row += 1
                    stdscr.addstr(row, 0, "║  Byte   Base   Now    Diff   16-bit                             ║"); row += 1
                    stdscr.addstr(row, 0, "║  ─────────────────────────────────────                          ║"); row += 1
                    for idx, base, curr in changes[:8]:
                        diff = curr - base
                        if idx < len(data) - 1:
                            val_16 = data[idx] | (data[idx + 1] << 8)
                            stdscr.addstr(row, 0, f"║  [{idx:2d}]   {base:3d}    {curr:3d}   {diff:+4d}   {val_16:5d}                             ║")
                        else:
                            stdscr.addstr(row, 0, f"║  [{idx:2d}]   {base:3d}    {curr:3d}   {diff:+4d}                                    ║")
                        row += 1
                    if len(changes) > 8:
                        stdscr.addstr(row, 0, f"║  ... and {len(changes) - 8} more changes                                    ║"); row += 1
                else:
                    stdscr.addstr(row, 0, "║  No changes - move a control or press a button!                  ║"); row += 1

                stdscr.addstr(row, 0, "╠══════════════════════════════════════════════════════════════════╣"); row += 1
                stdscr.addstr(row, 0, "║  RAW DATA (hex):                                                 ║"); row += 1
                stdscr.addstr(row, 0, "║       0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F             ║"); row += 1

                for hexrow in range(4):
                    start = hexrow * 16
                    end = min(start + 16, len(data))
                    if start >= len(data):
                        break
                    row_data = data[start:end]
                    hex_str = " ".join(f"{b:02X}" for b in row_data)
                    stdscr.addstr(row, 0, f"║  {start:02X}: {hex_str:<48}   ║"); row += 1

                stdscr.addstr(row, 0, "╚══════════════════════════════════════════════════════════════════╝"); row += 1
                stdscr.addstr(row + 1, 0, "Press Ctrl+C to stop")

                stdscr.refresh()

                # Check for 'q' key
                try:
                    key = stdscr.getch()
                    if key == ord('q'):
                        break
                except:
                    pass

        curses.wrapper(curses_main)

    except OSError as e:
        print(f"Error: {e}")
        print("\nMake sure:")
        print("  1. The device is connected")
        print("  2. No other program is using it")
        print("  3. You have permissions (try: sudo uv run ...)")
    except KeyboardInterrupt:
        print("\n\nStopped.")
    finally:
        if 'device' in locals():
            device.close()


def main():
    parser = argparse.ArgumentParser(description="Listen to HID device input")
    parser.add_argument("--vid", type=lambda x: int(x, 0), help="Vendor ID (e.g., 0x0EB7)")
    parser.add_argument("--pid", type=lambda x: int(x, 0), help="Product ID (e.g., 0x0E07)")
    parser.add_argument("--list", "-l", action="store_true", help="List all HID devices")
    args = parser.parse_args()

    if args.list:
        list_devices()
        return

    if args.vid and args.pid:
        listen_to_device(args.vid, args.pid)
    else:
        # Interactive mode
        print("HID Device Listener\n")
        devices = list_devices()
        vid, pid = select_device(devices)
        if vid and pid:
            listen_to_device(vid, pid)
        else:
            print("No device selected.")


if __name__ == "__main__":
    main()
