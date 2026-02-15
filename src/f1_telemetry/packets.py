"""F1 Telemetry Packet Data Types - Clean Python dataclasses."""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional


# =============================================================================
# ENUMS
# =============================================================================

class PacketType(IntEnum):
    MOTION = 0
    SESSION = 1
    LAP_DATA = 2
    EVENT = 3
    PARTICIPANTS = 4
    CAR_SETUPS = 5
    CAR_TELEMETRY = 6
    CAR_STATUS = 7
    FINAL_CLASSIFICATION = 8
    LOBBY_INFO = 9
    CAR_DAMAGE = 10
    SESSION_HISTORY = 11
    TYRE_SETS = 12
    MOTION_EX = 13
    TIME_TRIAL = 14


class Weather(IntEnum):
    CLEAR = 0
    LIGHT_CLOUD = 1
    OVERCAST = 2
    LIGHT_RAIN = 3
    HEAVY_RAIN = 4
    STORM = 5


class SessionType(IntEnum):
    UNKNOWN = 0
    P1 = 1
    P2 = 2
    P3 = 3
    SHORT_P = 4
    Q1 = 5
    Q2 = 6
    Q3 = 7
    SHORT_Q = 8
    OSQ = 9
    RACE = 10
    RACE_2 = 11
    RACE_3 = 12
    TIME_TRIAL = 13


class Track(IntEnum):
    MELBOURNE = 0
    PAUL_RICARD = 1
    SHANGHAI = 2
    BAHRAIN = 3
    CATALUNYA = 4
    MONACO = 5
    MONTREAL = 6
    SILVERSTONE = 7
    HOCKENHEIM = 8
    HUNGARORING = 9
    SPA = 10
    MONZA = 11
    SINGAPORE = 12
    SUZUKA = 13
    ABU_DHABI = 14
    TEXAS = 15
    BRAZIL = 16
    AUSTRIA = 17
    SOCHI = 18
    MEXICO = 19
    BAKU = 20
    BAHRAIN_SHORT = 21
    SILVERSTONE_SHORT = 22
    TEXAS_SHORT = 23
    SUZUKA_SHORT = 24
    HANOI = 25
    ZANDVOORT = 26
    IMOLA = 27
    PORTIMAO = 28
    JEDDAH = 29
    MIAMI = 30
    LAS_VEGAS = 31
    LOSAIL = 32


class TyreCompound(IntEnum):
    SOFT = 16
    MEDIUM = 17
    HARD = 18
    INTER = 7
    WET = 8


class FuelMix(IntEnum):
    LEAN = 0
    STANDARD = 1
    RICH = 2
    MAX = 3


class ERSMode(IntEnum):
    NONE = 0
    MEDIUM = 1
    HOTLAP = 2
    OVERTAKE = 3


class VehicleFlag(IntEnum):
    NONE = 0
    GREEN = 1
    BLUE = 2
    YELLOW = 3
    RED = 4


class PitStatus(IntEnum):
    NONE = 0
    PITTING = 1
    IN_PIT_AREA = 2


class Team(IntEnum):
    MERCEDES = 0
    FERRARI = 1
    RED_BULL = 2
    WILLIAMS = 3
    ASTON_MARTIN = 4
    ALPINE = 5
    ALPHA_TAURI = 6
    HAAS = 7
    MCLAREN = 8
    ALFA_ROMEO = 9


# =============================================================================
# HELPER DATACLASSES
# =============================================================================

@dataclass
class TyreData:
    """Tyre data for all 4 wheels (RL, RR, FL, FR)."""
    rear_left: float
    rear_right: float
    front_left: float
    front_right: float

    def __repr__(self):
        return f"TyreData(FL={self.front_left}, FR={self.front_right}, RL={self.rear_left}, RR={self.rear_right})"


@dataclass
class Vector3:
    """3D vector."""
    x: float
    y: float
    z: float


# =============================================================================
# PACKET HEADER
# =============================================================================

@dataclass
class PacketHeader:
    """F1 UDP packet header (29 bytes)."""
    packet_format: int          # Game year (2023, 2024, 2025)
    game_year: int
    game_major_version: int
    game_minor_version: int
    packet_version: int
    packet_type: PacketType
    session_uid: int
    session_time: float
    frame_identifier: int
    overall_frame_identifier: int
    player_car_index: int
    secondary_player_car_index: int


