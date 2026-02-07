#!/usr/bin/env python3
"""
HID Device Mapper

Shows baseline vs current state side-by-side.
Press a button to see which bytes change.

Usage:
  uv run src/hid_mapper.py
  uv run src/hid_mapper.py --vid 0x0EB7 --pid 0x0E07
  uv run src/hid_mapper.py --diagnose   # Run diagnostics first
"""

import argparse
import curses
import time
import hid


def list_devices():
    """List all connected HID devices."""
    devices = hid.enumerate()
    seen = {}
    for device in devices:
        key = (device['vendor_id'], device['product_id'])
        if key not in seen:
            seen[key] = device
    return list(seen.values())


def list_interfaces(vid, pid):
    """List all interfaces for a specific device."""
    devices = hid.enumerate(vid, pid)
    return devices


def select_device(devices):
    """Let user select a device."""
    if not devices:
        print("No HID devices found.")
        return None, None

    print(f"Found {len(devices)} device(s):\n")
    for i, d in enumerate(devices, 1):
        name = d['product_string'] or d['manufacturer_string'] or 'Unknown'
        print(f"  [{i}] {name}")
        print(f"      VID: 0x{d['vendor_id']:04X}  PID: 0x{d['product_id']:04X}")
        print()

    if len(devices) == 1:
        d = devices[0]
        print(f"Auto-selecting: {d['product_string'] or 'Unknown'}")
        return d['vendor_id'], d['product_id']

    try:
        choice = input("Select device number: ").strip()
        idx = int(choice) - 1
        if 0 <= idx < len(devices):
            d = devices[idx]
            return d['vendor_id'], d['product_id']
    except (ValueError, KeyboardInterrupt):
        pass
    return None, None


def open_device(vid: int, pid: int):
    """Open a HID device, trying all interfaces if needed."""
    interfaces = list_interfaces(vid, pid)

    if not interfaces:
        print(f"No interfaces found for VID=0x{vid:04X} PID=0x{pid:04X}")
        return None, None

    print(f"\nFound {len(interfaces)} interface(s) for this device:")
    for i, iface in enumerate(interfaces):
        usage = f"usage_page=0x{iface['usage_page']:04X} usage=0x{iface['usage']:04X}"
        iface_num = iface.get('interface_number', '?')
        print(f"  [{i+1}] Interface {iface_num}: {usage}")

    # Try to open each interface until one works
    device = hid.device()
    opened_iface = None

    for i, iface in enumerate(interfaces):
        try:
            device.open_path(iface['path'])
            device.set_nonblocking(False)
            opened_iface = iface
            print(f"\n✓ Opened interface {i+1} (interface_number={iface.get('interface_number', '?')})")
            break
        except OSError:
            continue

    if not opened_iface:
        print("\n✗ Failed to open any interface")
        print("  Try running with sudo: sudo uv run src/hid_mapper.py")
        return None, None

    info = device.get_product_string() or opened_iface.get('product_string') or "Unknown Device"
    return device, info


def get_usage_name(usage_page, usage):
    """Get human-readable name for HID usage."""
    if usage_page == 0x01:  # Generic Desktop
        names = {
            0x01: "Pointer",
            0x02: "Mouse",
            0x04: "Joystick",
            0x05: "Gamepad",
            0x06: "Keyboard",
            0x07: "Keypad",
            0x08: "Multi-axis Controller",
        }
        return names.get(usage, f"Desktop 0x{usage:02X}")
    elif usage_page == 0x0C:
        return "Consumer Control"
    elif usage_page == 0x0F:
        return "Physical (Force Feedback)"
    elif usage_page >= 0xFF00:
        return "Vendor Defined"
    return f"0x{usage_page:04X}/0x{usage:02X}"


