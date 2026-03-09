"""Lap Analyzer - produces a formatted telemetry report from a .f1lap file."""

from .lap_reader import LapFile

# ── Lookup tables ────────────────────────────────────────────────

TRACK_NAMES = {
    0: "Melbourne", 1: "Paul Ricard", 2: "Shanghai", 3: "Bahrain",
    4: "Catalunya", 5: "Monaco", 6: "Montreal", 7: "Silverstone",
    8: "Hockenheim", 9: "Hungaroring", 10: "Spa", 11: "Monza",
    12: "Singapore", 13: "Suzuka", 14: "Abu Dhabi", 15: "Texas",
    16: "Brazil", 17: "Austria", 18: "Sochi", 19: "Mexico",
    20: "Baku", 21: "Bahrain Short", 22: "Silverstone Short",
    23: "Texas Short", 24: "Suzuka Short", 25: "Hanoi",
    26: "Zandvoort", 27: "Imola", 28: "Portimao", 29: "Jeddah",
    30: "Miami", 31: "Las Vegas", 32: "Losail",
}

SESSION_NAMES = {
    0: "Unknown", 1: "P1", 2: "P2", 3: "P3", 4: "Short Practice",
    5: "Q1", 6: "Q2", 7: "Q3", 8: "Short Qualifying", 9: "One-Shot Qualifying",
    10: "Race", 11: "Race 2", 12: "Race 3", 13: "Time Trial",
}

TYRE_NAMES = {
    16: "Soft", 17: "Medium", 18: "Hard", 7: "Inter", 8: "Wet",
}

WEATHER_NAMES = {
    0: "Clear", 1: "Light Cloud", 2: "Overcast",
    3: "Light Rain", 4: "Heavy Rain", 5: "Storm",
}

TEAM_NAMES = {
    0: "Mercedes", 1: "Ferrari", 2: "Red Bull", 3: "Williams",
    4: "Aston Martin", 5: "Alpine", 6: "AlphaTauri", 7: "Haas",
    8: "McLaren", 9: "Alfa Romeo",
}

ERS_MODE_NAMES = {0: "None", 1: "Medium", 2: "Hotlap", 3: "Overtake"}

STEERING_ASSIST = {0: "Off", 1: "On"}
BRAKING_ASSIST = {0: "Off", 1: "Low", 2: "Medium", 3: "High"}
GEARBOX_ASSIST = {0: "Manual", 1: "Suggested", 2: "Manual+Suggested", 3: "Auto"}
ON_OFF = {0: "Off", 1: "On"}
RACING_LINE = {0: "Off", 1: "Corners Only", 2: "Full"}
TC_NAMES = {0: "Off", 1: "Medium", 2: "Full"}


# ── Helpers ──────────────────────────────────────────────────────

def _fmt_time(ms: int) -> str:
    if ms == 0:
        return "--:--.---"
    m = ms // 60000
    s = (ms % 60000) / 1000
    return f"{m}:{s:06.3f}"


def _pct(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}%"


def _section(title: str) -> str:
    return f"\n{'─' * 60}\n  {title}\n{'─' * 60}"


# ── Main analyzer ────────────────────────────────────────────────

