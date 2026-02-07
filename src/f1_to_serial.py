#!/usr/bin/env python3
"""
F1 to Serial Bridge

Listens for F1 UDP telemetry and sends RC commands to Arduino over Serial.

Usage:
  uv run src/f1_to_serial.py                      # Auto-detect serial port
  uv run src/f1_to_serial.py -p /dev/cu.usbmodem* # Specify port
  uv run src/f1_to_serial.py --list               # List available ports
  uv run src/f1_to_serial.py --flash              # Flash firmware first

Configuration:
  Set ARDUINO_PORT environment variable to skip auto-detection:
    export ARDUINO_PORT=/dev/cu.usbmodem101
    uv run src/f1_to_serial.py

Finding your Arduino port:
  macOS:   ls /dev/cu.usbmodem*
  Linux:   ls /dev/ttyACM* /dev/ttyUSB*
  Windows: Check Device Manager for COM ports

  Or run: uv run src/f1_to_serial.py --list
"""

import socket
import struct
import subprocess
import sys
import os
import argparse
import time
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Optional

import serial
import serial.tools.list_ports

# Firmware location relative to this script
FIRMWARE_DIR = Path(__file__).parent.parent / "rc-car-firmware"
ARDUINO_FQBN = "arduino:renesas_uno:unor4wifi"


class PacketId(IntEnum):
    """F1 UDP packet types"""
    MOTION = 0
    SESSION = 1
    LAP_DATA = 2
    EVENT = 3
    PARTICIPANTS = 4
    CAR_SETUPS = 5
    CAR_TELEMETRY = 6
    CAR_STATUS = 7
    FINAL_CLASSIFICATION = 8
    LOBBY_INFO = 9
    CAR_DAMAGE = 10
    SESSION_HISTORY = 11
    TYRE_SETS = 12
    MOTION_EX = 13


@dataclass
class PacketHeader:
    """F1 UDP packet header (29 bytes)"""
    packet_format: int
    game_year: int
    game_major_version: int
    game_minor_version: int
    packet_version: int
    packet_id: int
    session_uid: int
    session_time: float
    frame_identifier: int
    overall_frame_identifier: int
    player_car_index: int
    secondary_player_car_index: int


@dataclass
class CarTelemetry:
    """Car telemetry data"""
    speed: int                    # km/h
    throttle: float               # 0.0 - 1.0
    steer: float                  # -1.0 (left) to 1.0 (right)
    brake: float                  # 0.0 - 1.0
    clutch: int                   # 0 - 100
    gear: int                     # -1=R, 0=N, 1-8
    engine_rpm: int
    drs: int                      # 0=off, 1=on
    rev_lights_percent: int       # 0-100
    rev_lights_bit: int
    brake_temps: tuple            # RL, RR, FL, FR
    tyre_surface_temps: tuple     # RL, RR, FL, FR
    tyre_inner_temps: tuple       # RL, RR, FL, FR
    engine_temp: int              # Celsius
    tyre_pressures: tuple         # RL, RR, FL, FR (PSI)
    surface_types: tuple          # RL, RR, FL, FR


def parse_header(data: bytes) -> Optional[PacketHeader]:
    """Parse the packet header from raw UDP data"""
    if len(data) < 29:
        return None

    header_format = "<HBBBBBQfIIBB"

    try:
        unpacked = struct.unpack(header_format, data[:29])
        return PacketHeader(
            packet_format=unpacked[0],
            game_year=unpacked[1],
            game_major_version=unpacked[2],
            game_minor_version=unpacked[3],
            packet_version=unpacked[4],
            packet_id=unpacked[5],
            session_uid=unpacked[6],
            session_time=unpacked[7],
            frame_identifier=unpacked[8],
            overall_frame_identifier=unpacked[9],
            player_car_index=unpacked[10],
            secondary_player_car_index=unpacked[11],
        )
    except struct.error:
        return None


