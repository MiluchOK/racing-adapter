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
    EventData,
    FinalClassification,
    LobbyInfo,
    LapHistoryItem,
    SessionHistory,
    TyreSetInfo,
    TyreSetData,
    TimeTrialDataSet,
    TimeTrial,
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


def parse_motion_ex(data: bytes) -> Optional[MotionEx]:
    """Parse extended motion data (player car only)."""
    if len(data) < 29 + 217:
        return None

    try:
        d = data[29:]

        susp_pos = struct.unpack("<4f", d[0:16])
        susp_vel = struct.unpack("<4f", d[16:32])
        susp_acc = struct.unpack("<4f", d[32:48])
        wheel_speed = struct.unpack("<4f", d[48:64])
        wheel_slip_ratio = struct.unpack("<4f", d[64:80])
        wheel_slip_angle = struct.unpack("<4f", d[80:96])
        wheel_lat_force = struct.unpack("<4f", d[96:112])
        wheel_long_force = struct.unpack("<4f", d[112:128])
        height_cog = struct.unpack("<f", d[128:132])[0]
        local_vel = struct.unpack("<3f", d[132:144])
        angular_vel = struct.unpack("<3f", d[144:156])
        angular_acc = struct.unpack("<3f", d[156:168])
        front_wheels_angle = struct.unpack("<f", d[168:172])[0]
        wheel_vert_force = struct.unpack("<4f", d[172:188])

        return MotionEx(
            suspension_position=TyreData(*susp_pos),
            suspension_velocity=TyreData(*susp_vel),
            suspension_acceleration=TyreData(*susp_acc),
            wheel_speed=TyreData(*wheel_speed),
            wheel_slip_ratio=TyreData(*wheel_slip_ratio),
            wheel_slip_angle=TyreData(*wheel_slip_angle),
            wheel_lat_force=TyreData(*wheel_lat_force),
            wheel_long_force=TyreData(*wheel_long_force),
            height_of_cog_above_ground=height_cog,
            local_velocity=Vector3(*local_vel),
            angular_velocity=Vector3(*angular_vel),
            angular_acceleration=Vector3(*angular_acc),
            front_wheels_angle=front_wheels_angle,
            wheel_vert_force=TyreData(*wheel_vert_force),
        )
    except (struct.error, ValueError, IndexError):
        return None


def parse_participants(data: bytes, car_index: int) -> Optional[ParticipantData]:
    """Parse participant data for specific car."""
    header_size = 29
    # First byte after header is m_numActiveCars
    participant_size = 58  # per-car participant record
    offset = header_size + 1 + (car_index * participant_size)

    if len(data) < offset + participant_size:
        return None

    try:
        d = data[offset:offset + participant_size]

        ai = bool(d[0])
        driver_id = d[1]
        network_id = d[2]
        team_id = d[3]
        my_team = bool(d[4])
        race_number = d[5]
        nationality = d[6]
        name = d[7:55].split(b"\x00")[0].decode("utf-8", errors="replace")
        telemetry_public = bool(d[55])
        show_online = bool(d[56])
        platform = d[57]

        return ParticipantData(
            ai_controlled=ai,
            driver_id=driver_id,
            network_id=network_id,
            team=Team(team_id) if team_id <= 9 else team_id,
            my_team=my_team,
            race_number=race_number,
            nationality=nationality,
            name=name,
            telemetry_public=telemetry_public,
            show_online_names=show_online,
            tech_level=0,
            platform=platform,
        )
    except (struct.error, ValueError, IndexError):
        return None


def parse_car_setup(data: bytes, car_index: int) -> Optional[CarSetup]:
    """Parse car setup for specific car."""
    header_size = 29
    setup_size = 53
    offset = header_size + (car_index * setup_size)

    if len(data) < offset + setup_size:
        return None

    try:
        d = data[offset:offset + setup_size]

        front_wing = d[0]
        rear_wing = d[1]
        on_throttle = d[2]
        off_throttle = d[3]
        front_camber = struct.unpack("<f", d[4:8])[0]
        rear_camber = struct.unpack("<f", d[8:12])[0]
        front_toe = struct.unpack("<f", d[12:16])[0]
        rear_toe = struct.unpack("<f", d[16:20])[0]
        front_susp = d[20]
        rear_susp = d[21]
        front_arb = d[22]
        rear_arb = d[23]
        front_height = d[24]
        rear_height = d[25]
        brake_pressure = d[26]
        brake_bias = d[27]
        rl_pressure = struct.unpack("<f", d[28:32])[0]
        rr_pressure = struct.unpack("<f", d[32:36])[0]
        fl_pressure = struct.unpack("<f", d[36:40])[0]
        fr_pressure = struct.unpack("<f", d[40:44])[0]
        ballast = d[44]
        fuel_load = struct.unpack("<f", d[45:49])[0]
        engine_braking = d[49] if len(d) > 49 else 0

        return CarSetup(
            front_wing=front_wing,
            rear_wing=rear_wing,
            on_throttle=on_throttle,
            off_throttle=off_throttle,
            front_camber=front_camber,
            rear_camber=rear_camber,
            front_toe=front_toe,
            rear_toe=rear_toe,
            front_suspension=front_susp,
            rear_suspension=rear_susp,
            front_anti_roll_bar=front_arb,
            rear_anti_roll_bar=rear_arb,
            front_suspension_height=front_height,
            rear_suspension_height=rear_height,
            brake_pressure=brake_pressure,
            brake_bias=brake_bias,
            rear_left_tyre_pressure=rl_pressure,
            rear_right_tyre_pressure=rr_pressure,
            front_left_tyre_pressure=fl_pressure,
            front_right_tyre_pressure=fr_pressure,
            ballast=ballast,
            fuel_load=fuel_load,
            engine_braking=engine_braking,
        )
    except (struct.error, ValueError, IndexError):
        return None


