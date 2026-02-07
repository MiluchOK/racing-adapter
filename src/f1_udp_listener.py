#!/usr/bin/env python3
"""
F1 UDP Telemetry Listener

Uses the f1_telemetry client library for clean data access.

Usage:
  uv run src/f1_udp_listener.py          # Live telemetry display
  uv run src/f1_udp_listener.py --raw    # Raw packet dump for analysis
"""

import sys
import os
import time
import argparse
from collections import defaultdict

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from f1_telemetry import F1TelemetryClient
from f1_telemetry.packets import PacketType


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def live_display():
    """Show live telemetry using the client library."""
    client = F1TelemetryClient()
    client.start()

    clear_screen()
    print("=" * 70)
    print("  F1 TELEMETRY - LIVE")
    print("=" * 70)
    print("  Listening on port 20777...")
    print("  Start your F1 game and get on track.")
    print("=" * 70)
    print("\n  Waiting for data...")

    try:
        last_update = 0
        while True:
            if client.is_connected():
                # Update display ~10 times per second
                if time.time() - last_update > 0.1:
                    last_update = time.time()
                    d = client.data

                    clear_screen()
                    print("=" * 70)
                    print("  F1 TELEMETRY - LIVE")
                    print(f"  Game: F1 {d.header.packet_format} | Session: {d.header.session_time:.1f}s")
                    print("=" * 70)

                    # Session info
                    if d.session:
                        print(f"\n  TRACK: {d.track}")
                        print(f"  Weather: {d.weather} | Air: {d.session.air_temperature}°C | Track: {d.session.track_temperature}°C")
                        print(f"  Session: {d.session.session_type_name}")

                    # Lap info
                    if d.lap:
                        print(f"\n  LAP: {d.current_lap} | Position: P{d.position}")
                        print(f"  Current: {d.lap_time} | Last: {d.last_lap}")
                        print(f"  Sector: {d.lap.sector_number} | Distance: {d.lap.lap_distance:.0f}m")

                    # Telemetry
                    if d.telemetry:
                        print(f"\n  SPEED: {d.speed:3d} km/h | GEAR: {d.gear} | RPM: {d.rpm:5d}")

                        # Throttle bar
                        throttle_bar = "█" * int(d.throttle / 5) + "░" * (20 - int(d.throttle / 5))
                        print(f"  Throttle: [{throttle_bar}] {d.throttle:5.1f}%")

                        # Brake bar
                        brake_bar = "█" * int(d.brake / 5) + "░" * (20 - int(d.brake / 5))
                        print(f"  Brake:    [{brake_bar}] {d.brake:5.1f}%")

                        # Steering
                        steer = d.telemetry.steer
                        steer_pos = int((steer + 1) * 10)
                        steer_bar = "░" * steer_pos + "█" + "░" * (20 - steer_pos)
                        print(f"  Steering: [{steer_bar}] {steer:+.2f}")

                        print(f"  DRS: {'ACTIVE' if d.drs else 'Off'}")

                    # Car status
                    if d.status:
                        print(f"\n  TYRES: {d.tyre_compound} ({d.tyre_age} laps)")
                        print(f"  Fuel: {d.fuel:.1f} kg ({d.fuel_laps:.1f} laps)")
                        print(f"  ERS: {d.ers_percent:.0f}%")

                    # Temperatures
                    if d.telemetry:
                        t = d.telemetry
                        print(f"\n  TEMPS:")
                        print(f"    Engine: {t.engine_temperature}°C")
                        print(f"    Tyres (surface): FL:{t.tyre_surface_temperature.front_left}° FR:{t.tyre_surface_temperature.front_right}° "
                              f"RL:{t.tyre_surface_temperature.rear_left}° RR:{t.tyre_surface_temperature.rear_right}°")
                        print(f"    Brakes: FL:{t.brake_temperature.front_left}° FR:{t.brake_temperature.front_right}° "
                              f"RL:{t.brake_temperature.rear_left}° RR:{t.brake_temperature.rear_right}°")

                    # Damage
                    if d.damage and d.damage.has_damage:
                        print(f"\n  DAMAGE:")
                        if d.damage.front_left_wing_damage > 0:
                            print(f"    Front Left Wing: {d.damage.front_left_wing_damage}%")
                        if d.damage.front_right_wing_damage > 0:
                            print(f"    Front Right Wing: {d.damage.front_right_wing_damage}%")
                        if d.damage.rear_wing_damage > 0:
                            print(f"    Rear Wing: {d.damage.rear_wing_damage}%")

                    print("\n" + "=" * 70)
                    print("  Press Ctrl+C to exit")

            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\n\nStopping...")
        client.stop()