def parse_car_telemetry(data: bytes, player_index: int) -> Optional[CarTelemetry]:
    """Parse car telemetry data for the player's car"""
    header_size = 29
    total_data = len(data) - header_size

    per_car_size = total_data // 22
    offset = header_size + (player_index * per_car_size)

    if len(data) < offset + 60:
        return None

    car_data = data[offset:offset + 80]

    try:
        # First part: speed through rev_lights_bit (22 bytes)
        # H=2, f=4, f=4, f=4, B=1, b=1, H=2, B=1, B=1, H=2 = 22 bytes
        fmt1 = "<HfffBbHBBH"
        part1 = struct.unpack(fmt1, car_data[:22])

        speed = part1[0]
        throttle = part1[1]
        steer = part1[2]
        brake = part1[3]
        clutch = part1[4]
        gear = part1[5]
        engine_rpm = part1[6]
        drs = part1[7]
        rev_lights_percent = part1[8]
        rev_lights_bit = part1[9]

        # Brake temps: 4 x u16 (8 bytes) at offset 22
        brake_temps = struct.unpack("<4H", car_data[22:30])

        # Tyre surface temps: 4 x u8 (4 bytes) at offset 30
        tyre_surface_temps = struct.unpack("<4B", car_data[30:34])

        # Tyre inner temps: 4 x u8 (4 bytes) at offset 34
        tyre_inner_temps = struct.unpack("<4B", car_data[34:38])

        # Engine temp: u16 (2 bytes) at offset 38
        engine_temp = struct.unpack("<H", car_data[38:40])[0]

        # Tyre pressures: 4 x f32 (16 bytes) at offset 40
        tyre_pressures = struct.unpack("<4f", car_data[40:56])

        # Surface types: 4 x u8 (4 bytes) at offset 56
        surface_types = struct.unpack("<4B", car_data[56:60])

        return CarTelemetry(
            speed=speed,
            throttle=throttle,
            steer=steer,
            brake=brake,
            clutch=clutch,
            gear=gear,
            engine_rpm=engine_rpm,
            drs=drs,
            rev_lights_percent=rev_lights_percent,
            rev_lights_bit=rev_lights_bit,
            brake_temps=brake_temps,
            tyre_surface_temps=tyre_surface_temps,
            tyre_inner_temps=tyre_inner_temps,
            engine_temp=engine_temp,
            tyre_pressures=tyre_pressures,
            surface_types=surface_types,
        )
    except struct.error:
        return None


def find_arduino_port() -> Optional[str]:
    """Auto-detect Arduino serial port. Checks ARDUINO_PORT env var first."""
    # Check environment variable first
    env_port = os.environ.get("ARDUINO_PORT")
    if env_port:
        return env_port

    ports = serial.tools.list_ports.comports()

    for port in ports:
        # Common Arduino identifiers
        if "Arduino" in port.description or "usbmodem" in port.device or "ttyACM" in port.device:
            return port.device

    # Return first available if no Arduino found
    if ports:
        return ports[0].device

    return None


def list_ports():
    """List all available serial ports"""
    ports = serial.tools.list_ports.comports()
    if not ports:
        print("No serial ports found")
        return

    print("Available serial ports:")
    for port in ports:
        print(f"  {port.device} - {port.description}")