def parse_event(data: bytes) -> Optional[EventData]:
    """Parse event packet."""
    if len(data) < 29 + 4:
        return None

    try:
        d = data[29:]
        event_code = d[0:4].decode("utf-8", errors="replace")

        event = EventData(event_code=event_code)
        details = d[4:]

        if event_code == EventData.FASTEST_LAP and len(details) >= 5:
            event.vehicle_index = details[0]
            event.lap_time = struct.unpack("<f", details[1:5])[0]
        elif event_code in (EventData.RETIREMENT, EventData.TEAM_MATE_IN_PITS,
                            EventData.RACE_WINNER) and len(details) >= 1:
            event.vehicle_index = details[0]
        elif event_code == EventData.PENALTY_ISSUED and len(details) >= 7:
            event.penalty_type = details[0]
            event.infringement_type = details[1]
            event.vehicle_index = details[2]
            event.other_vehicle_index = details[3]
            event.time = details[4]
            event.lap_num = details[5]
            event.places_gained = details[6]
        elif event_code == EventData.SPEED_TRAP and len(details) >= 5:
            event.vehicle_index = details[0]
            event.speed = struct.unpack("<f", details[1:5])[0]
        elif event_code == EventData.OVERTAKE and len(details) >= 2:
            event.vehicle_index = details[0]
            event.other_vehicle_index = details[1]

        return event
    except (struct.error, ValueError, IndexError):
        return None


def parse_final_classification(data: bytes, car_index: int) -> Optional[FinalClassification]:
    """Parse final classification for specific car."""
    header_size = 29
    # First byte after header is m_numCars
    classification_size = 37
    offset = header_size + 1 + (car_index * classification_size)

    if len(data) < offset + classification_size:
        return None

    try:
        d = data[offset:offset + classification_size]

        position = d[0]
        num_laps = d[1]
        grid_position = d[2]
        points = d[3]
        num_pit_stops = d[4]
        result_status = d[5]
        best_lap = struct.unpack("<f", d[6:10])[0]
        total_time = struct.unpack("<d", d[10:18])[0]
        penalties_time = d[18]
        num_penalties = d[19]
        num_tyre_stints = d[20]
        tyre_actual = list(d[21:29])
        tyre_visual = list(d[29:37])

        return FinalClassification(
            position=position,
            num_laps=num_laps,
            grid_position=grid_position,
            points=points,
            num_pit_stops=num_pit_stops,
            result_status=result_status,
            best_lap_time=best_lap,
            total_race_time=total_time,
            penalties_time=penalties_time,
            num_penalties=num_penalties,
            num_tyre_stints=num_tyre_stints,
            tyre_stints_actual=tyre_actual[:num_tyre_stints],
            tyre_stints_visual=tyre_visual[:num_tyre_stints],
        )
    except (struct.error, ValueError, IndexError):
        return None


def parse_lobby_info(data: bytes, car_index: int) -> Optional[LobbyInfo]:
    """Parse lobby info for specific player."""
    header_size = 29
    # First byte after header is m_numPlayers
    lobby_size = 55
    offset = header_size + 1 + (car_index * lobby_size)

    if len(data) < offset + lobby_size:
        return None

    try:
        d = data[offset:offset + lobby_size]

        ai = bool(d[0])
        team_id = d[1]
        nationality = d[2]
        name = d[3:51].split(b"\x00")[0].decode("utf-8", errors="replace")
        ready_status = d[51]
        tech_level = struct.unpack("<H", d[53:55])[0] if len(d) >= 55 else 0

        return LobbyInfo(
            ai_controlled=ai,
            team_id=team_id,
            nationality=nationality,
            name=name,
            ready_status=ready_status,
            tech_level=tech_level,
        )
    except (struct.error, ValueError, IndexError):
        return None


