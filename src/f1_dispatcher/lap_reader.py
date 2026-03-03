"""Lap Reader - decode .f1lap binary files back into Python objects."""

import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .lap_recorder import MAGIC, HEADER_STRUCT, HEADER_SIZE, SAMPLE_STRUCT, SAMPLE_SIZE


@dataclass
class LapSample:
    """One telemetry sample (~20 Hz)."""
    session_time: float

    # CAR_TELEMETRY
    speed: int
    throttle: float
    steer: float
    brake: float
    clutch: int
    gear: int
    engine_rpm: int
    drs: bool
    rev_lights_percent: int
    brake_temp: tuple       # (RL, RR, FL, FR)
    tyre_surface_temp: tuple
    tyre_inner_temp: tuple
    engine_temperature: int
    tyre_pressure: tuple
    surface_type: tuple

    # LAP_DATA
    current_lap_time_ms: int
    sector1_time_ms: int
    sector2_time_ms: int
    lap_distance: float
    total_distance: float
    safety_car_delta: float
    position: int
    current_lap: int
    pit_status: int
    sector: int
    current_lap_invalid: bool
    delta_car_in_front_ms: int
    delta_race_leader_ms: int
    driver_status: int
    result_status: int

    # MOTION
    world_position: tuple   # (x, y, z)
    world_velocity: tuple   # (x, y, z)
    g_force: tuple          # (lat, lon, vert)
    yaw: float
    pitch: float
    roll: float

    # MOTION_EX
    suspension_position: tuple    # (RL, RR, FL, FR)
    suspension_velocity: tuple
    suspension_accel: tuple
    wheel_speed: tuple
    wheel_slip_ratio: tuple
    wheel_slip_angle: tuple
    wheel_lat_force: tuple
    wheel_long_force: tuple
    height_of_cog: float
    local_velocity: tuple         # (x, y, z)
    angular_velocity: tuple
    angular_accel: tuple
    front_wheels_angle: float
    wheel_vert_force: tuple

    # CAR_STATUS
    fuel_mix: int
    front_brake_bias: int
    fuel_remaining: float
    fuel_remaining_laps: float
    drs_allowed: bool
    drs_activation_distance: int
    actual_tyre_compound: int
    tyre_age_laps: int
    vehicle_flag: int
    ers_store_energy: float
    ers_deploy_mode: int
    ers_harvested_mguk: float
    ers_harvested_mguh: float
    ers_deployed_this_lap: float

    # CAR_DAMAGE
    tyre_wear: tuple         # (RL, RR, FL, FR)
    tyre_damage: tuple
    brakes_damage: tuple
    fl_wing_damage: int
    fr_wing_damage: int
    rear_wing_damage: int
    floor_damage: int
    diffuser_damage: int
    sidepod_damage: int
    drs_fault: bool
    ers_fault: bool
    gearbox_damage: int
    engine_damage: int
    engine_mguh_wear: int
    engine_es_wear: int
    engine_ce_wear: int
    engine_ice_wear: int
    engine_mguk_wear: int
    engine_tc_wear: int


@dataclass
class LapHeader:
    """File header metadata for a recorded lap."""
    version: int
    game_year: int
    track_id: int
    session_type: int
    weather: int
    lap_number: int
    lap_valid: bool
    team_id: int
    tyre_compound: int
    session_uid: int
    lap_time_ms: int
    sector1_ms: int
    sector2_ms: int
    sector3_ms: int
    driver_name: str
    num_samples: int


@dataclass
class LapFile:
    """Complete decoded .f1lap file."""
    header: LapHeader
    samples: list  # list[LapSample]
    path: Optional[Path] = None


@dataclass
class LapSummary:
    """Lightweight metadata for listing laps without loading samples."""
    path: Path
    lap_number: int
    track_id: int
    session_type: int
    lap_time_ms: int
    driver_name: str
    num_samples: int
    lap_valid: bool
    session_dir: str