def diagnose_device(vid: int, pid: int):
    """Run diagnostics on HID device to verify data integrity."""

    print("\n" + "=" * 60)
    print("HID DEVICE DIAGNOSTIC REPORT")
    print("=" * 60)

    # List all interfaces first
    interfaces = list_interfaces(vid, pid)

    if not interfaces:
        print("\n✗ FAILED: Device not found")
        print("  Make sure it's plugged in and try: sudo uv run ...")
        return

    # Categorize interfaces
    input_interfaces = []
    other_interfaces = []
    for iface in interfaces:
        usage_page = iface['usage_page']
        usage = iface['usage']
        if usage_page == 0x01 and usage in (0x04, 0x05):  # Joystick or Gamepad
            input_interfaces.append(iface)
        else:
            other_interfaces.append(iface)

    # Open device
    device, info = open_device(vid, pid)
    if not device:
        return

    # Collect data
    print("\nCollecting data (don't touch anything)...")
    frames = []
    start_time = time.time()
    timeout_count = 0
    while len(frames) < 100 and timeout_count < 50:
        data = device.read(64, timeout_ms=100)
        if data:
            frames.append(list(data))
            timeout_count = 0
        else:
            timeout_count += 1
    elapsed = time.time() - start_time
    device.close()

    # === SUMMARY (Plain English) ===
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    # 1. Connection status
    print(f"\n✓ CONNECTED: {info}")
    print(f"  Vendor ID: 0x{vid:04X}, Product ID: 0x{pid:04X}")

    # 2. What can this device do?
    print(f"\nWHAT THIS DEVICE PROVIDES:")
    if input_interfaces:
        print(f"  ✓ Controller inputs (buttons, axes) - {len(input_interfaces)} channel(s)")
    else:
        print(f"  ? No standard controller interface found")

    has_ff = any(i['usage_page'] == 0x0F for i in interfaces)
    has_vendor = any(i['usage_page'] >= 0xFF00 for i in interfaces)

    if has_ff:
        print(f"  ✓ Force feedback / vibration")
    if has_vendor:
        print(f"  ? Vendor-specific features (LEDs, settings, etc.)")

    # 3. Data quality
    if not frames:
        print(f"\n✗ DATA PROBLEM: No data received from device")
        print(f"  The device connected but isn't sending any data.")
        print(f"  This might be the wrong interface (LED control, etc.)")
        return

    report_size = len(frames[0])
    frame_rate = len(frames) / elapsed if elapsed > 0 else 0

    print(f"\nDATA QUALITY:")
    print(f"  ✓ Receiving data: {report_size} bytes per update")

    if frame_rate >= 100:
        print(f"  ✓ Fast updates: ~{frame_rate:.0f} times per second (good for racing)")
    elif frame_rate >= 50:
        print(f"  ✓ Updates: ~{frame_rate:.0f} times per second (OK)")
    else:
        print(f"  ⚠ Slow updates: ~{frame_rate:.0f} times per second (may feel laggy)")

    # Analyze stability
    byte_analysis = []
    for i in range(report_size):
        values = [f[i] for f in frames]
        unique = len(set(values))
        byte_analysis.append({
            'index': i,
            'min': min(values),
            'max': max(values),
            'unique': unique,
        })

    stable_bytes = [b for b in byte_analysis if b['unique'] == 1]
    jittery_bytes = [b for b in byte_analysis if b['unique'] > 10]

    if len(jittery_bytes) == 0:
        print(f"  ✓ Stable signal: no noise detected")
    elif len(jittery_bytes) <= 2:
        print(f"  ⚠ Minor noise: {len(jittery_bytes)} byte(s) fluctuating slightly")
    else:
        print(f"  ✗ Noisy signal: {len(jittery_bytes)} bytes changing randomly")
        print(f"    Check USB cable or try a different port")

    # 4. What to do next
    print(f"\nNEXT STEPS:")
    print(f"  1. Run the mapper:  uv run src/hid_mapper.py")
    print(f"  2. Press buttons one at a time to see which bytes change")
    print(f"  3. Use [r] to set a new baseline while holding a button")

    # === TECHNICAL DETAILS (for debugging) ===
    print("\n" + "=" * 60)
    print("TECHNICAL DETAILS")
    print("=" * 60)

    print(f"\nInterfaces ({len(interfaces)} total):")
    for i, iface in enumerate(interfaces):
        usage_page = iface['usage_page']
        usage = iface['usage']
        usage_name = get_usage_name(usage_page, usage)
        iface_num = iface.get('interface_number', '?')
        print(f"  [{i+1}] Interface {iface_num}: {usage_name}")

    print(f"\nSample data (first frame, hex):")
    if frames:
        hex_str = " ".join(f"{b:02X}" for b in frames[0][:16])
        print(f"  {hex_str}")
        if report_size > 16:
            hex_str2 = " ".join(f"{b:02X}" for b in frames[0][16:32])
            print(f"  {hex_str2}")

    print(f"\nByte stability (when nothing is touched):")
    print(f"  Constant: {len(stable_bytes)} bytes never change")
    print(f"  Variable: {len(jittery_bytes)} bytes fluctuate")

    if jittery_bytes:
        idxs = ", ".join(f"[{b['index']}]" for b in jittery_bytes[:5])
        print(f"  Fluctuating bytes: {idxs}")

    print()


