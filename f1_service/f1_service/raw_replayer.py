"""Raw UDP Replayer — re-sends captured .f1raw files as UDP packets."""

import socket
import struct
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from .packets import PacketType

from .raw_recorder import MAGIC, FORMAT_VERSION, FILE_HEADER_STRUCT, RECORD_HEADER_STRUCT

# Packet type byte is at offset 5 in the F1 UDP header
_PACKET_TYPE_OFFSET = 5


@dataclass
class FileInfo:
    """Metadata about a .f1raw capture file."""
    path: Path
    packet_count: int
    duration_s: float
    file_size: int
    packet_types: dict[str, int]  # type_name -> count


def file_info(path: str | Path) -> FileInfo:
    """Quick metadata scan of a .f1raw file."""
    path = Path(path)
    data = path.read_bytes()

    if len(data) < FILE_HEADER_STRUCT.size:
        raise ValueError(f"File too small: {len(data)} bytes")

    magic, version, _ = FILE_HEADER_STRUCT.unpack(data[:FILE_HEADER_STRUCT.size])
    if magic != MAGIC:
        raise ValueError(f"Bad magic: {magic!r} (expected {MAGIC!r})")
    if version != FORMAT_VERSION:
        raise ValueError(f"Unknown version: {version}")

    offset = FILE_HEADER_STRUCT.size
    packet_count = 0
    total_delta_us = 0
    type_counts: dict[str, int] = {}

    while offset + RECORD_HEADER_STRUCT.size <= len(data):
        delta_us, length = RECORD_HEADER_STRUCT.unpack_from(data, offset)
        offset += RECORD_HEADER_STRUCT.size

        if offset + length > len(data):
            break

        total_delta_us += delta_us
        packet_count += 1

        # Extract packet type from raw payload
        if length > _PACKET_TYPE_OFFSET:
            type_id = data[offset + _PACKET_TYPE_OFFSET]
            try:
                name = PacketType(type_id).name
            except ValueError:
                name = f"UNKNOWN({type_id})"
            type_counts[name] = type_counts.get(name, 0) + 1

        offset += length

    return FileInfo(
        path=path,
        packet_count=packet_count,
        duration_s=total_delta_us / 1_000_000,
        file_size=path.stat().st_size,
        packet_types=type_counts,
    )


def replay(
    path: str | Path,
    host: str = "127.0.0.1",
    port: int = 20777,
    speed: float = 1.0,
    loop: bool = False,
    callback: Optional[Callable[[int, int], None]] = None,
) -> None:
    """Replay a .f1raw capture file by sending packets via UDP.

    Args:
        path: Path to the .f1raw file.
        host: Destination host.
        port: Destination UDP port.
        speed: Playback speed multiplier (2.0 = double speed, 0 = no delay).
        loop: If True, replay continuously until interrupted.
        callback: Called with (packets_sent, total_packets) for progress reporting.
    """
    path = Path(path)
    data = path.read_bytes()

    if len(data) < FILE_HEADER_STRUCT.size:
        raise ValueError(f"File too small: {len(data)} bytes")

    magic, version, _ = FILE_HEADER_STRUCT.unpack(data[:FILE_HEADER_STRUCT.size])
    if magic != MAGIC:
        raise ValueError(f"Bad magic: {magic!r}")
    if version != FORMAT_VERSION:
        raise ValueError(f"Unknown version: {version}")

    # Pre-load all records into memory
    records: list[tuple[int, bytes]] = []  # (delta_us, payload)
    offset = FILE_HEADER_STRUCT.size

    while offset + RECORD_HEADER_STRUCT.size <= len(data):
        delta_us, length = RECORD_HEADER_STRUCT.unpack_from(data, offset)
        offset += RECORD_HEADER_STRUCT.size

        if offset + length > len(data):
            break

        payload = data[offset:offset + length]
        records.append((delta_us, payload))
        offset += length

    if not records:
        raise ValueError("No packets found in file")

    total = len(records)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        while True:
            for i, (delta_us, payload) in enumerate(records):
                if delta_us > 0 and speed > 0:
                    time.sleep(delta_us / 1_000_000 / speed)

                sock.sendto(payload, (host, port))

                if callback:
                    callback(i + 1, total)

            if not loop:
                break
    finally:
        sock.close()
