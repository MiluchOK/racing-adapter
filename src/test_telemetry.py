#!/usr/bin/env python3
"""Simple test script to detect F1 telemetry data on port 20777."""

import socket

PORT = 20777

print(f"Listening for F1 telemetry on port {PORT}...")
print("Start your F1 game and get on track.")
print("Press Ctrl+C to stop.\n")

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
sock.bind(("", PORT))

packet_count = 0
try:
    while True:
        data, addr = sock.recvfrom(2048)
        packet_count += 1
        if packet_count == 1:
            print(f"DATA DETECTED! First packet from {addr}")
            print(f"Packet size: {len(data)} bytes")
        if packet_count % 100 == 0:
            print(f"Received {packet_count} packets...")
except KeyboardInterrupt:
    print(f"\n\nTotal packets received: {packet_count}")
finally:
    sock.close()