def flash_firmware(port: Optional[str] = None) -> str:
    """Compile and upload firmware to Arduino. Returns the port used."""
    print("Flashing firmware...")

    # Check arduino-cli is available
    try:
        subprocess.run(["arduino-cli", "version"], capture_output=True, check=True)
    except FileNotFoundError:
        print("Error: arduino-cli not found. Install it from https://arduino.github.io/arduino-cli/")
        sys.exit(1)

    # Auto-detect port if not specified
    if not port:
        # Check env var
        port = os.environ.get("ARDUINO_PORT")

    if not port:
        # Try arduino-cli board list
        result = subprocess.run(
            ["arduino-cli", "board", "list"],
            capture_output=True,
            text=True
        )
        print("Detected boards:")
        print(result.stdout)
        for line in result.stdout.splitlines():
            if "arduino" in line.lower():
                port = line.split()[0]
                break

    if not port:
        print("Error: No Arduino board found.")
        print("\nTo find your port manually:")
        print("  macOS:   ls /dev/cu.usbmodem*")
        print("  Linux:   ls /dev/ttyACM* /dev/ttyUSB*")
        print("\nThen run with: uv run src/f1_to_serial.py -p <port> --flash")
        print("Or set:        export ARDUINO_PORT=<port>")
        sys.exit(1)

    print(f"  Board: {ARDUINO_FQBN}")
    print(f"  Port: {port}")
    print(f"  Sketch: {FIRMWARE_DIR}")

    # Compile
    print("\nCompiling...")
    result = subprocess.run(
        ["arduino-cli", "compile", "--fqbn", ARDUINO_FQBN, str(FIRMWARE_DIR)],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"Compile failed:\n{result.stderr}")
        sys.exit(1)
    print("  Compile OK")

    # Upload
    print("Uploading...")
    result = subprocess.run(
        ["arduino-cli", "upload", "-p", port, "--fqbn", ARDUINO_FQBN, str(FIRMWARE_DIR)],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"Upload failed:\n{result.stderr}")
        print("\nTroubleshooting:")
        print("  1. Try pressing the reset button on Arduino")
        print("  2. Unplug and replug the USB cable")
        print("  3. Check if another program is using the port (e.g., Serial Monitor)")
        print(f"  4. Verify port exists: ls {port}")
        print(f"  5. Try a different port: uv run src/f1_to_serial.py --list")
        sys.exit(1)
    print("  Upload OK")

    return port


def format_gear(gear: int) -> str:
    if gear == -1:
        return "R"
    elif gear == 0:
        return "N"
    return str(gear)


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def move_cursor_home():
    sys.stdout.write('\033[H')
    sys.stdout.flush()


def draw_bar(value: float, width: int = 20, fill: str = "█", empty: str = "░") -> str:
    filled = int(value * width)
    return fill * filled + empty * (width - filled)


