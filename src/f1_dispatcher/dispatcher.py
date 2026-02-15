"""F1Dispatcher - Listens for F1 UDP packets and dispatches parsed data to registered handlers."""

import socket
import struct
import threading
from typing import Optional, Callable, Any
from collections import defaultdict

from f1_telemetry.packets import PacketType, PacketHeader
from f1_telemetry.client import (
    parse_header,
    parse_session,
    parse_lap_data,
    parse_car_telemetry,
    parse_car_status,
    parse_car_damage,
    parse_car_motion,
    parse_motion_ex,
    parse_participants,
    parse_car_setup,
    parse_event,
    parse_final_classification,
    parse_lobby_info,
    parse_session_history,
    parse_tyre_sets,
    parse_time_trial,
)


# Maps PacketType to (parse_function, needs_car_index)
_PARSERS: dict[PacketType, tuple[Callable, bool]] = {
    PacketType.MOTION: (parse_car_motion, True),
    PacketType.SESSION: (parse_session, False),
    PacketType.LAP_DATA: (parse_lap_data, True),
    PacketType.EVENT: (parse_event, False),
    PacketType.PARTICIPANTS: (parse_participants, True),
    PacketType.CAR_SETUPS: (parse_car_setup, True),
    PacketType.CAR_TELEMETRY: (parse_car_telemetry, True),
    PacketType.CAR_STATUS: (parse_car_status, True),
    PacketType.FINAL_CLASSIFICATION: (parse_final_classification, True),
    PacketType.LOBBY_INFO: (parse_lobby_info, True),
    PacketType.CAR_DAMAGE: (parse_car_damage, True),
    PacketType.SESSION_HISTORY: (parse_session_history, False),
    PacketType.TYRE_SETS: (parse_tyre_sets, False),
    PacketType.MOTION_EX: (parse_motion_ex, False),
    PacketType.TIME_TRIAL: (parse_time_trial, False),
}


class F1Dispatcher:
    """
    Listens for F1 game UDP telemetry packets and dispatches parsed data
    to registered per-packet-type handlers.

    Usage:
        dispatcher = F1Dispatcher()

        @dispatcher.on(PacketType.CAR_TELEMETRY)
        def handle_telemetry(header, telemetry):
            print(f"Speed: {telemetry.speed} km/h")

        dispatcher.on(PacketType.SESSION, my_session_handler)

        dispatcher.start()
        # ... later ...
        dispatcher.stop()
    """

    def __init__(self, port: int = 20777):
        self.port = port
        self._handlers: dict[PacketType, list[Callable]] = defaultdict(list)
        self._socket: Optional[socket.socket] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def on(self, packet_type: PacketType, handler: Optional[Callable] = None) -> Callable:
        """
        Register a handler for a specific packet type.

        Can be used as a decorator or called directly:
            @dispatcher.on(PacketType.CAR_TELEMETRY)
            def handle(header, data): ...

            dispatcher.on(PacketType.SESSION, my_handler)

        Handlers receive (header: PacketHeader, parsed_data).
        """
        if handler is not None:
            self._handlers[packet_type].append(handler)
            return handler

        # Decorator usage
        def decorator(fn: Callable) -> Callable:
            self._handlers[packet_type].append(fn)
            return fn
        return decorator

    def start(self):
        """Start listening for UDP packets and dispatching."""
        if self._running:
            return

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        self._socket.bind(("", self.port))
        self._socket.settimeout(1.0)

        self._running = True
        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop listening and dispatching."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._socket:
            self._socket.close()
            self._socket = None

    @property
    def is_running(self) -> bool:
        return self._running

    def _listen(self):
        """Main UDP listening loop."""
        while self._running:
            try:
                data, _ = self._socket.recvfrom(4096)
                self._process_packet(data)
            except socket.timeout:
                continue
            except Exception:
                if self._running:
                    continue

    def _process_packet(self, data: bytes):
        """Parse a raw UDP packet and dispatch to registered handlers."""
        header = parse_header(data)
        if not header:
            return

        packet_type = header.packet_type
        if packet_type not in _PARSERS:
            return

        handlers = self._handlers.get(packet_type)
        if not handlers:
            return

        parse_fn, needs_car_index = _PARSERS[packet_type]

        if needs_car_index:
            parsed = parse_fn(data, header.player_car_index)
        else:
            parsed = parse_fn(data)

        if parsed is None:
            return

        for handler in handlers:
            try:
                handler(header, parsed)
            except Exception:
                pass