# =============================================================================
# SESSION DATA
# =============================================================================

@dataclass
class SessionData:
    """Session information - track, weather, session type."""
    weather: Weather
    track_temperature: int          # Celsius
    air_temperature: int            # Celsius
    total_laps: int
    track_length: int               # Meters
    session_type: SessionType
    track: Track
    formula: int
    session_time_left: int          # Seconds
    session_duration: int           # Seconds
    pit_speed_limit: int            # km/h
    game_paused: bool
    is_spectating: bool
    spectator_car_index: int
    sli_pro_support: bool
    num_marshal_zones: int
    safety_car_status: int
    network_game: bool
    num_weather_forecast_samples: int
    forecast_accuracy: int
    ai_difficulty: int
    season_link_identifier: int
    weekend_link_identifier: int
    session_link_identifier: int
    pit_stop_window_ideal_lap: int
    pit_stop_window_latest_lap: int
    pit_stop_rejoin_position: int
    steering_assist: bool
    braking_assist: int
    gearbox_assist: int
    pit_assist: bool
    pit_release_assist: bool
    ers_assist: bool
    drs_assist: bool
    dynamic_racing_line: int
    dynamic_racing_line_type: int
    game_mode: int
    rule_set: int
    time_of_day: int
    session_length: int

    @property
    def track_name(self) -> str:
        """Get human-readable track name."""
        names = {
            Track.SPA: "Spa-Francorchamps (Belgium)",
            Track.MONZA: "Monza (Italy)",
            Track.SILVERSTONE: "Silverstone (UK)",
            Track.MONACO: "Monaco",
            Track.SUZUKA: "Suzuka (Japan)",
            Track.MELBOURNE: "Melbourne (Australia)",
            Track.BAHRAIN: "Bahrain",
            Track.JEDDAH: "Jeddah (Saudi Arabia)",
            Track.MIAMI: "Miami (USA)",
            Track.IMOLA: "Imola (Italy)",
            Track.MONTREAL: "Montreal (Canada)",
            Track.CATALUNYA: "Barcelona (Spain)",
            Track.AUSTRIA: "Red Bull Ring (Austria)",
            Track.HUNGARORING: "Hungaroring (Hungary)",
            Track.ZANDVOORT: "Zandvoort (Netherlands)",
            Track.SINGAPORE: "Singapore",
            Track.TEXAS: "Austin (USA)",
            Track.MEXICO: "Mexico City",
            Track.BRAZIL: "Interlagos (Brazil)",
            Track.LAS_VEGAS: "Las Vegas (USA)",
            Track.LOSAIL: "Losail (Qatar)",
            Track.ABU_DHABI: "Abu Dhabi",
        }
        return names.get(self.track, self.track.name if isinstance(self.track, Track) else f"Unknown ({self.track})")

    @property
    def weather_name(self) -> str:
        """Get human-readable weather name."""
        return self.weather.name.replace("_", " ").title() if isinstance(self.weather, Weather) else str(self.weather)

    @property
    def session_type_name(self) -> str:
        """Get human-readable session type."""
        return self.session_type.name.replace("_", " ").title() if isinstance(self.session_type, SessionType) else str(self.session_type)


# =============================================================================
# LAP DATA
# =============================================================================

@dataclass
class LapData:
    """Lap timing information for a car."""
    last_lap_time_ms: int
    current_lap_time_ms: int
    sector1_time_ms: int
    sector2_time_ms: int
    delta_to_car_in_front_ms: int
    delta_to_race_leader_ms: int
    lap_distance: float             # Meters into lap
    total_distance: float           # Total meters traveled
    safety_car_delta: float
    position: int                   # Race position
    current_lap: int
    pit_status: PitStatus
    num_pit_stops: int
    sector: int                     # 0 = sector1, 1 = sector2, 2 = sector3
    current_lap_invalid: bool
    penalties: int                  # Accumulated time penalties (seconds)
    total_warnings: int
    corner_cutting_warnings: int
    num_unserved_drive_through: int
    num_unserved_stop_go: int
    grid_position: int
    driver_status: int
    result_status: int
    pit_lane_timer_active: bool
    pit_lane_time_in_lane_ms: int
    pit_stop_timer_ms: int
    pit_stop_should_serve_penalty: bool

    @property
    def last_lap_time(self) -> str:
        """Format last lap time as M:SS.mmm"""
        if self.last_lap_time_ms == 0:
            return "--:--.---"
        mins = self.last_lap_time_ms // 60000
        secs = (self.last_lap_time_ms % 60000) / 1000
        return f"{mins}:{secs:06.3f}"

    @property
    def current_lap_time(self) -> str:
        """Format current lap time as M:SS.mmm"""
        mins = self.current_lap_time_ms // 60000
        secs = (self.current_lap_time_ms % 60000) / 1000
        return f"{mins}:{secs:06.3f}"

    @property
    def sector_number(self) -> int:
        """Get 1-indexed sector number."""
        return self.sector + 1