def _unpack_sample(raw: bytes) -> LapSample:
    """Unpack a single sample record from raw bytes."""
    v = SAMPLE_STRUCT.unpack(raw)
    i = 0

    def take(n=1):
        nonlocal i
        if n == 1:
            val = v[i]
            i += 1
            return val
        val = v[i:i + n]
        i += n
        return val

    session_time = take()

    # CAR_TELEMETRY
    speed = take()
    throttle = take()
    steer = take()
    brake = take()
    clutch = take()
    gear = take()
    engine_rpm = take()
    drs = bool(take())
    rev_lights_percent = take()
    brake_temp = take(4)
    tyre_surface_temp = take(4)
    tyre_inner_temp = take(4)
    engine_temperature = take()
    tyre_pressure = take(4)
    surface_type = take(4)

    # LAP_DATA
    current_lap_time_ms = take()
    sector1_time_ms = take()
    sector2_time_ms = take()
    lap_distance = take()
    total_distance = take()
    safety_car_delta = take()
    position = take()
    current_lap = take()
    pit_status = take()
    sector = take()
    current_lap_invalid = bool(take())
    delta_car_in_front_ms = take()
    delta_race_leader_ms = take()
    driver_status = take()
    result_status = take()

    # MOTION
    world_position = take(3)
    world_velocity = take(3)
    g_force = take(3)
    yaw = take()
    pitch = take()
    roll = take()

    # MOTION_EX
    suspension_position = take(4)
    suspension_velocity = take(4)
    suspension_accel = take(4)
    wheel_speed = take(4)
    wheel_slip_ratio = take(4)
    wheel_slip_angle = take(4)
    wheel_lat_force = take(4)
    wheel_long_force = take(4)
    height_of_cog = take()
    local_velocity = take(3)
    angular_velocity = take(3)
    angular_accel = take(3)
    front_wheels_angle = take()
    wheel_vert_force = take(4)

    # CAR_STATUS
    fuel_mix = take()
    front_brake_bias = take()
    fuel_remaining = take()
    fuel_remaining_laps = take()
    drs_allowed = bool(take())
    drs_activation_distance = take()
    actual_tyre_compound = take()
    tyre_age_laps = take()
    vehicle_flag = take()
    ers_store_energy = take()
    ers_deploy_mode = take()
    ers_harvested_mguk = take()
    ers_harvested_mguh = take()
    ers_deployed_this_lap = take()

    # CAR_DAMAGE
    tyre_wear = take(4)
    tyre_damage = take(4)
    brakes_damage = take(4)
    fl_wing_damage = take()
    fr_wing_damage = take()
    rear_wing_damage = take()
    floor_damage = take()
    diffuser_damage = take()
    sidepod_damage = take()
    drs_fault = bool(take())
    ers_fault = bool(take())
    gearbox_damage = take()
    engine_damage = take()
    engine_mguh_wear = take()
    engine_es_wear = take()
    engine_ce_wear = take()
    engine_ice_wear = take()
    engine_mguk_wear = take()
    engine_tc_wear = take()

    return LapSample(
        session_time=session_time,
        speed=speed, throttle=throttle, steer=steer, brake=brake,
        clutch=clutch, gear=gear, engine_rpm=engine_rpm, drs=drs,
        rev_lights_percent=rev_lights_percent,
        brake_temp=brake_temp, tyre_surface_temp=tyre_surface_temp,
        tyre_inner_temp=tyre_inner_temp, engine_temperature=engine_temperature,
        tyre_pressure=tyre_pressure, surface_type=surface_type,
        current_lap_time_ms=current_lap_time_ms,
        sector1_time_ms=sector1_time_ms, sector2_time_ms=sector2_time_ms,
        lap_distance=lap_distance, total_distance=total_distance,
        safety_car_delta=safety_car_delta, position=position,
        current_lap=current_lap, pit_status=pit_status, sector=sector,
        current_lap_invalid=current_lap_invalid,
        delta_car_in_front_ms=delta_car_in_front_ms,
        delta_race_leader_ms=delta_race_leader_ms,
        driver_status=driver_status, result_status=result_status,
        world_position=world_position, world_velocity=world_velocity,
        g_force=g_force, yaw=yaw, pitch=pitch, roll=roll,
        suspension_position=suspension_position,
        suspension_velocity=suspension_velocity,
        suspension_accel=suspension_accel,
        wheel_speed=wheel_speed, wheel_slip_ratio=wheel_slip_ratio,
        wheel_slip_angle=wheel_slip_angle,
        wheel_lat_force=wheel_lat_force, wheel_long_force=wheel_long_force,
        height_of_cog=height_of_cog,
        local_velocity=local_velocity, angular_velocity=angular_velocity,
        angular_accel=angular_accel, front_wheels_angle=front_wheels_angle,
        wheel_vert_force=wheel_vert_force,
        fuel_mix=fuel_mix, front_brake_bias=front_brake_bias,
        fuel_remaining=fuel_remaining, fuel_remaining_laps=fuel_remaining_laps,
        drs_allowed=drs_allowed, drs_activation_distance=drs_activation_distance,
        actual_tyre_compound=actual_tyre_compound,
        tyre_age_laps=tyre_age_laps, vehicle_flag=vehicle_flag,
        ers_store_energy=ers_store_energy, ers_deploy_mode=ers_deploy_mode,
        ers_harvested_mguk=ers_harvested_mguk,
        ers_harvested_mguh=ers_harvested_mguh,
        ers_deployed_this_lap=ers_deployed_this_lap,
        tyre_wear=tyre_wear, tyre_damage=tyre_damage,
        brakes_damage=brakes_damage,
        fl_wing_damage=fl_wing_damage, fr_wing_damage=fr_wing_damage,
        rear_wing_damage=rear_wing_damage, floor_damage=floor_damage,
        diffuser_damage=diffuser_damage, sidepod_damage=sidepod_damage,
        drs_fault=drs_fault, ers_fault=ers_fault,
        gearbox_damage=gearbox_damage, engine_damage=engine_damage,
        engine_mguh_wear=engine_mguh_wear, engine_es_wear=engine_es_wear,
        engine_ce_wear=engine_ce_wear, engine_ice_wear=engine_ice_wear,
        engine_mguk_wear=engine_mguk_wear, engine_tc_wear=engine_tc_wear,
    )


