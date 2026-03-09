"""Lap Recorder - records per-lap telemetry to compact .f1lap binary files."""

import logging
import struct
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("f1_service.lap_recorder")

from .packets import (
    PacketType, Track, Weather, SessionType, Team, TyreCompound,
)

# Binary format constants
MAGIC = b"F1LP"
FORMAT_VERSION = 2

# V1 header (84 bytes) — kept for reader backward compat
HEADER_V1_STRUCT = struct.Struct("<4s B B B B B B B B B Q I H H H 48s I")
HEADER_V1_SIZE = HEADER_V1_STRUCT.size

# V2 header adds 10 assist bytes after num_samples (94 bytes)
# Assists: steering_assist, braking_assist, gearbox_assist, pit_assist,
#          pit_release_assist, ers_assist, drs_assist, dynamic_racing_line,
#          traction_control, anti_lock_brakes
HEADER_STRUCT = struct.Struct("<4s B B B B B B B B B Q I H H H 48s I 10B")
HEADER_SIZE = HEADER_STRUCT.size

# Per-sample struct: 4 + 58 + 31 + 48 + 188 + 33 + 40 = 402 bytes
SAMPLE_STRUCT = struct.Struct(
    "<"
    # session_time (4B)
    "f"
    # CAR_TELEMETRY (58B)
    "H f f f B b H B B"   # speed, throttle, steer, brake, clutch, gear, rpm, drs, rev_lights
    "4H"                   # brake_temp (RL,RR,FL,FR)
    "4B"                   # tyre_surface_temp
    "4B"                   # tyre_inner_temp
    "H"                    # engine_temperature
    "4f"                   # tyre_pressure
    "4B"                   # surface_type
    # LAP_DATA (31B)
    "I H H"                # current_lap_time_ms, sector1_time_ms, sector2_time_ms
    "f f f"                # lap_distance, total_distance, safety_car_delta
    "B B B B B"            # position, current_lap, pit_status, sector, current_lap_invalid
    "H H"                  # delta_car_in_front_ms, delta_race_leader_ms
    "B B"                  # driver_status, result_status
    # MOTION (48B)
    "3f"                   # world_position (x,y,z)
    "3f"                   # world_velocity (x,y,z)
    "3f"                   # g_force (lat,lon,vert)
    "3f"                   # yaw, pitch, roll
    # MOTION_EX (188B)
    "4f"                   # suspension_position
    "4f"                   # suspension_velocity
    "4f"                   # suspension_accel
    "4f"                   # wheel_speed
    "4f"                   # wheel_slip_ratio
    "4f"                   # wheel_slip_angle
    "4f"                   # wheel_lat_force
    "4f"                   # wheel_long_force
    "f"                    # height_of_cog
    "3f"                   # local_velocity
    "3f"                   # angular_velocity
    "3f"                   # angular_accel
    "f"                    # front_wheels_angle
    "4f"                   # wheel_vert_force
    # CAR_STATUS (33B)
    "B B"                  # fuel_mix, front_brake_bias
    "f f"                  # fuel_remaining, fuel_remaining_laps
    "B H"                  # drs_allowed, drs_activation_distance
    "B B B"                # actual_tyre_compound, tyre_age_laps, vehicle_flag
    "f"                    # ers_store_energy
    "B"                    # ers_deploy_mode
    "f f f"                # ers_harvested_mguk, ers_harvested_mguh, ers_deployed_this_lap
    # CAR_DAMAGE (40B)
    "4f"                   # tyre_wear
    "4B"                   # tyre_damage
    "4B"                   # brakes_damage
    "B B B B B B"          # fl_wing, fr_wing, rear_wing, floor, diffuser, sidepod
    "B B"                  # drs_fault, ers_fault
    "B B"                  # gearbox_damage, engine_damage
    "B B B B B B"          # mguh, es, ce, ice, mguk, tc wear
)
SAMPLE_SIZE = SAMPLE_STRUCT.size

FLUSH_INTERVAL = 5.0  # seconds between flushes


def _tyre4(td):
    """Extract (RL, RR, FL, FR) tuple from a TyreData object."""
    return (td.rear_left, td.rear_right, td.front_left, td.front_right)


