"""F1 Telemetry Client - UDP listener with clean Python API."""

import socket
import struct
import threading
from typing import Optional, Callable
from dataclasses import dataclass

from .packets import (
    PacketType,
    PacketHeader,
    SessionData,
    LapData,
    CarTelemetry,
    CarStatus,
    CarDamage,
    CarMotion,
    MotionEx,
    ParticipantData,
    CarSetup,
    TyreData,
    Vector3,
    Weather,
    SessionType,
    Track,
    TyreCompound,
    FuelMix,
    ERSMode,
    VehicleFlag,
    PitStatus,
    Team,
)


# =============================================================================
# PACKET PARSING
# =============================================================================

def parse_header(data: bytes) -> Optional[PacketHeader]:
    """Parse packet header (29 bytes)."""
    if len(data) < 29:
        return None

    try:
        u = struct.unpack("<HBBBBBQfIIBB", data[:29])
        return PacketHeader(
            packet_format=u[0],
            game_year=u[1],
            game_major_version=u[2],
            game_minor_version=u[3],
            packet_version=u[4],
            packet_type=PacketType(u[5]) if u[5] <= 14 else u[5],
            session_uid=u[6],
            session_time=u[7],
            frame_identifier=u[8],
            overall_frame_identifier=u[9],
            player_car_index=u[10],
            secondary_player_car_index=u[11],
        )
    except (struct.error, ValueError):
        return None


def parse_session(data: bytes) -> Optional[SessionData]:
    """Parse session packet."""
    if len(data) < 29 + 50:
        return None

    try:
        d = data[29:]

        weather = d[0]
        track_temp = struct.unpack("<b", d[1:2])[0]
        air_temp = struct.unpack("<b", d[2:3])[0]
        total_laps = d[3]
        track_length = struct.unpack("<H", d[4:6])[0]
        session_type = d[6]
        track_id = struct.unpack("<b", d[7:8])[0]
        formula = d[8]
        session_time_left = struct.unpack("<H", d[9:11])[0]
        session_duration = struct.unpack("<H", d[11:13])[0]
        pit_speed_limit = d[13]
        game_paused = bool(d[14])
        is_spectating = bool(d[15])
        spectator_car_index = d[16]
        sli_pro_support = bool(d[17])
        num_marshal_zones = d[18]

        # Skip marshal zones (21 * num_marshal_zones bytes)
        offset = 19 + (21 * num_marshal_zones)

        safety_car_status = d[offset] if offset < len(d) else 0
        network_game = bool(d[offset + 1]) if offset + 1 < len(d) else False

        return SessionData(
            weather=Weather(weather) if weather <= 5 else weather,
            track_temperature=track_temp,
            air_temperature=air_temp,
            total_laps=total_laps,
            track_length=track_length,
            session_type=SessionType(session_type) if session_type <= 13 else session_type,
            track=Track(track_id) if 0 <= track_id <= 32 else track_id,
            formula=formula,
            session_time_left=session_time_left,
            session_duration=session_duration,
            pit_speed_limit=pit_speed_limit,
            game_paused=game_paused,
            is_spectating=is_spectating,
            spectator_car_index=spectator_car_index,
            sli_pro_support=sli_pro_support,
            num_marshal_zones=num_marshal_zones,
            safety_car_status=safety_car_status,
            network_game=network_game,
            num_weather_forecast_samples=0,
            forecast_accuracy=0,
            ai_difficulty=0,
            season_link_identifier=0,
            weekend_link_identifier=0,
            session_link_identifier=0,
            pit_stop_window_ideal_lap=0,
            pit_stop_window_latest_lap=0,
            pit_stop_rejoin_position=0,
            steering_assist=False,
            braking_assist=0,
            gearbox_assist=0,
            pit_assist=False,
            pit_release_assist=False,
            ers_assist=False,
            drs_assist=False,
            dynamic_racing_line=0,
            dynamic_racing_line_type=0,
            game_mode=0,
            rule_set=0,
            time_of_day=0,
            session_length=0,
        )
    except (struct.error, ValueError, IndexError):
        return None