def analyze_lap(lap: LapFile) -> str:
    """Produce a formatted multi-section telemetry report."""
    h = lap.header
    samples = lap.samples
    lines: list[str] = []

    n = len(samples)
    if n == 0:
        return f"No samples in {lap.path}"

    # ── 1. Header ────────────────────────────────────────────────

    track = TRACK_NAMES.get(h.track_id, f"Track {h.track_id}")
    session = SESSION_NAMES.get(h.session_type, f"Session {h.session_type}")
    tyre = TYRE_NAMES.get(h.tyre_compound, f"Compound {h.tyre_compound}")
    weather = WEATHER_NAMES.get(h.weather, f"Weather {h.weather}")
    team = TEAM_NAMES.get(h.team_id, f"Team {h.team_id}")
    valid = "Valid" if h.lap_valid else "INVALID"

    lines.append(_section("LAP INFO"))
    lines.append(f"  File:      {lap.path.name if lap.path else 'N/A'}")
    lines.append(f"  Driver:    {h.driver_name}  ({team})")
    lines.append(f"  Track:     {track}")
    lines.append(f"  Session:   {session}  |  Weather: {weather}")
    lines.append(f"  Lap:       {h.lap_number}  |  {valid}")
    lines.append(f"  Tyre:      {tyre}")
    lines.append(f"  Game:      F1 20{h.game_year}")
    lines.append(f"  Samples:   {n}  (format v{h.version})")
    lines.append(f"  Lap Time:  {_fmt_time(h.lap_time_ms)}")
    lines.append(f"  Sectors:   S1 {_fmt_time(h.sector1_ms)}  S2 {_fmt_time(h.sector2_ms)}  S3 {_fmt_time(h.sector3_ms)}")

    # ── 2. Assists ───────────────────────────────────────────────

    lines.append(_section("ASSISTS"))
    if h.steering_assist is not None:
        lines.append(f"  Steering Assist:      {STEERING_ASSIST.get(h.steering_assist, h.steering_assist)}")
        lines.append(f"  Braking Assist:       {BRAKING_ASSIST.get(h.braking_assist, h.braking_assist)}")
        lines.append(f"  Gearbox Assist:       {GEARBOX_ASSIST.get(h.gearbox_assist, h.gearbox_assist)}")
        lines.append(f"  Pit Assist:           {ON_OFF.get(h.pit_assist, h.pit_assist)}")
        lines.append(f"  Pit Release Assist:   {ON_OFF.get(h.pit_release_assist, h.pit_release_assist)}")
        lines.append(f"  ERS Assist:           {ON_OFF.get(h.ers_assist, h.ers_assist)}")
        lines.append(f"  DRS Assist:           {ON_OFF.get(h.drs_assist, h.drs_assist)}")
        lines.append(f"  Racing Line:          {RACING_LINE.get(h.dynamic_racing_line, h.dynamic_racing_line)}")
        lines.append(f"  Traction Control:     {TC_NAMES.get(h.traction_control, h.traction_control)}")
        lines.append(f"  Anti-Lock Brakes:     {ON_OFF.get(h.anti_lock_brakes, h.anti_lock_brakes)}")
    else:
        lines.append("  N/A (v1 file — assists not recorded)")

    # ── 3. Speed ─────────────────────────────────────────────────

    speeds = [s.speed for s in samples]
    lines.append(_section("SPEED"))
    lines.append(f"  Max:  {max(speeds):5d} km/h")
    lines.append(f"  Min:  {min(speeds):5d} km/h")
    lines.append(f"  Avg:  {sum(speeds)/n:5.0f} km/h")

    # ── 4. Engine ────────────────────────────────────────────────

    rpms = [s.engine_rpm for s in samples]
    lines.append(_section("ENGINE"))
    lines.append(f"  RPM Max:  {max(rpms):6d}")
    lines.append(f"  RPM Min:  {min(rpms):6d}")
    lines.append(f"  RPM Avg:  {sum(rpms)/n:6.0f}")
    temps = [s.engine_temperature for s in samples]
    lines.append(f"  Temp Max: {max(temps):4d} C")
    lines.append(f"  Temp Avg: {sum(temps)/n:4.0f} C")

    # ── 5. Inputs ────────────────────────────────────────────────

    throttles = [s.throttle for s in samples]
    brakes = [s.brake for s in samples]
    steers = [s.steer for s in samples]
    full_throttle = sum(1 for t in throttles if t > 0.95)
    trail_braking = sum(1 for i in range(n) if brakes[i] > 0.05 and throttles[i] > 0.05)
    coasting = sum(1 for i in range(n) if throttles[i] < 0.05 and brakes[i] < 0.05)

    lines.append(_section("INPUTS"))
    lines.append(f"  Throttle:  avg {sum(throttles)/n:.0%}  max {max(throttles):.0%}")
    lines.append(f"  Brake:     avg {sum(brakes)/n:.0%}  max {max(brakes):.0%}")
    lines.append(f"  Steer:     min {min(steers):+.2f}  max {max(steers):+.2f}")
    lines.append(f"  Full Throttle:  {_pct(full_throttle/n*100)}")
    lines.append(f"  Trail Braking:  {_pct(trail_braking/n*100)}")
    lines.append(f"  Coasting:       {_pct(coasting/n*100)}")

    # ── 6. Gears ─────────────────────────────────────────────────

    gear_counts: dict[int, int] = {}
    for s in samples:
        gear_counts[s.gear] = gear_counts.get(s.gear, 0) + 1

    lines.append(_section("GEARS"))
    for g in sorted(gear_counts):
        label = "R" if g == -1 else ("N" if g == 0 else str(g))
        pct = gear_counts[g] / n * 100
        bar_len = int(pct / 2)
        lines.append(f"  {label:>2s}  {'█' * bar_len:25s} {pct:5.1f}%")

    # ── 7. G-Forces ──────────────────────────────────────────────

    g_lat = [s.g_force[0] for s in samples]
    g_lon = [s.g_force[1] for s in samples]
    g_vert = [s.g_force[2] for s in samples]

    lines.append(_section("G-FORCES"))
    lines.append(f"  Lateral:      {min(g_lat):+.2f} to {max(g_lat):+.2f} g")
    lines.append(f"  Longitudinal: {min(g_lon):+.2f} to {max(g_lon):+.2f} g")
    lines.append(f"  Vertical:     {min(g_vert):+.2f} to {max(g_vert):+.2f} g")

    # ── 8. Braking Zones ─────────────────────────────────────────

    lines.append(_section("BRAKING ZONES (>80% brake)"))
    in_zone = False
    zone_start_speed = 0
    zone_start_dist = 0.0
    zone_count = 0
    for s in samples:
        if s.brake > 0.80 and not in_zone:
            in_zone = True
            zone_start_speed = s.speed
            zone_start_dist = s.lap_distance
        elif s.brake <= 0.80 and in_zone:
            in_zone = False
            zone_count += 1
            dist = s.lap_distance - zone_start_dist
            lines.append(
                f"  #{zone_count:2d}  {zone_start_speed:3d} -> {s.speed:3d} km/h"
                f"  ({dist:5.0f}m)  @ {zone_start_dist:.0f}m"
            )
    if zone_count == 0:
        lines.append("  None")

    # ── 9. Slow Moments ──────────────────────────────────────────

    lines.append(_section("SLOW MOMENTS (<80 km/h)"))
    slow_events = []
    in_slow = False
    slow_start_dist = 0.0
    slow_min_speed = 999
    for s in samples:
        if s.speed < 80 and not in_slow:
            in_slow = True
            slow_start_dist = s.lap_distance
            slow_min_speed = s.speed
        elif s.speed < 80 and in_slow:
            slow_min_speed = min(slow_min_speed, s.speed)
        elif s.speed >= 80 and in_slow:
            in_slow = False
            slow_events.append((slow_start_dist, s.lap_distance, slow_min_speed))

    for i, (start, end, min_spd) in enumerate(slow_events, 1):
        lines.append(f"  #{i:2d}  min {min_spd:3d} km/h  @ {start:.0f}-{end:.0f}m")
    if not slow_events:
        lines.append("  None")

    # ── 10. Tyres ────────────────────────────────────────────────

    last = samples[-1]
    lines.append(_section("TYRES"))
    lines.append(f"  Compound: {tyre}  Age: {last.tyre_age_laps} laps")
    lines.append(f"  Wear (RL RR FL FR):  {last.tyre_wear[0]:5.1f}  {last.tyre_wear[1]:5.1f}  {last.tyre_wear[2]:5.1f}  {last.tyre_wear[3]:5.1f} %")

    # Surface temps (end of lap)
    lines.append(f"  Surface Temp:        {last.tyre_surface_temp[0]:4d}  {last.tyre_surface_temp[1]:4d}  {last.tyre_surface_temp[2]:4d}  {last.tyre_surface_temp[3]:4d} C")
    lines.append(f"  Inner Temp:          {last.tyre_inner_temp[0]:4d}  {last.tyre_inner_temp[1]:4d}  {last.tyre_inner_temp[2]:4d}  {last.tyre_inner_temp[3]:4d} C")
    lines.append(f"  Pressure:            {last.tyre_pressure[0]:5.1f} {last.tyre_pressure[1]:5.1f} {last.tyre_pressure[2]:5.1f} {last.tyre_pressure[3]:5.1f} psi")

    # ── 11. Brakes ───────────────────────────────────────────────

    lines.append(_section("BRAKES"))
    # Peak brake temps across all samples
    peak_bt = [0, 0, 0, 0]
    for s in samples:
        for w in range(4):
            peak_bt[w] = max(peak_bt[w], s.brake_temp[w])
    lines.append(f"  Peak Temp (RL RR FL FR): {peak_bt[0]:4d}  {peak_bt[1]:4d}  {peak_bt[2]:4d}  {peak_bt[3]:4d} C")
    lines.append(f"  End Temp:                {last.brake_temp[0]:4d}  {last.brake_temp[1]:4d}  {last.brake_temp[2]:4d}  {last.brake_temp[3]:4d} C")
    lines.append(f"  Brake Bias:  {last.front_brake_bias}% front")
    lines.append(f"  Damage:      {last.brakes_damage[0]}  {last.brakes_damage[1]}  {last.brakes_damage[2]}  {last.brakes_damage[3]} %")

    # ── 12. ERS & Fuel ───────────────────────────────────────────

    lines.append(_section("ERS & FUEL"))
    first = samples[0]
    ers_pct_start = first.ers_store_energy / 4_000_000 * 100
    ers_pct_end = last.ers_store_energy / 4_000_000 * 100
    lines.append(f"  ERS Store:    {ers_pct_start:.1f}% -> {ers_pct_end:.1f}%")
    lines.append(f"  ERS Deploy:   {ERS_MODE_NAMES.get(last.ers_deploy_mode, last.ers_deploy_mode)}")
    lines.append(f"  Harvested (MGU-K): {last.ers_harvested_mguk/1e6:.3f} MJ")
    lines.append(f"  Harvested (MGU-H): {last.ers_harvested_mguh/1e6:.3f} MJ")
    lines.append(f"  Deployed:          {last.ers_deployed_this_lap/1e6:.3f} MJ")
    lines.append(f"  Fuel:         {first.fuel_remaining:.2f} -> {last.fuel_remaining:.2f} kg  ({last.fuel_remaining_laps:+.1f} laps)")

    # ── 13. DRS ──────────────────────────────────────────────────

    drs_open = sum(1 for s in samples if s.drs)
    drs_allowed = sum(1 for s in samples if s.drs_allowed)

    lines.append(_section("DRS"))
    lines.append(f"  Open:    {_pct(drs_open/n*100)}  ({drs_open} samples)")
    lines.append(f"  Allowed: {_pct(drs_allowed/n*100)}  ({drs_allowed} samples)")

    # ── 14. Damage ───────────────────────────────────────────────

    lines.append(_section("DAMAGE (end of lap)"))
    lines.append(f"  Front Wing:  L {last.fl_wing_damage}%  R {last.fr_wing_damage}%")
    lines.append(f"  Rear Wing:   {last.rear_wing_damage}%")
    lines.append(f"  Floor:       {last.floor_damage}%")
    lines.append(f"  Diffuser:    {last.diffuser_damage}%")
    lines.append(f"  Sidepod:     {last.sidepod_damage}%")
    lines.append(f"  Gearbox:     {last.gearbox_damage}%")
    lines.append(f"  Engine:      {last.engine_damage}%")
    if last.drs_fault:
        lines.append("  DRS FAULT")
    if last.ers_fault:
        lines.append("  ERS FAULT")
    lines.append(f"  PU Wear:  MGU-H {last.engine_mguh_wear}%  ES {last.engine_es_wear}%  CE {last.engine_ce_wear}%  ICE {last.engine_ice_wear}%  MGU-K {last.engine_mguk_wear}%  TC {last.engine_tc_wear}%")

    # ── 15. Wheel Slip ───────────────────────────────────────────

    slip_threshold = 0.3
    high_slip = sum(
        1 for s in samples
        if any(abs(s.wheel_slip_ratio[w]) > slip_threshold for w in range(4))
    )

    lines.append(_section("WHEEL SLIP"))
    lines.append(f"  High slip (|ratio| > {slip_threshold}): {_pct(high_slip/n*100)}  ({high_slip} samples)")

    lines.append("")
    return "\n".join(lines)