# =============================================================================
# CAR TELEMETRY
# =============================================================================

@dataclass
class CarTelemetry:
    """Live car telemetry data."""
    speed: int                      # km/h
    throttle: float                 # 0.0 - 1.0
    steer: float                    # -1.0 (left) to 1.0 (right)
    brake: float                    # 0.0 - 1.0
    clutch: int                     # 0 - 100
    gear: int                       # -1 = R, 0 = N, 1-8
    engine_rpm: int
    drs: bool
    rev_lights_percent: int         # 0 - 100
    rev_lights_bit_value: int
    brake_temperature: TyreData     # Celsius
    tyre_surface_temperature: TyreData  # Celsius
    tyre_inner_temperature: TyreData    # Celsius
    engine_temperature: int         # Celsius
    tyre_pressure: TyreData         # PSI
    surface_type: tuple             # Track surface type per wheel

    @property
    def gear_str(self) -> str:
        """Get gear as string (R, N, 1-8)."""
        if self.gear == -1:
            return "R"
        elif self.gear == 0:
            return "N"
        return str(self.gear)

    @property
    def throttle_percent(self) -> float:
        return round(self.throttle * 100, 1)

    @property
    def brake_percent(self) -> float:
        return round(self.brake * 100, 1)


# =============================================================================
# CAR STATUS
# =============================================================================

@dataclass
class CarStatus:
    """Car status - fuel, ERS, tyres, flags."""
    traction_control: int           # 0 = off, 1 = medium, 2 = full
    anti_lock_brakes: bool
    fuel_mix: FuelMix
    front_brake_bias: int           # Percentage
    pit_limiter: bool
    fuel_remaining: float           # kg
    fuel_capacity: float            # kg
    fuel_remaining_laps: float
    max_rpm: int
    idle_rpm: int
    max_gears: int
    drs_allowed: bool
    drs_activation_distance: int    # Meters
    actual_tyre_compound: TyreCompound
    visual_tyre_compound: int
    tyre_age_laps: int
    vehicle_flag: VehicleFlag
    engine_power_ice: float
    engine_power_mguk: float
    ers_store_energy: float         # Joules
    ers_deploy_mode: ERSMode
    ers_harvested_this_lap_mguk: float
    ers_harvested_this_lap_mguh: float
    ers_deployed_this_lap: float
    network_paused: bool

    @property
    def fuel_mix_name(self) -> str:
        return self.fuel_mix.name.title() if isinstance(self.fuel_mix, FuelMix) else str(self.fuel_mix)

    @property
    def tyre_compound_name(self) -> str:
        return self.actual_tyre_compound.name.title() if isinstance(self.actual_tyre_compound, TyreCompound) else f"Unknown ({self.actual_tyre_compound})"

    @property
    def ers_percent(self) -> float:
        """ERS battery percentage (4MJ max)."""
        return round((self.ers_store_energy / 4000000) * 100, 1)


# =============================================================================
# CAR DAMAGE
# =============================================================================