def parse_lap_data(data: bytes, car_index: int) -> Optional[LapData]:
    """Parse lap data for specific car."""
    header_size = 29
    lap_size = 57
    offset = header_size + (car_index * lap_size)

    if len(data) < offset + lap_size:
        return None

    try:
        d = data[offset:offset + lap_size]

        last_lap_ms = struct.unpack("<I", d[0:4])[0]
        current_lap_ms = struct.unpack("<I", d[4:8])[0]
        sector1_ms = struct.unpack("<H", d[8:10])[0]
        sector1_mins = d[10]
        sector2_ms = struct.unpack("<H", d[11:13])[0]
        sector2_mins = d[13]
        delta_in_front = struct.unpack("<H", d[14:16])[0]
        delta_leader = struct.unpack("<H", d[16:18])[0]
        lap_distance = struct.unpack("<f", d[18:22])[0]
        total_distance = struct.unpack("<f", d[22:26])[0]
        safety_car_delta = struct.unpack("<f", d[26:30])[0]
        position = d[30]
        current_lap = d[31]
        pit_status = d[32]
        num_pit_stops = d[33]
        sector = d[34]
        current_lap_invalid = bool(d[35])
        penalties = d[36]
        total_warnings = d[37]
        corner_cutting = d[38]
        num_dt = d[39]
        num_sg = d[40]
        grid_position = d[41]
        driver_status = d[42]
        result_status = d[43]
        pit_timer_active = bool(d[44])
        pit_time_in_lane = struct.unpack("<H", d[45:47])[0]
        pit_stop_timer = struct.unpack("<H", d[47:49])[0]
        pit_serve_penalty = bool(d[49])

        return LapData(
            last_lap_time_ms=last_lap_ms,
            current_lap_time_ms=current_lap_ms,
            sector1_time_ms=sector1_ms + (sector1_mins * 60000),
            sector2_time_ms=sector2_ms + (sector2_mins * 60000),
            delta_to_car_in_front_ms=delta_in_front,
            delta_to_race_leader_ms=delta_leader,
            lap_distance=lap_distance,
            total_distance=total_distance,
            safety_car_delta=safety_car_delta,
            position=position,
            current_lap=current_lap,
            pit_status=PitStatus(pit_status) if pit_status <= 2 else pit_status,
            num_pit_stops=num_pit_stops,
            sector=sector,
            current_lap_invalid=current_lap_invalid,
            penalties=penalties,
            total_warnings=total_warnings,
            corner_cutting_warnings=corner_cutting,
            num_unserved_drive_through=num_dt,
            num_unserved_stop_go=num_sg,
            grid_position=grid_position,
            driver_status=driver_status,
            result_status=result_status,
            pit_lane_timer_active=pit_timer_active,
            pit_lane_time_in_lane_ms=pit_time_in_lane,
            pit_stop_timer_ms=pit_stop_timer,
            pit_stop_should_serve_penalty=pit_serve_penalty,
        )
    except (struct.error, ValueError, IndexError):
        return None


def parse_car_telemetry(data: bytes, car_index: int) -> Optional[CarTelemetry]:
    """Parse car telemetry for specific car."""
    header_size = 29
    telemetry_size = 60
    offset = header_size + (car_index * telemetry_size)

    if len(data) < offset + telemetry_size:
        return None

    try:
        d = data[offset:offset + telemetry_size]

        speed = struct.unpack("<H", d[0:2])[0]
        throttle = struct.unpack("<f", d[2:6])[0]
        steer = struct.unpack("<f", d[6:10])[0]
        brake = struct.unpack("<f", d[10:14])[0]
        clutch = d[14]
        gear = struct.unpack("<b", d[15:16])[0]
        rpm = struct.unpack("<H", d[16:18])[0]
        drs = bool(d[18])
        rev_lights = d[19]
        rev_lights_bit = struct.unpack("<H", d[20:22])[0]

        brake_temp = struct.unpack("<4H", d[22:30])
        tyre_surface = struct.unpack("<4B", d[30:34])
        tyre_inner = struct.unpack("<4B", d[34:38])
        engine_temp = struct.unpack("<H", d[38:40])[0]
        tyre_pressure = struct.unpack("<4f", d[40:56])
        surface_type = struct.unpack("<4B", d[56:60])

        return CarTelemetry(
            speed=speed,
            throttle=throttle,
            steer=steer,
            brake=brake,
            clutch=clutch,
            gear=gear,
            engine_rpm=rpm,
            drs=drs,
            rev_lights_percent=rev_lights,
            rev_lights_bit_value=rev_lights_bit,
            brake_temperature=TyreData(brake_temp[0], brake_temp[1], brake_temp[2], brake_temp[3]),
            tyre_surface_temperature=TyreData(tyre_surface[0], tyre_surface[1], tyre_surface[2], tyre_surface[3]),
            tyre_inner_temperature=TyreData(tyre_inner[0], tyre_inner[1], tyre_inner[2], tyre_inner[3]),
            engine_temperature=engine_temp,
            tyre_pressure=TyreData(tyre_pressure[0], tyre_pressure[1], tyre_pressure[2], tyre_pressure[3]),
            surface_type=surface_type,
        )
    except (struct.error, ValueError, IndexError):
        return None