def raw_dump():
    """Dump raw packets for analysis."""
    import socket
    import struct

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    sock.bind(("", 20777))

    print("=" * 70)
    print("  F1 RAW PACKET DUMP")
    print("=" * 70)
    print("  Collecting raw packets for analysis...")
    print("  Press Ctrl+C to stop and show summary.\n")

    packet_sizes = defaultdict(set)
    packet_samples = {}
    packet_counts = defaultdict(int)

    try:
        while True:
            data, _ = sock.recvfrom(4096)

            if len(data) < 29:
                continue

            # Parse header
            header = struct.unpack("<HBBBBBQfIIBB", data[:29])
            packet_id = header[5]
            packet_counts[packet_id] += 1
            packet_sizes[packet_id].add(len(data))

            # Store first sample of each type
            if packet_id not in packet_samples:
                packet_samples[packet_id] = data
                print(f"  Captured packet type {packet_id}: {len(data)} bytes")

            # Show progress
            total = sum(packet_counts.values())
            if total % 100 == 0:
                print(f"  Total packets: {total}", end="\r")

    except KeyboardInterrupt:
        print("\n\n" + "=" * 70)
        print("  PACKET ANALYSIS SUMMARY")
        print("=" * 70)

        packet_names = {
            0: "MOTION", 1: "SESSION", 2: "LAP_DATA", 3: "EVENT",
            4: "PARTICIPANTS", 5: "CAR_SETUPS", 6: "CAR_TELEMETRY",
            7: "CAR_STATUS", 8: "FINAL_CLASSIFICATION", 9: "LOBBY_INFO",
            10: "CAR_DAMAGE", 11: "SESSION_HISTORY", 12: "TYRE_SETS",
            13: "MOTION_EX", 14: "TIME_TRIAL",
        }

        for pid in sorted(packet_sizes.keys()):
            name = packet_names.get(pid, f"UNKNOWN_{pid}")
            sizes = packet_sizes[pid]
            count = packet_counts[pid]
            print(f"\n  {name} (type {pid}):")
            print(f"    Count: {count}")
            print(f"    Sizes: {sorted(sizes)}")

            if pid in packet_samples:
                sample = packet_samples[pid]
                print(f"    Header (29 bytes):")
                print(f"      Raw: {sample[:29].hex()}")

                # Calculate per-car data size
                data_size = len(sample) - 29
                if data_size > 0:
                    print(f"    Data ({data_size} bytes):")
                    # If divisible by 22 (cars), show per-car size
                    if data_size % 22 == 0:
                        per_car = data_size // 22
                        print(f"      Per car: {per_car} bytes (22 cars)")
                    # Show first 100 bytes of data
                    print(f"      First 100 bytes: {sample[29:129].hex()}")

        # Save raw samples to files
        print("\n  Saving raw samples to f1_packets/...")
        os.makedirs("f1_packets", exist_ok=True)
        for pid, sample in packet_samples.items():
            name = packet_names.get(pid, f"unknown_{pid}")
            with open(f"f1_packets/{name.lower()}.bin", "wb") as f:
                f.write(sample)
            with open(f"f1_packets/{name.lower()}.hex", "w") as f:
                # Write header
                f.write(f"Packet Type: {name} ({pid})\n")
                f.write(f"Total Size: {len(sample)} bytes\n")
                f.write(f"Header Size: 29 bytes\n")
                f.write(f"Data Size: {len(sample) - 29} bytes\n\n")

                # Write hex dump
                f.write("Header:\n")
                f.write(f"  {sample[:29].hex()}\n\n")

                f.write("Data (hex):\n")
                for i in range(29, len(sample), 32):
                    chunk = sample[i:i+32]
                    hex_str = chunk.hex()
                    # Add spaces every 2 chars
                    spaced = ' '.join(hex_str[j:j+2] for j in range(0, len(hex_str), 2))
                    f.write(f"  {i:04d}: {spaced}\n")

        print("  Done!")
        print("=" * 70)

    finally:
        sock.close()


def main():
    parser = argparse.ArgumentParser(description="F1 UDP Telemetry Listener")
    parser.add_argument("--raw", action="store_true", help="Raw packet dump mode")
    args = parser.parse_args()

    if args.raw:
        raw_dump()
    else:
        live_display()


if __name__ == "__main__":
    main()
