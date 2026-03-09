"""InfluxDB publisher for F1 telemetry data."""

import os

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.domain.bucket_retention_rules import BucketRetentionRules

from .packets import PacketType


class InfluxDBPublisher:
    """Publishes F1 telemetry data to an InfluxDB 2.x instance."""

    def __init__(
        self,
        url: str = "http://localhost:8086",
        token: str | None = None,
        org: str | None = None,
        bucket: str = "f1",
    ):
        self._url = url
        self._token = token or os.environ.get("INFLUXDB_TOKEN", "")
        self._org = org or os.environ.get("INFLUXDB_ORG", "")
        self._bucket = bucket
        self._client: InfluxDBClient | None = None
        self._write_api = None
        # Session metadata cached from SESSION packets
        self._track = ""
        self._session_type = ""
        self._weather = ""

    def connect(self):
        """Create InfluxDB client with batched writes and auto-create bucket if missing."""
        self._client = InfluxDBClient(url=self._url, token=self._token, org=self._org)
        self._write_api = self._client.write_api(
            write_options=SYNCHRONOUS,
        )
        # Auto-create bucket if it doesn't exist
        buckets_api = self._client.buckets_api()
        existing = buckets_api.find_bucket_by_name(self._bucket)
        if existing is None:
            orgs = self._client.organizations_api().find_organizations(org=self._org)
            if orgs:
                buckets_api.create_bucket(
                    bucket_name=self._bucket,
                    org_id=orgs[0].id,
                    retention_rules=BucketRetentionRules(type="expire", every_seconds=0),
                )

    def close(self):
        """Flush and close write API and client."""
        if self._write_api:
            self._write_api.close()
            self._write_api = None
        if self._client:
            self._client.close()
            self._client = None

    def register(self, dispatcher):
        """Register all handlers on an F1Dispatcher instance."""
        dispatcher.on(PacketType.MOTION, self.handle_motion)
        dispatcher.on(PacketType.SESSION, self.handle_session)
        dispatcher.on(PacketType.LAP_DATA, self.handle_lap_data)
        dispatcher.on(PacketType.EVENT, self.handle_event)
        dispatcher.on(PacketType.PARTICIPANTS, self.handle_participants)
        dispatcher.on(PacketType.CAR_SETUPS, self.handle_car_setup)
        dispatcher.on(PacketType.CAR_TELEMETRY, self.handle_car_telemetry)
        dispatcher.on(PacketType.CAR_STATUS, self.handle_car_status)
        dispatcher.on(PacketType.FINAL_CLASSIFICATION, self.handle_final_classification)
        dispatcher.on(PacketType.LOBBY_INFO, self.handle_lobby_info)
        dispatcher.on(PacketType.CAR_DAMAGE, self.handle_car_damage)
        dispatcher.on(PacketType.SESSION_HISTORY, self.handle_session_history)
        dispatcher.on(PacketType.TYRE_SETS, self.handle_tyre_sets)
        dispatcher.on(PacketType.MOTION_EX, self.handle_motion_ex)
        dispatcher.on(PacketType.TIME_TRIAL, self.handle_time_trial)

    def _base_point(self, measurement: str, header) -> Point:
        """Create a Point with common tags."""
        p = Point(measurement)
        p.tag("session_uid", str(header.session_uid))
        if self._track:
            p.tag("track", self._track)
        if self._session_type:
            p.tag("session_type", self._session_type)
        return p

    def _write(self, point: Point):
        if self._write_api:
            self._write_api.write(bucket=self._bucket, record=point)

    # -- Handlers --

    def handle_session(self, header, data):
        self._track = data.track.name if hasattr(data.track, "name") else str(data.track)
        self._session_type = data.session_type.name if hasattr(data.session_type, "name") else str(data.session_type)
        self._weather = data.weather.name if hasattr(data.weather, "name") else str(data.weather)

        p = self._base_point("f1_session", header)
        p.field("weather", self._weather)
        p.field("track_temperature", data.track_temperature)
        p.field("air_temperature", data.air_temperature)
        p.field("total_laps", data.total_laps)
        p.field("track_length", data.track_length)
        p.field("session_time_left", data.session_time_left)
        p.field("session_duration", data.session_duration)
        p.field("pit_speed_limit", data.pit_speed_limit)
        p.field("game_paused", data.game_paused)
        p.field("safety_car_status", data.safety_car_status)
        p.field("forecast_accuracy", data.forecast_accuracy)
        p.field("ai_difficulty", data.ai_difficulty)
        self._write(p)

    def handle_car_telemetry(self, header, data):
        p = self._base_point("f1_telemetry", header)
        p.field("speed", data.speed)
        p.field("throttle", data.throttle)
        p.field("steer", data.steer)
        p.field("brake", data.brake)
        p.field("clutch", data.clutch)
        p.field("gear", data.gear)
        p.field("engine_rpm", data.engine_rpm)
        p.field("drs", data.drs)
        p.field("rev_lights_percent", data.rev_lights_percent)
        p.field("engine_temp", data.engine_temperature)
        # Brake temps
        p.field("brake_temp_rl", data.brake_temperature.rear_left)
        p.field("brake_temp_rr", data.brake_temperature.rear_right)
        p.field("brake_temp_fl", data.brake_temperature.front_left)
        p.field("brake_temp_fr", data.brake_temperature.front_right)
        # Tyre surface temps
        p.field("tyre_surface_temp_rl", data.tyre_surface_temperature.rear_left)
        p.field("tyre_surface_temp_rr", data.tyre_surface_temperature.rear_right)
        p.field("tyre_surface_temp_fl", data.tyre_surface_temperature.front_left)
        p.field("tyre_surface_temp_fr", data.tyre_surface_temperature.front_right)
        # Tyre inner temps
        p.field("tyre_inner_temp_rl", data.tyre_inner_temperature.rear_left)
        p.field("tyre_inner_temp_rr", data.tyre_inner_temperature.rear_right)
        p.field("tyre_inner_temp_fl", data.tyre_inner_temperature.front_left)
        p.field("tyre_inner_temp_fr", data.tyre_inner_temperature.front_right)
        # Tyre pressures
        p.field("tyre_pressure_rl", data.tyre_pressure.rear_left)
        p.field("tyre_pressure_rr", data.tyre_pressure.rear_right)
        p.field("tyre_pressure_fl", data.tyre_pressure.front_left)
        p.field("tyre_pressure_fr", data.tyre_pressure.front_right)
        self._write(p)

    def handle_lap_data(self, header, data):
        p = self._base_point("f1_lap", header)
        p.field("last_lap_time_ms", data.last_lap_time_ms)
        p.field("current_lap_time_ms", data.current_lap_time_ms)
        p.field("sector1_time_ms", data.sector1_time_ms)
        p.field("sector2_time_ms", data.sector2_time_ms)
        p.field("delta_to_car_in_front_ms", data.delta_to_car_in_front_ms)
        p.field("delta_to_race_leader_ms", data.delta_to_race_leader_ms)
        p.field("lap_distance", data.lap_distance)
        p.field("total_distance", data.total_distance)
        p.field("safety_car_delta", data.safety_car_delta)
        p.field("position", data.position)
        p.field("current_lap", data.current_lap)
        p.field("pit_status", data.pit_status.value if hasattr(data.pit_status, "value") else int(data.pit_status))
        p.field("num_pit_stops", data.num_pit_stops)
        p.field("sector", data.sector)
        p.field("current_lap_invalid", data.current_lap_invalid)
        p.field("penalties", data.penalties)
        p.field("total_warnings", data.total_warnings)
        p.field("corner_cutting_warnings", data.corner_cutting_warnings)
        p.field("grid_position", data.grid_position)
        p.field("driver_status", data.driver_status)
        p.field("result_status", data.result_status)
        self._write(p)

    def handle_motion(self, header, data):
        p = self._base_point("f1_motion", header)
        p.field("world_pos_x", data.world_position.x)
        p.field("world_pos_y", data.world_position.y)
        p.field("world_pos_z", data.world_position.z)
        p.field("velocity_x", data.world_velocity.x)
        p.field("velocity_y", data.world_velocity.y)
        p.field("velocity_z", data.world_velocity.z)
        p.field("forward_x", data.world_forward_dir.x)
        p.field("forward_y", data.world_forward_dir.y)
        p.field("forward_z", data.world_forward_dir.z)
        p.field("right_x", data.world_right_dir.x)
        p.field("right_y", data.world_right_dir.y)
        p.field("right_z", data.world_right_dir.z)
        p.field("g_force_lat", data.g_force_lateral)
        p.field("g_force_lon", data.g_force_longitudinal)
        p.field("g_force_vert", data.g_force_vertical)
        p.field("yaw", data.yaw)
        p.field("pitch", data.pitch)
        p.field("roll", data.roll)
        self._write(p)

    def handle_car_status(self, header, data):
        p = self._base_point("f1_status", header)
        p.field("traction_control", data.traction_control)
        p.field("anti_lock_brakes", data.anti_lock_brakes)
        p.field("fuel_mix", data.fuel_mix.value if hasattr(data.fuel_mix, "value") else int(data.fuel_mix))
        p.field("front_brake_bias", data.front_brake_bias)
        p.field("pit_limiter", data.pit_limiter)
        p.field("fuel_remaining", data.fuel_remaining)
        p.field("fuel_capacity", data.fuel_capacity)
        p.field("fuel_remaining_laps", data.fuel_remaining_laps)
        p.field("max_rpm", data.max_rpm)
        p.field("idle_rpm", data.idle_rpm)
        p.field("max_gears", data.max_gears)
        p.field("drs_allowed", data.drs_allowed)
        p.field("drs_activation_distance", data.drs_activation_distance)
        p.field("tyre_compound", data.actual_tyre_compound.name if hasattr(data.actual_tyre_compound, "name") else str(data.actual_tyre_compound))
        p.field("visual_tyre_compound", data.visual_tyre_compound)
        p.field("tyre_age_laps", data.tyre_age_laps)
        p.field("vehicle_flag", data.vehicle_flag.value if hasattr(data.vehicle_flag, "value") else int(data.vehicle_flag))
        p.field("engine_power_ice", data.engine_power_ice)
        p.field("engine_power_mguk", data.engine_power_mguk)
        p.field("ers_store_energy", data.ers_store_energy)
        p.field("ers_deploy_mode", data.ers_deploy_mode.value if hasattr(data.ers_deploy_mode, "value") else int(data.ers_deploy_mode))
        p.field("ers_harvested_this_lap_mguk", data.ers_harvested_this_lap_mguk)
        p.field("ers_harvested_this_lap_mguh", data.ers_harvested_this_lap_mguh)
        p.field("ers_deployed_this_lap", data.ers_deployed_this_lap)
        self._write(p)

    def handle_car_damage(self, header, data):
        p = self._base_point("f1_damage", header)
        # Tyre wear
        p.field("tyre_wear_rl", data.tyre_wear.rear_left)
        p.field("tyre_wear_rr", data.tyre_wear.rear_right)
        p.field("tyre_wear_fl", data.tyre_wear.front_left)
        p.field("tyre_wear_fr", data.tyre_wear.front_right)
        # Tyre damage
        p.field("tyre_damage_rl", data.tyre_damage.rear_left)
        p.field("tyre_damage_rr", data.tyre_damage.rear_right)
        p.field("tyre_damage_fl", data.tyre_damage.front_left)
        p.field("tyre_damage_fr", data.tyre_damage.front_right)
        # Brake damage
        p.field("brakes_damage_rl", data.brakes_damage.rear_left)
        p.field("brakes_damage_rr", data.brakes_damage.rear_right)
        p.field("brakes_damage_fl", data.brakes_damage.front_left)
        p.field("brakes_damage_fr", data.brakes_damage.front_right)
        # Aero damage
        p.field("fl_wing_damage", data.front_left_wing_damage)
        p.field("fr_wing_damage", data.front_right_wing_damage)
        p.field("rear_wing_damage", data.rear_wing_damage)
        p.field("floor_damage", data.floor_damage)
        p.field("diffuser_damage", data.diffuser_damage)
        p.field("sidepod_damage", data.sidepod_damage)
        # Faults
        p.field("drs_fault", data.drs_fault)
        p.field("ers_fault", data.ers_fault)
        # Drivetrain
        p.field("gearbox_damage", data.gearbox_damage)
        p.field("engine_damage", data.engine_damage)
        p.field("engine_mguh_wear", data.engine_mguh_wear)
        p.field("engine_es_wear", data.engine_es_wear)
        p.field("engine_ce_wear", data.engine_ce_wear)
        p.field("engine_ice_wear", data.engine_ice_wear)
        p.field("engine_mguk_wear", data.engine_mguk_wear)
        p.field("engine_tc_wear", data.engine_tc_wear)
        p.field("engine_blown", data.engine_blown)
        p.field("engine_seized", data.engine_seized)
        self._write(p)

    def handle_event(self, header, data):
        p = self._base_point("f1_event", header)
        p.tag("event_code", data.event_code)
        p.field("vehicle_index", data.vehicle_index)
        p.field("lap_time", data.lap_time)
        p.field("speed", data.speed)
        p.field("penalty_type", data.penalty_type)
        p.field("infringement_type", data.infringement_type)
        p.field("other_vehicle_index", data.other_vehicle_index)
        p.field("time", data.time)
        p.field("lap_num", data.lap_num)
        p.field("places_gained", data.places_gained)
        self._write(p)

    def handle_participants(self, header, data):
        p = self._base_point("f1_participant", header)
        p.field("ai_controlled", data.ai_controlled)
        p.field("driver_id", data.driver_id)
        p.field("network_id", data.network_id)
        p.field("team", data.team.name if hasattr(data.team, "name") else str(data.team))
        p.field("race_number", data.race_number)
        p.field("nationality", data.nationality)
        p.field("name", data.name)
        p.field("telemetry_public", data.telemetry_public)
        self._write(p)

    def handle_car_setup(self, header, data):
        p = self._base_point("f1_setup", header)
        p.field("front_wing", data.front_wing)
        p.field("rear_wing", data.rear_wing)
        p.field("on_throttle", data.on_throttle)
        p.field("off_throttle", data.off_throttle)
        p.field("front_camber", data.front_camber)
        p.field("rear_camber", data.rear_camber)
        p.field("front_toe", data.front_toe)
        p.field("rear_toe", data.rear_toe)
        p.field("front_suspension", data.front_suspension)
        p.field("rear_suspension", data.rear_suspension)
        p.field("front_anti_roll_bar", data.front_anti_roll_bar)
        p.field("rear_anti_roll_bar", data.rear_anti_roll_bar)
        p.field("front_suspension_height", data.front_suspension_height)
        p.field("rear_suspension_height", data.rear_suspension_height)
        p.field("brake_pressure", data.brake_pressure)
        p.field("brake_bias", data.brake_bias)
        p.field("rear_left_tyre_pressure", data.rear_left_tyre_pressure)
        p.field("rear_right_tyre_pressure", data.rear_right_tyre_pressure)
        p.field("front_left_tyre_pressure", data.front_left_tyre_pressure)
        p.field("front_right_tyre_pressure", data.front_right_tyre_pressure)
        p.field("ballast", data.ballast)
        p.field("fuel_load", data.fuel_load)
        p.field("engine_braking", data.engine_braking)
        self._write(p)

    def handle_final_classification(self, header, data):
        p = self._base_point("f1_classification", header)
        p.field("position", data.position)
        p.field("num_laps", data.num_laps)
        p.field("grid_position", data.grid_position)
        p.field("points", data.points)
        p.field("num_pit_stops", data.num_pit_stops)
        p.field("result_status", data.result_status)
        p.field("best_lap_time", data.best_lap_time)
        p.field("total_race_time", data.total_race_time)
        p.field("penalties_time", data.penalties_time)
        p.field("num_penalties", data.num_penalties)
        p.field("num_tyre_stints", data.num_tyre_stints)
        self._write(p)

    def handle_lobby_info(self, header, data):
        p = self._base_point("f1_lobby", header)
        p.field("ai_controlled", data.ai_controlled)
        p.field("team_id", data.team_id)
        p.field("nationality", data.nationality)
        p.field("name", data.name)
        p.field("ready_status", data.ready_status)
        self._write(p)

    def handle_session_history(self, header, data):
        p = self._base_point("f1_session_history", header)
        p.field("car_index", data.car_index)
        p.field("num_laps", data.num_laps)
        p.field("num_tyre_stints", data.num_tyre_stints)
        p.field("best_lap_time_lap_num", data.best_lap_time_lap_num)
        p.field("best_sector1_lap_num", data.best_sector1_lap_num)
        p.field("best_sector2_lap_num", data.best_sector2_lap_num)
        p.field("best_sector3_lap_num", data.best_sector3_lap_num)
        # Write individual lap history entries as separate points
        for i, lap in enumerate(data.lap_history):
            lp = self._base_point("f1_lap_history", header)
            lp.field("lap_number", i + 1)
            lp.field("lap_time_ms", lap.lap_time_ms)
            lp.field("sector1_time_ms", lap.sector1_time_ms)
            lp.field("sector2_time_ms", lap.sector2_time_ms)
            lp.field("sector3_time_ms", lap.sector3_time_ms)
            lp.field("lap_valid", lap.lap_valid)
            lp.field("sector1_valid", lap.sector1_valid)
            lp.field("sector2_valid", lap.sector2_valid)
            lp.field("sector3_valid", lap.sector3_valid)
            self._write(lp)
        self._write(p)

    def handle_tyre_sets(self, header, data):
        p = self._base_point("f1_tyre_sets", header)
        p.field("car_index", data.car_index)
        p.field("fitted_index", data.fitted_index)
        self._write(p)
        # Write each tyre set as a separate point
        for i, ts in enumerate(data.tyre_sets):
            tp = self._base_point("f1_tyre_set", header)
            tp.field("set_index", i)
            tp.field("actual_compound", ts.actual_compound)
            tp.field("visual_compound", ts.visual_compound)
            tp.field("wear", ts.wear)
            tp.field("available", ts.available)
            tp.field("recommended_session", ts.recommended_session)
            tp.field("life_span", ts.life_span)
            tp.field("usable_life", ts.usable_life)
            tp.field("lap_delta_time", ts.lap_delta_time)
            tp.field("fitted", ts.fitted)
            self._write(tp)

    def handle_motion_ex(self, header, data):
        p = self._base_point("f1_motion_ex", header)
        # Suspension
        p.field("suspension_pos_rl", data.suspension_position.rear_left)
        p.field("suspension_pos_rr", data.suspension_position.rear_right)
        p.field("suspension_pos_fl", data.suspension_position.front_left)
        p.field("suspension_pos_fr", data.suspension_position.front_right)
        p.field("suspension_vel_rl", data.suspension_velocity.rear_left)
        p.field("suspension_vel_rr", data.suspension_velocity.rear_right)
        p.field("suspension_vel_fl", data.suspension_velocity.front_left)
        p.field("suspension_vel_fr", data.suspension_velocity.front_right)
        p.field("suspension_accel_rl", data.suspension_acceleration.rear_left)
        p.field("suspension_accel_rr", data.suspension_acceleration.rear_right)
        p.field("suspension_accel_fl", data.suspension_acceleration.front_left)
        p.field("suspension_accel_fr", data.suspension_acceleration.front_right)
        # Wheel data
        p.field("wheel_speed_rl", data.wheel_speed.rear_left)
        p.field("wheel_speed_rr", data.wheel_speed.rear_right)
        p.field("wheel_speed_fl", data.wheel_speed.front_left)
        p.field("wheel_speed_fr", data.wheel_speed.front_right)
        p.field("wheel_slip_ratio_rl", data.wheel_slip_ratio.rear_left)
        p.field("wheel_slip_ratio_rr", data.wheel_slip_ratio.rear_right)
        p.field("wheel_slip_ratio_fl", data.wheel_slip_ratio.front_left)
        p.field("wheel_slip_ratio_fr", data.wheel_slip_ratio.front_right)
        p.field("wheel_slip_angle_rl", data.wheel_slip_angle.rear_left)
        p.field("wheel_slip_angle_rr", data.wheel_slip_angle.rear_right)
        p.field("wheel_slip_angle_fl", data.wheel_slip_angle.front_left)
        p.field("wheel_slip_angle_fr", data.wheel_slip_angle.front_right)
        # Forces
        p.field("wheel_lat_force_rl", data.wheel_lat_force.rear_left)
        p.field("wheel_lat_force_rr", data.wheel_lat_force.rear_right)
        p.field("wheel_lat_force_fl", data.wheel_lat_force.front_left)
        p.field("wheel_lat_force_fr", data.wheel_lat_force.front_right)
        p.field("wheel_long_force_rl", data.wheel_long_force.rear_left)
        p.field("wheel_long_force_rr", data.wheel_long_force.rear_right)
        p.field("wheel_long_force_fl", data.wheel_long_force.front_left)
        p.field("wheel_long_force_fr", data.wheel_long_force.front_right)
        p.field("wheel_vert_force_rl", data.wheel_vert_force.rear_left)
        p.field("wheel_vert_force_rr", data.wheel_vert_force.rear_right)
        p.field("wheel_vert_force_fl", data.wheel_vert_force.front_left)
        p.field("wheel_vert_force_fr", data.wheel_vert_force.front_right)
        # Other
        p.field("height_of_cog_above_ground", data.height_of_cog_above_ground)
        p.field("local_velocity_x", data.local_velocity.x)
        p.field("local_velocity_y", data.local_velocity.y)
        p.field("local_velocity_z", data.local_velocity.z)
        p.field("angular_velocity_x", data.angular_velocity.x)
        p.field("angular_velocity_y", data.angular_velocity.y)
        p.field("angular_velocity_z", data.angular_velocity.z)
        p.field("angular_accel_x", data.angular_acceleration.x)
        p.field("angular_accel_y", data.angular_acceleration.y)
        p.field("angular_accel_z", data.angular_acceleration.z)
        p.field("front_wheels_angle", data.front_wheels_angle)
        self._write(p)

    def handle_time_trial(self, header, data):
        for label, entry in [
            ("session_best", data.player_session_best),
            ("personal_best", data.personal_best),
            ("rival", data.rival),
        ]:
            p = self._base_point("f1_time_trial", header)
            p.tag("entry_type", label)
            p.field("car_index", entry.car_index)
            p.field("team_id", entry.team_id)
            p.field("lap_time_ms", entry.lap_time_ms)
            p.field("sector1_time_ms", entry.sector1_time_ms)
            p.field("sector2_time_ms", entry.sector2_time_ms)
            p.field("sector3_time_ms", entry.sector3_time_ms)
            p.field("traction_control", entry.traction_control)
            p.field("gearbox_assist", entry.gearbox_assist)
            p.field("anti_lock_brakes", entry.anti_lock_brakes)
            p.field("equal_car_performance", entry.equal_car_performance)
            p.field("custom_setup", entry.custom_setup)
            p.field("valid", entry.valid)
            self._write(p)