def parse_car_status(data: bytes, car_index: int) -> Optional[CarStatus]:
    """Parse car status for specific car."""
    header_size = 29
    status_size = 55
    offset = header_size + (car_index * status_size)

    if len(data) < offset + status_size:
        return None

    try:
        d = data[offset:offset + status_size]

        tc = d[0]
        abs_on = bool(d[1])
        fuel_mix = d[2]
        brake_bias = d[3]
        pit_limiter = bool(d[4])
        fuel = struct.unpack("<f", d[5:9])[0]
        fuel_cap = struct.unpack("<f", d[9:13])[0]
        fuel_laps = struct.unpack("<f", d[13:17])[0]
        max_rpm = struct.unpack("<H", d[17:19])[0]
        idle_rpm = struct.unpack("<H", d[19:21])[0]
        max_gears = d[21]
        drs_allowed = bool(d[22])
        drs_dist = struct.unpack("<H", d[23:25])[0]
        tyre_compound = d[25]
        tyre_visual = d[26]
        tyre_age = d[27]
        flag = d[28]
        ers = struct.unpack("<f", d[29:33])[0]
        ers_mode = d[33]
        ers_mguk = struct.unpack("<f", d[34:38])[0]
        ers_mguh = struct.unpack("<f", d[38:42])[0]
        ers_deployed = struct.unpack("<f", d[42:46])[0]

        return CarStatus(
            traction_control=tc,
            anti_lock_brakes=abs_on,
            fuel_mix=FuelMix(fuel_mix) if fuel_mix <= 3 else fuel_mix,
            front_brake_bias=brake_bias,
            pit_limiter=pit_limiter,
            fuel_remaining=fuel,
            fuel_capacity=fuel_cap,
            fuel_remaining_laps=fuel_laps,
            max_rpm=max_rpm,
            idle_rpm=idle_rpm,
            max_gears=max_gears,
            drs_allowed=drs_allowed,
            drs_activation_distance=drs_dist,
            actual_tyre_compound=TyreCompound(tyre_compound) if tyre_compound in (7, 8, 16, 17, 18) else tyre_compound,
            visual_tyre_compound=tyre_visual,
            tyre_age_laps=tyre_age,
            vehicle_flag=VehicleFlag(flag) if flag <= 4 else flag,
            engine_power_ice=0,
            engine_power_mguk=0,
            ers_store_energy=ers,
            ers_deploy_mode=ERSMode(ers_mode) if ers_mode <= 3 else ers_mode,
            ers_harvested_this_lap_mguk=ers_mguk,
            ers_harvested_this_lap_mguh=ers_mguh,
            ers_deployed_this_lap=ers_deployed,
            network_paused=False,
        )
    except (struct.error, ValueError, IndexError):
        return None