def map_device(vid: int, pid: int):
    """Interactive mapping with curses display."""
    print(f"\nOpening device VID=0x{vid:04X} PID=0x{pid:04X}...")

    device, info = open_device(vid, pid)
    if not device:
        return

    print(f"Connected to: {info}\n")

    # Record baseline
    print("Recording baseline - DON'T TOUCH ANYTHING...")
    baseline = None
    for _ in range(30):
        data = device.read(64, timeout_ms=100)
        if data:
            baseline = list(data)
            break

    if not baseline:
        print("Failed to read from device")
        device.close()
        return

    print(f"Baseline recorded! ({len(baseline)} bytes)")
    print("Starting mapper... Press 'r' to re-record baseline, 'q' to quit\n")

    def run_curses(stdscr):
        nonlocal baseline
        curses.curs_set(0)
        curses.start_color()
        curses.init_pair(1, curses.COLOR_YELLOW, curses.COLOR_BLACK)  # Changed
        curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)   # Same
        curses.init_pair(3, curses.COLOR_CYAN, curses.COLOR_BLACK)    # Header
        stdscr.nodelay(True)

        while True:
            data = device.read(64, timeout_ms=50)
            if not data:
                continue

            data = list(data)
            stdscr.erase()

            # Header
            stdscr.attron(curses.color_pair(3) | curses.A_BOLD)
            stdscr.addstr(0, 0, f"HID MAPPER - {info}")
            stdscr.addstr(1, 0, f"VID: 0x{vid:04X}  PID: 0x{pid:04X}  Report: {len(data)} bytes")
            stdscr.attroff(curses.color_pair(3) | curses.A_BOLD)

            # Column headers
            stdscr.addstr(3, 0, "Byte   BASELINE   CURRENT    DIFF    Notes")
            stdscr.addstr(4, 0, "─" * 60)

            # Compare each byte
            row = 5
            changes = []
            for i in range(len(baseline)):
                base_val = baseline[i]
                curr_val = data[i] if i < len(data) else 0
                diff = curr_val - base_val

                if base_val != curr_val:
                    # This byte changed - highlight it
                    changes.append(i)
                    stdscr.attron(curses.color_pair(1) | curses.A_BOLD)

                    # Check if it's a single bit change
                    bit_diff = base_val ^ curr_val
                    note = ""
                    if bit_diff and (bit_diff & (bit_diff - 1)) == 0:
                        bit_num = bit_diff.bit_length() - 1
                        note = f"← bit {bit_num}"

                    line = f"[{i:2d}]     {base_val:3d}       {curr_val:3d}     {diff:+4d}    {note}"
                    stdscr.addstr(row, 0, line)
                    stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)
                    row += 1

            if not changes:
                stdscr.attron(curses.color_pair(2))
                stdscr.addstr(row, 0, "(no changes - press a button or move a control)")
                stdscr.attroff(curses.color_pair(2))
                row += 1

            # Raw hex view
            row += 1
            stdscr.addstr(row, 0, "─" * 60)
            row += 1
            stdscr.addstr(row, 0, "RAW HEX (baseline → current):")
            row += 1

            # Show hex with highlighting
            stdscr.addstr(row, 0, "     ")
            for i in range(min(16, len(baseline))):
                stdscr.addstr(f"{i:02X} ")
            row += 1

            for hexrow in range(min(4, (len(baseline) + 15) // 16)):
                start = hexrow * 16
                stdscr.addstr(row, 0, f"{start:02X}│B ")
                for i in range(start, min(start + 16, len(baseline))):
                    if i in changes:
                        stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
                    stdscr.addstr(f"{baseline[i]:02X} ")
                    if i in changes:
                        stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)
                row += 1

                stdscr.addstr(row, 0, f"  │C ")
                for i in range(start, min(start + 16, len(data))):
                    if i in changes:
                        stdscr.attron(curses.color_pair(1) | curses.A_BOLD)
                    stdscr.addstr(f"{data[i]:02X} ")
                    if i in changes:
                        stdscr.attroff(curses.color_pair(1) | curses.A_BOLD)
                row += 1

            row += 1
            stdscr.addstr(row, 0, "─" * 60)
            row += 1
            stdscr.addstr(row, 0, "[r] Re-record baseline  [q] Quit")

            stdscr.refresh()

            # Handle keys
            try:
                key = stdscr.getch()
                if key == ord('q'):
                    break
                elif key == ord('r'):
                    # Re-record baseline with current state
                    baseline = list(data)
            except:
                pass

    try:
        curses.wrapper(run_curses)
    except KeyboardInterrupt:
        pass
    finally:
        device.close()
        print("\nMapper closed.")


def main():
    parser = argparse.ArgumentParser(description="Map HID device inputs")
    parser.add_argument("--vid", type=lambda x: int(x, 0), help="Vendor ID")
    parser.add_argument("--pid", type=lambda x: int(x, 0), help="Product ID")
    parser.add_argument("--diagnose", "-d", action="store_true",
                        help="Run diagnostics to verify data integrity")
    args = parser.parse_args()

    # Get device
    if args.vid and args.pid:
        vid, pid = args.vid, args.pid
    else:
        devices = list_devices()
        vid, pid = select_device(devices)

    if not vid or not pid:
        print("No device selected.")
        return

    if args.diagnose:
        diagnose_device(vid, pid)
    else:
        map_device(vid, pid)


if __name__ == "__main__":
    main()