@dataclass
class CarDamage:
    """Car damage status."""
    tyre_wear: TyreData             # Percentage
    tyre_damage: TyreData           # Percentage
    brakes_damage: TyreData         # Percentage
    front_left_wing_damage: int     # Percentage
    front_right_wing_damage: int    # Percentage
    rear_wing_damage: int           # Percentage
    floor_damage: int               # Percentage
    diffuser_damage: int            # Percentage
    sidepod_damage: int             # Percentage
    drs_fault: bool
    ers_fault: bool
    gearbox_damage: int             # Percentage
    engine_damage: int              # Percentage
    engine_mguh_wear: int           # Percentage
    engine_es_wear: int             # Percentage
    engine_ce_wear: int             # Percentage
    engine_ice_wear: int            # Percentage
    engine_mguk_wear: int           # Percentage
    engine_tc_wear: int             # Percentage
    engine_blown: bool
    engine_seized: bool

    @property
    def has_damage(self) -> bool:
        """Check if car has any significant damage."""
        return (
            self.front_left_wing_damage > 0 or
            self.front_right_wing_damage > 0 or
            self.rear_wing_damage > 0 or
            self.floor_damage > 0 or
            self.gearbox_damage > 0 or
            self.engine_damage > 0 or
            self.drs_fault or
            self.ers_fault
        )


# =============================================================================
# CAR MOTION
# =============================================================================

@dataclass
class CarMotion:
    """Car motion/physics data."""
    world_position: Vector3         # World coordinates
    world_velocity: Vector3         # Velocity in world coords
    world_forward_dir: Vector3      # Normalized forward direction
    world_right_dir: Vector3        # Normalized right direction
    g_force_lateral: float
    g_force_longitudinal: float
    g_force_vertical: float
    yaw: float                      # Radians
    pitch: float                    # Radians
    roll: float                     # Radians


# =============================================================================
# MOTION EXTENDED
# =============================================================================

@dataclass
class MotionEx:
    """Extended motion data - suspension, wheels."""
    suspension_position: TyreData   # Meters
    suspension_velocity: TyreData   # m/s
    suspension_acceleration: TyreData
    wheel_speed: TyreData           # m/s
    wheel_slip_ratio: TyreData
    wheel_slip_angle: TyreData
    wheel_lat_force: TyreData
    wheel_long_force: TyreData
    height_of_cog_above_ground: float
    local_velocity: Vector3
    angular_velocity: Vector3
    angular_acceleration: Vector3
    front_wheels_angle: float       # Radians
    wheel_vert_force: TyreData


# =============================================================================
# PARTICIPANT DATA
# =============================================================================

@dataclass
class ParticipantData:
    """Driver/participant information."""
    ai_controlled: bool
    driver_id: int
    network_id: int
    team: Team
    my_team: bool
    race_number: int
    nationality: int
    name: str
    telemetry_public: bool
    show_online_names: bool
    tech_level: int
    platform: int

    @property
    def team_name(self) -> str:
        return self.team.name.replace("_", " ").title() if isinstance(self.team, Team) else f"Unknown ({self.team})"


# =============================================================================
# CAR SETUP
# =============================================================================

@dataclass
class CarSetup:
    """Car setup data."""
    front_wing: int
    rear_wing: int
    on_throttle: int                # Differential %
    off_throttle: int               # Differential %
    front_camber: float
    rear_camber: float
    front_toe: float
    rear_toe: float
    front_suspension: int
    rear_suspension: int
    front_anti_roll_bar: int
    rear_anti_roll_bar: int
    front_suspension_height: int
    rear_suspension_height: int
    brake_pressure: int             # Percentage
    brake_bias: int                 # Percentage
    rear_left_tyre_pressure: float  # PSI
    rear_right_tyre_pressure: float
    front_left_tyre_pressure: float
    front_right_tyre_pressure: float
    ballast: int
    fuel_load: float
    engine_braking: int = 0          # Engine braking %


# =============================================================================
# EVENT DATA
# =============================================================================

@dataclass
class EventData:
    """Event packet - notable in-game events."""
    event_code: str                  # 4-character event code
    vehicle_index: int = 0           # Car index involved (if applicable)
    lap_time: float = 0.0            # Fastest lap time (FTLP)
    speed: float = 0.0               # Speed trap speed (SPTP)
    penalty_type: int = 0            # Penalty type (PNAL)
    infringement_type: int = 0       # Infringement type (PNAL)
    other_vehicle_index: int = 0     # Other car involved (PNAL)
    time: int = 0                    # Penalty time seconds (PNAL)
    lap_num: int = 0                 # Lap number (PNAL)
    places_gained: int = 0           # Places gained (PNAL)

    # Event code constants
    SESSION_STARTED = "SSTA"
    SESSION_ENDED = "SEND"
    FASTEST_LAP = "FTLP"
    RETIREMENT = "RTMT"
    DRS_ENABLED = "DRSE"
    DRS_DISABLED = "DRSD"
    TEAM_MATE_IN_PITS = "TMPT"
    CHEQUERED_FLAG = "CHQF"
    RACE_WINNER = "RCWN"
    PENALTY_ISSUED = "PNAL"
    SPEED_TRAP = "SPTP"
    START_LIGHTS = "STLG"
    LIGHTS_OUT = "LGOT"
    DRIVE_THROUGH_SERVED = "DTSV"
    STOP_GO_SERVED = "SGSV"
    FLASHBACK = "FLBK"
    BUTTON_STATUS = "BUTN"
    RED_FLAG = "RDFL"
    OVERTAKE = "OVTK"