def _read_header(raw: bytes) -> LapHeader:
    """Decode the 84-byte file header."""
    vals = HEADER_STRUCT.unpack(raw)
    # vals layout:
    # 0: magic (4s)
    # 1: version (B)
    # 2: game_year (B)
    # 3: track_id (B)
    # 4: session_type (B)
    # 5: weather (B)
    # 6: lap_number (B)
    # 7: lap_valid (B)
    # 8: team_id (B)
    # 9: tyre_compound (B)
    # 10: session_uid (Q)
    # 11: lap_time_ms (I)
    # 12: sector1_ms (H)
    # 13: sector2_ms (H)
    # 14: sector3_ms (H)
    # 15: driver_name (48s)
    # 16: num_samples (I)
    magic = vals[0]
    if magic != MAGIC:
        raise ValueError(f"Invalid magic: {magic!r} (expected {MAGIC!r})")

    driver_name = vals[15].split(b"\x00")[0].decode("utf-8", errors="replace")

    return LapHeader(
        version=vals[1],
        game_year=vals[2],
        track_id=vals[3],
        session_type=vals[4],
        weather=vals[5],
        lap_number=vals[6],
        lap_valid=bool(vals[7]),
        team_id=vals[8],
        tyre_compound=vals[9],
        session_uid=vals[10],
        lap_time_ms=vals[11],
        sector1_ms=vals[12],
        sector2_ms=vals[13],
        sector3_ms=vals[14],
        driver_name=driver_name,
        num_samples=vals[16],
    )


def read_lap(path) -> LapFile:
    """Decode a .f1lap file into a LapFile with header + samples.

    Args:
        path: Path to a .f1lap file (str or Path).

    Returns:
        LapFile with header metadata and list of LapSample objects.
    """
    path = Path(path)
    data = path.read_bytes()

    if len(data) < HEADER_SIZE:
        raise ValueError(f"File too small ({len(data)} bytes, need at least {HEADER_SIZE})")

    header = _read_header(data[:HEADER_SIZE])

    samples = []
    offset = HEADER_SIZE
    for _ in range(header.num_samples):
        if offset + SAMPLE_SIZE > len(data):
            break
        sample = _unpack_sample(data[offset:offset + SAMPLE_SIZE])
        samples.append(sample)
        offset += SAMPLE_SIZE

    return LapFile(header=header, samples=samples, path=path)


def list_laps(directory="laps") -> list[LapSummary]:
    """Scan a directory tree for .f1lap files and return metadata for each.

    Args:
        directory: Root directory to scan (default "laps").

    Returns:
        List of LapSummary sorted by path.
    """
    root = Path(directory)
    if not root.exists():
        return []

    summaries = []
    for f1lap in sorted(root.rglob("*.f1lap")):
        try:
            raw = f1lap.read_bytes()
            if len(raw) < HEADER_SIZE:
                continue
            hdr = _read_header(raw[:HEADER_SIZE])
            summaries.append(LapSummary(
                path=f1lap,
                lap_number=hdr.lap_number,
                track_id=hdr.track_id,
                session_type=hdr.session_type,
                lap_time_ms=hdr.lap_time_ms,
                driver_name=hdr.driver_name,
                num_samples=hdr.num_samples,
                lap_valid=hdr.lap_valid,
                session_dir=f1lap.parent.name,
            ))
        except (ValueError, OSError):
            continue

    return summaries