def parse_car_damage(data: bytes, car_index: int) -> Optional[CarDamage]:
    """Parse car damage for specific car."""
    header_size = 29
    damage_size = 42
    offset = header_size + (car_index * damage_size)

    if len(data) < offset + damage_size:
        return None

    try:
        d = data[offset:offset + damage_size]

        tyre_wear = struct.unpack("<4f", d[0:16])
        tyre_damage = struct.unpack("<4B", d[16:20])
        brakes_damage = struct.unpack("<4B", d[20:24])
        fl_wing = d[24]
        fr_wing = d[25]
        rear_wing = d[26]
        floor = d[27]
        diffuser = d[28]
        sidepod = d[29]
        drs_fault = bool(d[30])
        ers_fault = bool(d[31])
        gearbox = d[32]
        engine = d[33]
        mguh = d[34]
        es = d[35]
        ce = d[36]
        ice = d[37]
        mguk = d[38]
        tc = d[39]

        return CarDamage(
            tyre_wear=TyreData(tyre_wear[0], tyre_wear[1], tyre_wear[2], tyre_wear[3]),
            tyre_damage=TyreData(tyre_damage[0], tyre_damage[1], tyre_damage[2], tyre_damage[3]),
            brakes_damage=TyreData(brakes_damage[0], brakes_damage[1], brakes_damage[2], brakes_damage[3]),
            front_left_wing_damage=fl_wing,
            front_right_wing_damage=fr_wing,
            rear_wing_damage=rear_wing,
            floor_damage=floor,
            diffuser_damage=diffuser,
            sidepod_damage=sidepod,
            drs_fault=drs_fault,
            ers_fault=ers_fault,
            gearbox_damage=gearbox,
            engine_damage=engine,
            engine_mguh_wear=mguh,
            engine_es_wear=es,
            engine_ce_wear=ce,
            engine_ice_wear=ice,
            engine_mguk_wear=mguk,
            engine_tc_wear=tc,
            engine_blown=False,
            engine_seized=False,
        )
    except (struct.error, ValueError, IndexError):
        return None


def parse_car_motion(data: bytes, car_index: int) -> Optional[CarMotion]:
    """Parse car motion for specific car."""
    header_size = 29
    motion_size = 60
    offset = header_size + (car_index * motion_size)

    if len(data) < offset + motion_size:
        return None

    try:
        d = data[offset:offset + motion_size]

        pos = struct.unpack("<3f", d[0:12])
        vel = struct.unpack("<3f", d[12:24])
        fwd = struct.unpack("<3h", d[24:30])
        right = struct.unpack("<3h", d[30:36])
        g = struct.unpack("<3f", d[36:48])
        ypr = struct.unpack("<3f", d[48:60])

        return CarMotion(
            world_position=Vector3(pos[0], pos[1], pos[2]),
            world_velocity=Vector3(vel[0], vel[1], vel[2]),
            world_forward_dir=Vector3(fwd[0] / 32767.0, fwd[1] / 32767.0, fwd[2] / 32767.0),
            world_right_dir=Vector3(right[0] / 32767.0, right[1] / 32767.0, right[2] / 32767.0),
            g_force_lateral=g[0],
            g_force_longitudinal=g[1],
            g_force_vertical=g[2],
            yaw=ypr[0],
            pitch=ypr[1],
            roll=ypr[2],
        )
    except (struct.error, ValueError, IndexError):
        return None


# =============================================================================
# F1 TELEMETRY CLIENT
# =============================================================================