def parse_session_history(data: bytes) -> Optional[SessionHistory]:
    """Parse session history packet."""
    if len(data) < 29 + 7:
        return None

    try:
        d = data[29:]

        car_idx = d[0]
        num_laps = d[1]
        num_tyre_stints = d[2]
        best_lap_num = d[3]
        best_s1_num = d[4]
        best_s2_num = d[5]
        best_s3_num = d[6]

        lap_history = []
        lap_offset = 7
        lap_size = 11

        for i in range(min(num_laps, 100)):
            lo = lap_offset + (i * lap_size)
            if lo + lap_size > len(d):
                break

            lap_time_ms = struct.unpack("<I", d[lo:lo + 4])[0]
            s1_ms = struct.unpack("<H", d[lo + 4:lo + 6])[0]
            s2_ms = struct.unpack("<H", d[lo + 6:lo + 8])[0]
            s3_ms = struct.unpack("<H", d[lo + 8:lo + 10])[0]
            flags = d[lo + 10]

            lap_history.append(LapHistoryItem(
                lap_time_ms=lap_time_ms,
                sector1_time_ms=s1_ms,
                sector2_time_ms=s2_ms,
                sector3_time_ms=s3_ms,
                lap_valid=bool(flags & 0x01),
                sector1_valid=bool(flags & 0x02),
                sector2_valid=bool(flags & 0x04),
                sector3_valid=bool(flags & 0x08),
            ))

        return SessionHistory(
            car_index=car_idx,
            num_laps=num_laps,
            num_tyre_stints=num_tyre_stints,
            best_lap_time_lap_num=best_lap_num,
            best_sector1_lap_num=best_s1_num,
            best_sector2_lap_num=best_s2_num,
            best_sector3_lap_num=best_s3_num,
            lap_history=lap_history,
        )
    except (struct.error, ValueError, IndexError):
        return None


def parse_tyre_sets(data: bytes) -> Optional[TyreSetData]:
    """Parse tyre sets packet."""
    if len(data) < 29 + 3:
        return None

    try:
        d = data[29:]

        car_idx = d[0]
        fitted_idx = d[2] if len(d) > 2 else 255

        tyre_sets = []
        set_offset = 3
        set_size = 9  # per tyre set record

        for i in range(20):
            so = set_offset + (i * set_size)
            if so + set_size > len(d):
                break

            actual_compound = d[so]
            visual_compound = d[so + 1]
            wear = d[so + 2]
            available = bool(d[so + 3])
            recommended_session = d[so + 4]
            life_span = d[so + 5]
            usable_life = d[so + 6]
            lap_delta = struct.unpack("<h", d[so + 7:so + 9])[0]
            fitted = bool(d[so + 2] == 0 and i == fitted_idx)

            tyre_sets.append(TyreSetInfo(
                actual_compound=actual_compound,
                visual_compound=visual_compound,
                wear=wear,
                available=available,
                recommended_session=recommended_session,
                life_span=life_span,
                usable_life=usable_life,
                lap_delta_time=lap_delta,
                fitted=(i == fitted_idx),
            ))

        return TyreSetData(
            car_index=car_idx,
            tyre_sets=tyre_sets,
            fitted_index=fitted_idx,
        )
    except (struct.error, ValueError, IndexError):
        return None


def _parse_time_trial_dataset(d: bytes) -> Optional[TimeTrialDataSet]:
    """Parse a single time trial data set (24 bytes)."""
    if len(d) < 24:
        return None

    car_idx = d[0]
    team_id = d[1]
    lap_time = struct.unpack("<I", d[2:6])[0]
    s1 = struct.unpack("<I", d[6:10])[0]
    s2 = struct.unpack("<I", d[10:14])[0]
    s3 = struct.unpack("<I", d[14:18])[0]
    tc = d[18]
    gearbox = d[19]
    abs_on = bool(d[20])
    equal_perf = bool(d[21])
    custom_setup = bool(d[22])
    valid = bool(d[23])

    return TimeTrialDataSet(
        car_index=car_idx,
        team_id=team_id,
        lap_time_ms=lap_time,
        sector1_time_ms=s1,
        sector2_time_ms=s2,
        sector3_time_ms=s3,
        traction_control=tc,
        gearbox_assist=gearbox,
        anti_lock_brakes=abs_on,
        equal_car_performance=equal_perf,
        custom_setup=custom_setup,
        valid=valid,
    )


def parse_time_trial(data: bytes) -> Optional[TimeTrial]:
    """Parse time trial packet."""
    if len(data) < 29 + 72:
        return None

    try:
        d = data[29:]

        player_best = _parse_time_trial_dataset(d[0:24])
        personal_best = _parse_time_trial_dataset(d[24:48])
        rival = _parse_time_trial_dataset(d[48:72])

        if not all([player_best, personal_best, rival]):
            return None

        return TimeTrial(
            player_session_best=player_best,
            personal_best=personal_best,
            rival=rival,
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
