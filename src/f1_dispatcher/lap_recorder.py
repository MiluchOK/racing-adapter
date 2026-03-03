"""Lap Recorder - records per-lap telemetry to compact .f1lap binary files."""

import struct
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from f1_telemetry.packets import (
    PacketType, Track, Weather, SessionType, Team, TyreCompound,
)

# Binary format constants
MAGIC = b"F1LP"
FORMAT_VERSION = 1
HEADER_STRUCT = struct.Struct("<4s B B B B B B B B B Q I H H H 48s I")
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


def _tyre4(td):
    """Extract (RL, RR, FL, FR) tuple from a TyreData object."""
    return (td.rear_left, td.rear_right, td.front_left, td.front_right)


def _track_slug(track) -> str:
    """Short filesystem-safe track name."""
    if isinstance(track, Track):
        return track.name.lower()
    return str(track)


def _session_slug(session_type) -> str:
    """Short filesystem-safe session type name."""
    if isinstance(session_type, SessionType):
        return session_type.name.lower()
    return str(session_type)


@dataclass
class _CachedLap:
    """Accumulated samples for one lap."""
    lap_number: int = 0
    samples: list = field(default_factory=list)
    lap_valid: bool = True


class LapRecorder:
    """Records per-lap telemetry to .f1lap binary files.

    Uses the same register(dispatcher) pattern as LapReporter.
    CAR_TELEMETRY is the trigger (~20 Hz); lower-frequency packets carry
    their most recent cached values.
    """

    def __init__(self, laps_dir: str = "laps"):
        self._base_dir = Path(laps_dir)
        self._session_dir: Optional[Path] = None

        # Session-level metadata (from SESSION / PARTICIPANTS packets)
        self._game_year: int = 0
        self._track: Optional[Track] = None
        self._session_type: Optional[SessionType] = None
        self._weather: Optional[Weather] = None
        self._session_uid: int = 0
        self._driver_name: str = ""
        self._team: int = 0
        self._tyre_compound: int = 0

        # Per-lap sector cache from SESSION_HISTORY {lap_num: (s1, s2, s3)}
        self._lap_sectors: dict[int, tuple[int, int, int]] = {}

        # Latest cached packet data (carried forward into each sample)
        self._lap_data = None
        self._motion = None
        self._motion_ex = None
        self._car_status = None
        self._car_damage = None

        # Current lap accumulator
        self._current_lap = _CachedLap()
        self._recording = False

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
        prev_lap_num = self._current_lap.lap_number

        # Detect lap boundary
        if data.current_lap != prev_lap_num and prev_lap_num > 0 and self._recording:
            self._flush_lap()

        self._current_lap.lap_number = data.current_lap
        if data.current_lap_invalid:
            self._current_lap.lap_valid = False
        self._lap_data = data

    def _handle_car_telemetry(self, header, data):
        """Trigger: append a sample using latest cached values from all packet types."""
        if not self._recording:
            return

        sample = self._pack_sample(header.session_time, data)
        if sample:
            self._current_lap.samples.append(sample)

    def _handle_event(self, header, data):
        if data.event_code == "SSTA":
            self._start_session()
        elif data.event_code == "SEND":
            self._end_session()

    # ── session lifecycle ────────────────────────────────────────────

    def _start_session(self):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        track = _track_slug(self._track) if self._track is not None else "unknown"
        stype = _session_slug(self._session_type) if self._session_type is not None else "unknown"
        self._session_dir = self._base_dir / f"{ts}_{track}_{stype}"
        self._session_dir.mkdir(parents=True, exist_ok=True)

        self._current_lap = _CachedLap()
        self._lap_sectors.clear()
        self._recording = True
        print(f"[LapRecorder] Session started — recording to {self._session_dir}")

    def _end_session(self):
        if self._recording and self._current_lap.samples:
            self._flush_lap()
        self._recording = False
        print("[LapRecorder] Session ended")

    # ── flush / write ────────────────────────────────────────────────

    def _flush_lap(self):
        """Write accumulated samples for the completed lap to a .f1lap file."""
        lap = self._current_lap
        if not lap.samples or self._session_dir is None:
            self._current_lap = _CachedLap()
            return

        lap_num = lap.lap_number
        sectors = self._lap_sectors.get(lap_num, (0, 0, 0))

        # Compute lap time from sectors (if available) or from last_lap_time_ms
        lap_time_ms = 0
        if all(s > 0 for s in sectors):
            lap_time_ms = sum(sectors)
        elif self._lap_data and self._lap_data.last_lap_time_ms > 0:
            lap_time_ms = self._lap_data.last_lap_time_ms

        driver_bytes = self._driver_name.encode("utf-8")[:48].ljust(48, b"\x00")

        header_data = HEADER_STRUCT.pack(
            MAGIC,
            FORMAT_VERSION,
            self._game_year,
            int(self._track) if self._track is not None else 0,
            int(self._session_type) if self._session_type is not None else 0,
            int(self._weather) if self._weather is not None else 0,
            lap_num,
            1 if lap.lap_valid else 0,
            self._team,
            self._tyre_compound,
            self._session_uid,
            lap_time_ms,
            sectors[0],
            sectors[1],
            sectors[2],
            driver_bytes,
            len(lap.samples),
        )

        filename = self._session_dir / f"lap_{lap_num:02d}.f1lap"
        with open(filename, "wb") as f:
            f.write(header_data)
            for sample in lap.samples:
                f.write(sample)

        size_kb = (HEADER_SIZE + len(lap.samples) * SAMPLE_SIZE) / 1024
        print(f"[LapRecorder] Saved lap {lap_num} ({len(lap.samples)} samples, {size_kb:.0f} KB) → {filename.name}")

        self._current_lap = _CachedLap()

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
        except (struct.error, TypeError, AttributeError) as e:
            return None
