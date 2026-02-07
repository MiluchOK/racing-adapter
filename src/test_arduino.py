#!/usr/bin/env python3
"""
Arduino RC Protocol Tester

Send manual RC commands to Arduino for testing LED response.

Usage:
  uv run src/test_arduino.py <arduino-ip> <steer> [throttle] [brake]

Examples:
  uv run src/test_arduino.py 192.168.1.100 0       # Full left
  uv run src/test_arduino.py 192.168.1.100 128     # Center
  uv run src/test_arduino.py 192.168.1.100 255     # Full right
  uv run src/test_arduino.py 192.168.1.100 128 255 0  # Center, full throttle

Or use netcat directly:
  echo "RC:0,0,0" | nc -u -w1 <arduino-ip> 20777
  echo "RC:128,0,0" | nc -u -w1 <arduino-ip> 20777
  echo "RC:255,0,0" | nc -u -w1 <arduino-ip> 20777
"""

import socket
import sys
import argparse
import time


def send_command(ip: str, port: int, steer: int, throttle: int, brake: int):
    """Send a single RC command to Arduino"""
    packet = f"RC:{steer},{throttle},{brake}\n"

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(packet.encode(), (ip, port))
    sock.close()

    print(f"Sent: {packet.strip()} → {ip}:{port}")


def sweep_test(ip: str, port: int, delay: float = 0.1):
    """Sweep steering from left to right and back"""
    print(f"Sweeping steering on {ip}:{port}...")
    print("Press Ctrl+C to stop")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        while True:
            # Left to right
            for steer in range(0, 256, 8):
                packet = f"RC:{steer},0,0\n"
                sock.sendto(packet.encode(), (ip, port))
                print(f"\rSteer: {steer:3d}", end="", flush=True)
                time.sleep(delay)

            # Right to left
            for steer in range(255, -1, -8):
                packet = f"RC:{steer},0,0\n"
                sock.sendto(packet.encode(), (ip, port))
                print(f"\rSteer: {steer:3d}", end="", flush=True)
                time.sleep(delay)

    except KeyboardInterrupt:
        print("\nSweep stopped.")
    finally:
        sock.close()


def main():
    parser = argparse.ArgumentParser(
        description="Send RC commands to Arduino for testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s 192.168.1.100 0           # Full left steering
  %(prog)s 192.168.1.100 128         # Center steering
  %(prog)s 192.168.1.100 255         # Full right steering
  %(prog)s 192.168.1.100 128 255 0   # Center, full throttle
  %(prog)s 192.168.1.100 --sweep     # Continuous sweep test
"""
    )
    parser.add_argument("arduino_ip", help="Arduino IP address")
    parser.add_argument("steer", nargs="?", type=int, default=128,
                        help="Steering value 0-255 (default: 128)")
    parser.add_argument("throttle", nargs="?", type=int, default=0,
                        help="Throttle value 0-255 (default: 0)")
    parser.add_argument("brake", nargs="?", type=int, default=0,
                        help="Brake value 0-255 (default: 0)")
    parser.add_argument("--port", type=int, default=20777,
                        help="Arduino UDP port (default: 20777)")
    parser.add_argument("--sweep", action="store_true",
                        help="Run continuous sweep test")
    parser.add_argument("--sweep-delay", type=float, default=0.05,
                        help="Delay between sweep steps in seconds (default: 0.05)")

    args = parser.parse_args()

    # Validate values
    for name, val in [("steer", args.steer), ("throttle", args.throttle), ("brake", args.brake)]:
        if val < 0 or val > 255:
            print(f"Error: {name} must be 0-255, got {val}")
            sys.exit(1)

    if args.sweep:
        sweep_test(args.arduino_ip, args.port, args.sweep_delay)
    else:
        send_command(args.arduino_ip, args.port, args.steer, args.throttle, args.brake)


if __name__ == "__main__":
    main()
