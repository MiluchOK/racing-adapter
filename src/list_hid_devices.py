#!/usr/bin/env python3
"""List all connected HID devices."""

import hid


def main():
    """List all connected HID devices with their details."""
    devices = hid.enumerate()

    if not devices:
        print("No HID devices found.")
        return

    print(f"Found {len(devices)} HID device(s):\n")

    for i, device in enumerate(devices, 1):
        print(f"Device {i}:")
        print(f"  Vendor ID:      0x{device['vendor_id']:04x}")
        print(f"  Product ID:     0x{device['product_id']:04x}")
        print(f"  Manufacturer:   {device['manufacturer_string'] or 'N/A'}")
        print(f"  Product:        {device['product_string'] or 'N/A'}")
        print(f"  Serial Number:  {device['serial_number'] or 'N/A'}")
        print(f"  Interface:      {device['interface_number']}")
        print(f"  Path:           {device['path'].decode() if device['path'] else 'N/A'}")
        print()


if __name__ == "__main__":
    main()