def main():
    parser = argparse.ArgumentParser(description="F1 UDP to Arduino Serial bridge")
    parser.add_argument("--port", "-p", help="Serial port (auto-detect if not specified)")
    parser.add_argument("--baud", "-b", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--udp-port", type=int, default=20777, help="F1 UDP port (default: 20777)")
    parser.add_argument("--list", "-l", action="store_true", help="List available serial ports")
    parser.add_argument("--flash", "-f", action="store_true", help="Flash firmware before starting")
    args = parser.parse_args()

    if args.list:
        list_ports()
        return

    # Flash firmware if requested
    if args.flash:
        flash_port = flash_firmware(args.port)
        # Use the port from flashing if not explicitly specified
        if not args.port:
            args.port = flash_port
        print()  # Blank line after flash output

    # Find serial port
    serial_port = args.port or find_arduino_port()
    if not serial_port:
        print("Error: No serial port found. Use --list to see available ports.")
        sys.exit(1)

    # Open serial connection
    print(f"Opening serial port {serial_port} at {args.baud} baud...")
    try:
        ser = serial.Serial(serial_port, args.baud, timeout=0.1)
    except serial.SerialException as e:
        print(f"Error opening serial port: {e}")
        sys.exit(1)

    # Wait for Arduino to reset
    time.sleep(2)

    # Read any startup message from Arduino
    while ser.in_waiting:
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        if line:
            print(f"Arduino: {line}")

    # Setup UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", args.udp_port))

    clear_screen()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║           F1 to Arduino Serial Bridge                        ║")
    print(f"║  Serial: {serial_port:<20}  UDP: {args.udp_port:<5}               ║")
    print("╠══════════════════════════════════════════════════════════════╣")
    print("║  Waiting for F1 telemetry data...                            ║")
    print("║  Make sure F1 game has UDP telemetry enabled on port 20777   ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print("\nPress Ctrl+C to exit\n")

    try:
        while True:
            data, addr = sock.recvfrom(2048)

            header = parse_header(data)
            if not header:
                continue

            if header.packet_id == PacketId.CAR_TELEMETRY:
                telemetry = parse_car_telemetry(data, header.player_car_index)
                if telemetry:
                    # Convert to RC protocol values (0-255)
                    steer_byte = int((telemetry.steer + 1.0) * 127.5)
                    steer_byte = max(0, min(255, steer_byte))

                    throttle_byte = int(telemetry.throttle * 255)
                    throttle_byte = max(0, min(255, throttle_byte))

                    brake_byte = int(telemetry.brake * 255)
                    brake_byte = max(0, min(255, brake_byte))

                    # Send to Arduino
                    cmd = f"RC:{steer_byte},{throttle_byte},{brake_byte}\n"
                    ser.write(cmd.encode())

                    # Display
                    move_cursor_home()
                    print("╔══════════════════════════════════════════════════════════════╗")
                    print("║              F1 LIVE TELEMETRY → Arduino                     ║")
                    print(f"║  Serial: {serial_port:<20}  UDP: {args.udp_port:<5}               ║")
                    print("╠══════════════════════════════════════════════════════════════╣")

                    gear_str = format_gear(telemetry.gear)
                    drs_str = "DRS" if telemetry.drs else "   "
                    print(f"║  SPEED: {telemetry.speed:3d} km/h    GEAR: {gear_str}    RPM: {telemetry.engine_rpm:5d}    {drs_str}   ║")
                    print("╠══════════════════════════════════════════════════════════════╣")

                    throttle_bar = draw_bar(telemetry.throttle)
                    brake_bar = draw_bar(telemetry.brake)
                    print(f"║  THROTTLE: [{throttle_bar}] {telemetry.throttle*100:5.1f}%         ║")
                    print(f"║  BRAKE:    [{brake_bar}] {telemetry.brake*100:5.1f}%         ║")

                    steer_pos = int((telemetry.steer + 1) * 10)
                    steer_bar = "░" * steer_pos + "█" + "░" * (20 - steer_pos)
                    print(f"║  STEER:    [{steer_bar}] {telemetry.steer:+.2f}          ║")

                    print(f"║  CLUTCH: {telemetry.clutch:3d}%                                              ║")

                    print("╠══════════════════════════════════════════════════════════════╣")
                    print("║  TEMPERATURES                                                ║")
                    print(f"║  Engine: {telemetry.engine_temp:3d}°C                                           ║")
                    print("║                                                              ║")
                    print("║          FRONT                                               ║")
                    print(f"║    FL: {telemetry.tyre_surface_temps[2]:3d}°C    FR: {telemetry.tyre_surface_temps[3]:3d}°C   (Surface)            ║")
                    print(f"║    FL: {telemetry.tyre_inner_temps[2]:3d}°C    FR: {telemetry.tyre_inner_temps[3]:3d}°C   (Inner)              ║")
                    print(f"║    FL: {telemetry.brake_temps[2]:3d}°C    FR: {telemetry.brake_temps[3]:3d}°C   (Brakes)             ║")
                    print("║                                                              ║")
                    print("║          REAR                                                ║")
                    print(f"║    RL: {telemetry.tyre_surface_temps[0]:3d}°C    RR: {telemetry.tyre_surface_temps[1]:3d}°C   (Surface)            ║")
                    print(f"║    RL: {telemetry.tyre_inner_temps[0]:3d}°C    RR: {telemetry.tyre_inner_temps[1]:3d}°C   (Inner)              ║")
                    print(f"║    RL: {telemetry.brake_temps[0]:3d}°C    RR: {telemetry.brake_temps[1]:3d}°C   (Brakes)             ║")

                    print("╠══════════════════════════════════════════════════════════════╣")
                    print("║  TYRE PRESSURES (PSI)                                        ║")
                    print(f"║    FL: {telemetry.tyre_pressures[2]:5.1f}    FR: {telemetry.tyre_pressures[3]:5.1f}                       ║")
                    print(f"║    RL: {telemetry.tyre_pressures[0]:5.1f}    RR: {telemetry.tyre_pressures[1]:5.1f}                       ║")

                    print("╠══════════════════════════════════════════════════════════════╣")
                    print(f"║  Rev Lights: {telemetry.rev_lights_percent:3d}%                                        ║")
                    print("╠══════════════════════════════════════════════════════════════╣")
                    print(f"║  → Arduino: {cmd.strip():<30}                  ║")
                    print("╚══════════════════════════════════════════════════════════════╝")
                    print("\n  Press Ctrl+C to exit")
                    sys.stdout.flush()

    except KeyboardInterrupt:
        print("\n\nStopping...")

    finally:
        ser.close()
        sock.close()


if __name__ == "__main__":
    main()