# =============================================================================
# FINAL CLASSIFICATION
# =============================================================================

@dataclass
class FinalClassification:
    """End-of-session classification for a driver."""
    position: int                    # Finishing position
    num_laps: int                    # Laps completed
    grid_position: int               # Starting grid position
    points: int                      # Points scored
    num_pit_stops: int
    result_status: int               # 0=invalid, 1=inactive, 2=active, 3=finished, 4=DNF, 5=DSQ, 6=not classified
    best_lap_time: float             # Seconds
    total_race_time: float           # Seconds (double)
    penalties_time: int              # Seconds
    num_penalties: int
    num_tyre_stints: int
    tyre_stints_actual: list         # Actual compounds per stint
    tyre_stints_visual: list         # Visual compounds per stint


# =============================================================================
# LOBBY INFO
# =============================================================================

@dataclass
class LobbyInfo:
    """Multiplayer lobby player information."""
    ai_controlled: bool
    team_id: int
    nationality: int
    name: str
    ready_status: int                # 0=not ready, 1=ready, 2=spectating
    tech_level: int = 0


# =============================================================================
# SESSION HISTORY
# =============================================================================

@dataclass
class LapHistoryItem:
    """Single lap history entry."""
    lap_time_ms: int
    sector1_time_ms: int
    sector2_time_ms: int
    sector3_time_ms: int
    lap_valid: bool
    sector1_valid: bool
    sector2_valid: bool
    sector3_valid: bool

    @property
    def lap_time(self) -> str:
        """Format lap time as M:SS.mmm"""
        if self.lap_time_ms == 0:
            return "--:--.---"
        mins = self.lap_time_ms // 60000
        secs = (self.lap_time_ms % 60000) / 1000
        return f"{mins}:{secs:06.3f}"


@dataclass
class SessionHistory:
    """Lap and sector time history for a car."""
    car_index: int
    num_laps: int
    num_tyre_stints: int
    best_lap_time_lap_num: int
    best_sector1_lap_num: int
    best_sector2_lap_num: int
    best_sector3_lap_num: int
    lap_history: list                # List of LapHistoryItem


# =============================================================================
# TYRE SET DATA
# =============================================================================

@dataclass
class TyreSetInfo:
    """Information about a single tyre set."""
    actual_compound: int
    visual_compound: int
    wear: int                        # Percentage worn
    available: bool
    recommended_session: int
    life_span: int
    usable_life: int
    lap_delta_time: int              # ms delta vs fitted set
    fitted: bool


@dataclass
class TyreSetData:
    """Available tyre sets for a car."""
    car_index: int
    tyre_sets: list                  # List of TyreSetInfo
    fitted_index: int                # Index of currently fitted set


# =============================================================================
# TIME TRIAL
# =============================================================================

@dataclass
class TimeTrialDataSet:
    """Time trial data for a single entry (player/personal best/rival)."""
    car_index: int
    team_id: int
    lap_time_ms: int
    sector1_time_ms: int
    sector2_time_ms: int
    sector3_time_ms: int
    traction_control: int
    gearbox_assist: int
    anti_lock_brakes: bool
    equal_car_performance: bool
    custom_setup: bool
    valid: bool

    @property
    def lap_time(self) -> str:
        """Format lap time as M:SS.mmm"""
        if self.lap_time_ms == 0:
            return "--:--.---"
        mins = self.lap_time_ms // 60000
        secs = (self.lap_time_ms % 60000) / 1000
        return f"{mins}:{secs:06.3f}"


@dataclass
class TimeTrial:
    """Time trial packet data."""
    player_session_best: TimeTrialDataSet
    personal_best: TimeTrialDataSet
    rival: TimeTrialDataSet