@dataclass
class F1GameData:
    """Container for all F1 game data with clean API access."""
    header: Optional[PacketHeader] = None
    session: Optional[SessionData] = None
    lap: Optional[LapData] = None
    telemetry: Optional[CarTelemetry] = None
    status: Optional[CarStatus] = None
    damage: Optional[CarDamage] = None
    motion: Optional[CarMotion] = None

    @property
    def speed(self) -> int:
        """Current speed in km/h."""
        return self.telemetry.speed if self.telemetry else 0

    @property
    def gear(self) -> str:
        """Current gear as string."""
        return self.telemetry.gear_str if self.telemetry else "N"

    @property
    def rpm(self) -> int:
        """Current engine RPM."""
        return self.telemetry.engine_rpm if self.telemetry else 0

    @property
    def throttle(self) -> float:
        """Throttle percentage 0-100."""
        return self.telemetry.throttle_percent if self.telemetry else 0

    @property
    def brake(self) -> float:
        """Brake percentage 0-100."""
        return self.telemetry.brake_percent if self.telemetry else 0

    @property
    def drs(self) -> bool:
        """DRS active."""
        return self.telemetry.drs if self.telemetry else False

    @property
    def track(self) -> str:
        """Current track name."""
        return self.session.track_name if self.session else "Unknown"

    @property
    def weather(self) -> str:
        """Current weather."""
        return self.session.weather_name if self.session else "Unknown"

    @property
    def position(self) -> int:
        """Race position."""
        return self.lap.position if self.lap else 0

    @property
    def current_lap(self) -> int:
        """Current lap number."""
        return self.lap.current_lap if self.lap else 0

    @property
    def lap_time(self) -> str:
        """Current lap time formatted."""
        return self.lap.current_lap_time if self.lap else "0:00.000"

    @property
    def last_lap(self) -> str:
        """Last lap time formatted."""
        return self.lap.last_lap_time if self.lap else "--:--.---"

    @property
    def fuel(self) -> float:
        """Fuel remaining in kg."""
        return round(self.status.fuel_remaining, 2) if self.status else 0

    @property
    def fuel_laps(self) -> float:
        """Fuel remaining in laps."""
        return round(self.status.fuel_remaining_laps, 2) if self.status else 0

    @property
    def tyre_compound(self) -> str:
        """Current tyre compound."""
        return self.status.tyre_compound_name if self.status else "Unknown"

    @property
    def tyre_age(self) -> int:
        """Tyre age in laps."""
        return self.status.tyre_age_laps if self.status else 0

    @property
    def ers_percent(self) -> float:
        """ERS battery percentage."""
        return self.status.ers_percent if self.status else 0


class F1TelemetryClient:
    """
    F1 Telemetry UDP Client.

    Usage:
        client = F1TelemetryClient()
        client.start()

        # Access data
        print(client.data.speed)
        print(client.data.session.track_name)
        print(client.data.telemetry.gear)

        client.stop()
    """

    def __init__(self, port: int = 20777):
        self.port = port
        self.data = F1GameData()
        self._socket: Optional[socket.socket] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._callbacks: list[Callable[[F1GameData], None]] = []

    def on_update(self, callback: Callable[[F1GameData], None]):
        """Register callback for data updates."""
        self._callbacks.append(callback)

    def start(self):
        """Start listening for telemetry data."""
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
        """Stop listening."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._socket:
            self._socket.close()

    def is_connected(self) -> bool:
        """Check if receiving data (had recent packet)."""
        return self.data.header is not None

    def _listen(self):
        """Main listening loop."""
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
        """Process incoming packet."""
        header = parse_header(data)
        if not header:
            return

        self.data.header = header
        car_index = header.player_car_index

        if header.packet_type == PacketType.SESSION:
            self.data.session = parse_session(data)
        elif header.packet_type == PacketType.LAP_DATA:
            self.data.lap = parse_lap_data(data, car_index)
        elif header.packet_type == PacketType.CAR_TELEMETRY:
            self.data.telemetry = parse_car_telemetry(data, car_index)
        elif header.packet_type == PacketType.CAR_STATUS:
            self.data.status = parse_car_status(data, car_index)
        elif header.packet_type == PacketType.CAR_DAMAGE:
            self.data.damage = parse_car_damage(data, car_index)
        elif header.packet_type == PacketType.MOTION:
            self.data.motion = parse_car_motion(data, car_index)

        # Notify callbacks
        for callback in self._callbacks:
            try:
                callback(self.data)
            except Exception:
                pass


# =============================================================================
# SIMPLE USAGE EXAMPLE
# =============================================================================

if __name__ == "__main__":
    import time

    client = F1TelemetryClient()
    client.start()

    print("F1 Telemetry Client - Listening on port 20777...")
    print("Start your F1 game and get on track.\n")

    try:
        while True:
            if client.is_connected():
                d = client.data
                print(f"\r  {d.track} | Lap {d.current_lap} | P{d.position} | "
                      f"{d.speed:3d} km/h | Gear {d.gear} | {d.rpm:5d} RPM | "
                      f"Throttle {d.throttle:5.1f}% | Brake {d.brake:5.1f}% | "
                      f"Fuel {d.fuel:.1f}kg ({d.fuel_laps:.1f} laps) | {d.tyre_compound}",
                      end="", flush=True)
            else:
                print("\r  Waiting for data...", end="", flush=True)
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n\nStopping...")
        client.stop()
