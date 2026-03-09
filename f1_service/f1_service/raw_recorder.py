"""Raw UDP Recorder — captures all F1 UDP packets to .f1raw binary files."""

import struct
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# .f1raw binary format
# File header (16 bytes):
#   magic       4B  b"F1RW"
#   version     1B  uint8 (1)
#   reserved    3B  padding
#   start_time  8B  uint64 wall-clock epoch µs
#
# Per-packet record (10 + N bytes):
#   delta_us    8B  uint64 µs since previous packet
#   length      2B  uint16 packet byte count
#   raw_bytes   NB  raw UDP payload

MAGIC = b"F1RW"
FORMAT_VERSION = 1
FILE_HEADER_STRUCT = struct.Struct("<4s B 3x Q")  # 16 bytes
RECORD_HEADER_STRUCT = struct.Struct("<Q H")  # 10 bytes


class RawRecorder:
    """Records all raw UDP packets to a .f1raw binary file.

    Usage:
        recorder = RawRecorder(captures_dir="captures")
        recorder.register(dispatcher)
        # ... run dispatcher ...
        recorder.close()
    """

    def __init__(self, captures_dir: str = "captures"):
        self._captures_dir = Path(captures_dir)
        self._file = None
        self._packet_count = 0
        self._total_bytes = 0
        self._last_time: Optional[float] = None
        self._start_time: Optional[float] = None
        self._filepath: Optional[Path] = None

    def register(self, dispatcher) -> None:
        """Register as a raw handler on an F1Dispatcher."""
        dispatcher.on_raw(self._handle_raw)

    def _handle_raw(self, raw_bytes: bytes) -> None:
        """Write one raw packet record, opening the file lazily on first packet."""
        now = time.monotonic()

        if self._file is None:
            self._open_file()
            self._start_time = now
            self._last_time = now
            delta_us = 0
        else:
            delta_us = int((now - self._last_time) * 1_000_000)
            self._last_time = now

        record_header = RECORD_HEADER_STRUCT.pack(delta_us, len(raw_bytes))
        self._file.write(record_header)
        self._file.write(raw_bytes)

        self._packet_count += 1
        self._total_bytes += len(raw_bytes)

    def _open_file(self) -> None:
        """Create the output file and write the file header."""
        self._captures_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._filepath = self._captures_dir / f"{ts}.f1raw"

        wall_us = int(time.time() * 1_000_000)
        file_header = FILE_HEADER_STRUCT.pack(MAGIC, FORMAT_VERSION, wall_us)

        self._file = open(self._filepath, "wb")
        self._file.write(file_header)
        print(f"[RawRecorder] Recording to {self._filepath}")

    def close(self) -> None:
        """Flush, close the file, and print a summary."""
        if self._file is None:
            return

        self._file.flush()
        self._file.close()

        duration_s = 0.0
        if self._start_time is not None and self._last_time is not None:
            duration_s = self._last_time - self._start_time

        file_size = self._filepath.stat().st_size
        size_mb = file_size / (1024 * 1024)
        mins = int(duration_s) // 60
        secs = duration_s % 60

        print(
            f"[RawRecorder] Saved {self._packet_count} packets "
            f"({size_mb:.1f} MB, {mins}m{secs:04.1f}s) → {self._filepath.name}"
        )

        self._file = None