class LapRecorder:
    """Records per-lap telemetry to .f1lap binary files.

    Files are written directly to the laps directory (no sub-folders).
    Filename: <timestamp>_lap<N>.f1lap

    Streams samples to disk as they arrive. Flushes every 5 seconds.
    The header (with sample count and lap time) is rewritten when the lap ends.
    """

    def __init__(self, laps_dir: str = "laps"):
        self._base_dir = Path(laps_dir)

        # Session-level metadata (from SESSION / PARTICIPANTS packets)
        self._game_year: int = 0
        self._track: Optional[Track] = None
        self._session_type: Optional[SessionType] = None
        self._weather: Optional[Weather] = None
        self._session_uid: int = 0
        self._driver_name: str = ""
        self._team: int = 0
        self._tyre_compound: int = 0

        # Assist flags (from SESSION + CAR_STATUS packets)
        self._steering_assist: int = 0
        self._braking_assist: int = 0
        self._gearbox_assist: int = 0
        self._pit_assist: int = 0
        self._pit_release_assist: int = 0
        self._ers_assist: int = 0
        self._drs_assist: int = 0
        self._dynamic_racing_line: int = 0
        self._traction_control: int = 0
        self._anti_lock_brakes: int = 0

        # Per-lap sector cache from SESSION_HISTORY {lap_num: (s1, s2, s3)}
        self._lap_sectors: dict[int, tuple[int, int, int]] = {}

        # Latest cached packet data (carried forward into each sample)
        self._lap_data = None
        self._motion = None
        self._motion_ex = None
        self._car_status = None
        self._car_damage = None

        # Current lap streaming state
        self._lap_number: int = 0
        self._lap_valid: bool = True
        self._lap_file = None
        self._lap_filepath: Optional[Path] = None
        self._sample_count: int = 0
        self._recording = False
        self._session_ts: str = ""  # timestamp for filenames in this session
        self._last_flush: float = 0.0

    def register(self, dispatcher):
        """Register handlers on an F1Dispatcher instance."""
        dispatcher.on(PacketType.SESSION, self._handle_session)
        dispatcher.on(PacketType.PARTICIPANTS, self._handle_participants)
        dispatcher.on(PacketType.CAR_TELEMETRY, self._handle_car_telemetry)
        dispatcher.on(PacketType.LAP_DATA, self._handle_lap_data)
        dispatcher.on(PacketType.MOTION, self._handle_motion)
        dispatcher.on(PacketType.MOTION_EX, self._handle_motion_ex)
        dispatcher.on(PacketType.CAR_STATUS, self._handle_car_status)
        dispatcher.on(PacketType.CAR_DAMAGE, self._handle_car_damage)
        dispatcher.on(PacketType.SESSION_HISTORY, self._handle_session_history)
        dispatcher.on(PacketType.EVENT, self._handle_event)

    # ── packet handlers ──────────────────────────────────────────────

    def _handle_session(self, header, data):
        self._track = data.track
        self._weather = data.weather
        self._session_type = data.session_type
        self._game_year = header.game_year
        self._session_uid = header.session_uid
        # Cache assist flags from session data
        self._steering_assist = int(data.steering_assist)
        self._braking_assist = data.braking_assist
        self._gearbox_assist = data.gearbox_assist
        self._pit_assist = int(data.pit_assist)
        self._pit_release_assist = int(data.pit_release_assist)
        self._ers_assist = int(data.ers_assist)
        self._drs_assist = int(data.drs_assist)
        self._dynamic_racing_line = data.dynamic_racing_line

    def _handle_participants(self, header, data):
        self._driver_name = data.name
        self._team = int(data.team) if isinstance(data.team, Team) else data.team

    def _handle_car_status(self, header, data):
        self._car_status = data
        self._tyre_compound = (
            int(data.actual_tyre_compound)
            if isinstance(data.actual_tyre_compound, TyreCompound)
            else data.actual_tyre_compound
        )
        self._traction_control = data.traction_control
        self._anti_lock_brakes = int(data.anti_lock_brakes)

    def _handle_car_damage(self, header, data):
        self._car_damage = data

    def _handle_motion(self, header, data):
        self._motion = data

    def _handle_motion_ex(self, header, data):
        self._motion_ex = data

    def _handle_session_history(self, header, data):
        if data.car_index != header.player_car_index:
            return
        for i, lap in enumerate(data.lap_history):
            if lap.lap_time_ms > 0:
                self._lap_sectors[i + 1] = (
                    lap.sector1_time_ms,
                    lap.sector2_time_ms,
                    lap.sector3_time_ms,
                )

    def _handle_lap_data(self, header, data):
        prev_lap_num = self._lap_number

        # Detect lap boundary
        if data.current_lap != prev_lap_num and prev_lap_num > 0:
            self._finalize_lap()

        self._lap_number = data.current_lap
        if data.current_lap_invalid:
            self._lap_valid = False
        self._lap_data = data

    def _handle_car_telemetry(self, header, data):
        """Trigger: pack and stream one sample to disk."""
        self._ensure_recording()
        self._ensure_lap_file()

        sample = self._pack_sample(header.session_time, data)
        if sample and self._lap_file:
            self._lap_file.write(sample)
            self._sample_count += 1

            now = time.monotonic()
            if now - self._last_flush >= FLUSH_INTERVAL:
                self._lap_file.flush()
                self._last_flush = now

    def _handle_event(self, header, data):
        if data.event_code == "SSTA":
            self._start_session()
        elif data.event_code == "SEND":
            self._end_session()

    # ── session lifecycle ────────────────────────────────────────────

    def _ensure_recording(self):
        """Start recording lazily on first telemetry packet."""
        if self._recording:
            return
        self._start_session()

    def _start_session(self):
        # Finalize any in-progress lap from a previous session
        self._finalize_lap()

        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._session_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._lap_sectors.clear()
        self._recording = True
        print(f"[LapRecorder] Recording to {self._base_dir}/")

    def _end_session(self):
        self._finalize_lap()
        self._recording = False
        print("[LapRecorder] Session ended")

    def close(self):
        """Finalize any in-progress lap file (call on shutdown)."""
        self._finalize_lap()

    # ── per-lap file streaming ───────────────────────────────────────

    def _ensure_lap_file(self):
        """Open a new lap file if one isn't open yet."""
        if self._lap_file is not None:
            return

        lap_num = self._lap_number if self._lap_number > 0 else 1
        self._lap_filepath = self._base_dir / f"{self._session_ts}_lap{lap_num:03d}.f1lap"

        # Write a placeholder header — will be rewritten in _finalize_lap
        self._lap_file = open(self._lap_filepath, "wb")
        self._lap_file.write(self._pack_header(lap_num, 0, (0, 0, 0)))
        self._lap_file.flush()
        self._last_flush = time.monotonic()
        self._sample_count = 0
        self._lap_valid = True

    def _finalize_lap(self):
        """Close the current lap file and rewrite the header with final metadata."""
        if self._lap_file is None:
            return

        self._lap_file.close()

        lap_num = self._lap_number if self._lap_number > 0 else 1
        sectors = self._lap_sectors.get(lap_num, (0, 0, 0))

        # Compute lap time
        lap_time_ms = 0
        if all(s > 0 for s in sectors):
            lap_time_ms = sum(sectors)
        elif self._lap_data and self._lap_data.last_lap_time_ms > 0:
            lap_time_ms = self._lap_data.last_lap_time_ms

        # Rewrite the header in place with final sample count, lap time, sectors
        with open(self._lap_filepath, "r+b") as f:
            f.write(self._pack_header(lap_num, lap_time_ms, sectors))

        size_kb = (HEADER_SIZE + self._sample_count * SAMPLE_SIZE) / 1024
        print(f"[LapRecorder] Lap {lap_num} done ({self._sample_count} samples, {size_kb:.0f} KB) → {self._lap_filepath.name}")

        self._lap_file = None
        self._lap_filepath = None
        self._sample_count = 0

    def _pack_header(self, lap_num: int, lap_time_ms: int, sectors: tuple) -> bytes:
        """Pack the .f1lap file header."""
        driver_bytes = self._driver_name.encode("utf-8")[:48].ljust(48, b"\x00")
        return HEADER_STRUCT.pack(
            MAGIC,
            FORMAT_VERSION,
            self._game_year,
            int(self._track) if self._track is not None else 0,
            int(self._session_type) if self._session_type is not None else 0,
            int(self._weather) if self._weather is not None else 0,
            lap_num,
            1 if self._lap_valid else 0,
            self._team,
            self._tyre_compound,
            self._session_uid,
            lap_time_ms,
            sectors[0],
            sectors[1],
            sectors[2],
            driver_bytes,
            self._sample_count,
            # V2 assist flags
            self._steering_assist,
            self._braking_assist,
            self._gearbox_assist,
            self._pit_assist,
            self._pit_release_assist,
            self._ers_assist,
            self._drs_assist,
            self._dynamic_racing_line,
            self._traction_control,
            self._anti_lock_brakes,
        )

    # ── sample packing ───────────────────────────────────────────────

    def _pack_sample(self, session_time: float, tel) -> Optional[bytes]:
        """Pack one telemetry sample from all cached packet data."""
        ld = self._lap_data
        mo = self._motion
        mx = self._motion_ex
        cs = self._car_status
        cd = self._car_damage

        # We need at least telemetry (the trigger) — others get zero-filled defaults
        try:
            return SAMPLE_STRUCT.pack(
                # session_time
                session_time,
                # CAR_TELEMETRY
                tel.speed,
                tel.throttle,
                tel.steer,
                tel.brake,
                tel.clutch,
                tel.gear,
                tel.engine_rpm,
                1 if tel.drs else 0,
                tel.rev_lights_percent,
                *_tyre4(tel.brake_temperature),
                *_tyre4(tel.tyre_surface_temperature),
                *_tyre4(tel.tyre_inner_temperature),
                tel.engine_temperature,
                *_tyre4(tel.tyre_pressure),
                *tel.surface_type,
                # LAP_DATA
                ld.current_lap_time_ms if ld else 0,
                ld.sector1_time_ms if ld else 0,
                ld.sector2_time_ms if ld else 0,
                ld.lap_distance if ld else 0.0,
                ld.total_distance if ld else 0.0,
                ld.safety_car_delta if ld else 0.0,
                ld.position if ld else 0,
                ld.current_lap if ld else 0,
                int(ld.pit_status) if ld else 0,
                ld.sector if ld else 0,
                1 if (ld and ld.current_lap_invalid) else 0,
                ld.delta_to_car_in_front_ms if ld else 0,
                ld.delta_to_race_leader_ms if ld else 0,
                ld.driver_status if ld else 0,
                ld.result_status if ld else 0,
                # MOTION
                mo.world_position.x if mo else 0.0,
                mo.world_position.y if mo else 0.0,
                mo.world_position.z if mo else 0.0,
                mo.world_velocity.x if mo else 0.0,
                mo.world_velocity.y if mo else 0.0,
                mo.world_velocity.z if mo else 0.0,
                mo.g_force_lateral if mo else 0.0,
                mo.g_force_longitudinal if mo else 0.0,
                mo.g_force_vertical if mo else 0.0,
                mo.yaw if mo else 0.0,
                mo.pitch if mo else 0.0,
                mo.roll if mo else 0.0,
                # MOTION_EX
                *(_tyre4(mx.suspension_position) if mx else (0.0,) * 4),
                *(_tyre4(mx.suspension_velocity) if mx else (0.0,) * 4),
                *(_tyre4(mx.suspension_acceleration) if mx else (0.0,) * 4),
                *(_tyre4(mx.wheel_speed) if mx else (0.0,) * 4),
                *(_tyre4(mx.wheel_slip_ratio) if mx else (0.0,) * 4),
                *(_tyre4(mx.wheel_slip_angle) if mx else (0.0,) * 4),
                *(_tyre4(mx.wheel_lat_force) if mx else (0.0,) * 4),
                *(_tyre4(mx.wheel_long_force) if mx else (0.0,) * 4),
                mx.height_of_cog_above_ground if mx else 0.0,
                mx.local_velocity.x if mx else 0.0,
                mx.local_velocity.y if mx else 0.0,
                mx.local_velocity.z if mx else 0.0,
                mx.angular_velocity.x if mx else 0.0,
                mx.angular_velocity.y if mx else 0.0,
                mx.angular_velocity.z if mx else 0.0,
                mx.angular_acceleration.x if mx else 0.0,
                mx.angular_acceleration.y if mx else 0.0,
                mx.angular_acceleration.z if mx else 0.0,
                mx.front_wheels_angle if mx else 0.0,
                *(_tyre4(mx.wheel_vert_force) if mx else (0.0,) * 4),
                # CAR_STATUS
                int(cs.fuel_mix) if cs else 0,
                cs.front_brake_bias if cs else 0,
                cs.fuel_remaining if cs else 0.0,
                cs.fuel_remaining_laps if cs else 0.0,
                1 if (cs and cs.drs_allowed) else 0,
                cs.drs_activation_distance if cs else 0,
                int(cs.actual_tyre_compound) if cs else 0,
                cs.tyre_age_laps if cs else 0,
                int(cs.vehicle_flag) if cs else 0,
                cs.ers_store_energy if cs else 0.0,
                int(cs.ers_deploy_mode) if cs else 0,
                cs.ers_harvested_this_lap_mguk if cs else 0.0,
                cs.ers_harvested_this_lap_mguh if cs else 0.0,
                cs.ers_deployed_this_lap if cs else 0.0,
                # CAR_DAMAGE
                *(_tyre4(cd.tyre_wear) if cd else (0.0,) * 4),
                *(_tyre4(cd.tyre_damage) if cd else (0,) * 4),
                *(_tyre4(cd.brakes_damage) if cd else (0,) * 4),
                cd.front_left_wing_damage if cd else 0,
                cd.front_right_wing_damage if cd else 0,
                cd.rear_wing_damage if cd else 0,
                cd.floor_damage if cd else 0,
                cd.diffuser_damage if cd else 0,
                cd.sidepod_damage if cd else 0,
                1 if (cd and cd.drs_fault) else 0,
                1 if (cd and cd.ers_fault) else 0,
                cd.gearbox_damage if cd else 0,
                cd.engine_damage if cd else 0,
                cd.engine_mguh_wear if cd else 0,
                cd.engine_es_wear if cd else 0,
                cd.engine_ce_wear if cd else 0,
                cd.engine_ice_wear if cd else 0,
                cd.engine_mguk_wear if cd else 0,
                cd.engine_tc_wear if cd else 0,
            )
        except (struct.error, TypeError, AttributeError):
            logger.error("Failed to pack sample at session_time=%.3f", session_time, exc_info=True)
            return None
