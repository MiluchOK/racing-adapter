"""Lap Infographic — racing HUD-style PNG from .f1lap telemetry files."""

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .lap_analyzer import TRACK_NAMES, TEAM_NAMES, TYRE_NAMES, WEATHER_NAMES, SESSION_NAMES
from .lap_reader import LapFile


# ── Dimensions & Colors ─────────────────────────────────────────

W, H = 1920, 1080
BG = "#0a0a0a"
PANEL_BG = "#141414"
BORDER = "#222222"
WHITE = "#ffffff"
DIM = "#888888"
FAINT = "#555555"
GREEN = "#00FF66"
RED = "#FF3333"

TEAM_COLORS = {
    0: "#00D2BE",  # Mercedes
    1: "#DC0000",  # Ferrari
    2: "#3671C6",  # Red Bull
    3: "#005AFF",  # Williams
    4: "#006F63",  # Aston Martin
    5: "#0090FF",  # Alpine
    6: "#2B4562",  # AlphaTauri
    7: "#B6BABD",  # Haas
    8: "#FF8000",  # McLaren
    9: "#900000",  # Alfa Romeo
}

TYRE_CLR = {
    16: "#FF3C3C",  # Soft
    17: "#FFD232",  # Medium
    18: "#E6E6E6",  # Hard
    7: "#3CC83C",   # Inter
    8: "#3C64FF",   # Wet
}


# ── Font Loading ─────────────────────────────────────────────────

_font_cache = {}


def _font(size, bold=False):
    key = (size, bold)
    if key not in _font_cache:
        _font_cache[key] = _load_font(size, bold)
    return _font_cache[key]


def _load_font(size, bold=False):
    if bold:
        candidates = [
            ("/System/Library/Fonts/Helvetica.ttc", 1),
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
    else:
        candidates = [
            ("/System/Library/Fonts/Helvetica.ttc", 0),
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    for entry in candidates:
        try:
            if isinstance(entry, tuple):
                return ImageFont.truetype(entry[0], size, index=entry[1])
            return ImageFont.truetype(entry, size)
        except (OSError, IOError):
            continue
    try:
        return ImageFont.load_default(size)
    except TypeError:
        return ImageFont.load_default()


# ── Helpers ──────────────────────────────────────────────────────

def _hex(h):
    """Hex color string to (R, G, B) tuple."""
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _fmt_time(ms):
    if ms == 0:
        return "--:--.---"
    m = ms // 60000
    s = (ms % 60000) / 1000
    return f"{m}:{s:06.3f}"


def _speed_color(t):
    """Normalized speed (0=slow, 1=fast) to (R, G, B). Blue to green to red."""
    t = max(0.0, min(1.0, t))
    if t < 0.5:
        f = t * 2
        return (0, int(255 * f), int(255 * (1 - f)))
    f = (t - 0.5) * 2
    return (int(255 * f), int(255 * (1 - f)), 0)


def _draw_panel(draw, x, y, w, h, border=True):
    """Draw a dark panel rectangle."""
    draw.rectangle([x, y, x + w, y + h], fill=PANEL_BG)
    if border:
        draw.rectangle([x, y, x + w, y + h], outline=BORDER)


def _alpha_fill(img, points, color_rgba):
    """Draw a translucent polygon via alpha compositing on a cropped region."""
    if len(points) < 3:
        return
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    x0, y0 = max(0, int(min(xs))), max(0, int(min(ys)))
    x1, y1 = min(img.width, int(max(xs)) + 1), min(img.height, int(max(ys)) + 1)
    if x1 <= x0 or y1 <= y0:
        return
    region = img.crop((x0, y0, x1, y1)).convert("RGBA")
    overlay = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    shifted = [(p[0] - x0, p[1] - y0) for p in points]
    d.polygon(shifted, fill=color_rgba)
    result = Image.alpha_composite(region, overlay)
    img.paste(result, (x0, y0))


# ── Panel Renderers ──────────────────────────────────────────────

def _draw_banner(img, draw, lap, team_color):
    """Top banner: driver, track, lap time, sectors, validity."""
    h = lap.header
    bh = 130
    _draw_panel(draw, 0, 0, W, bh, border=False)
    # Team color accent line at bottom
    draw.rectangle([0, bh - 3, W, bh], fill=team_color)

    # Driver + Team
    driver = h.driver_name or "Unknown"
    team = TEAM_NAMES.get(h.team_id, f"Team {h.team_id}")
    draw.text((40, 20), driver, fill=WHITE, font=_font(42, bold=True))
    draw.text((40, 72), team, fill=team_color, font=_font(24))

    # Track + Session
    track = TRACK_NAMES.get(h.track_id, f"Track {h.track_id}")
    session = SESSION_NAMES.get(h.session_type, f"Session {h.session_type}")
    weather = WEATHER_NAMES.get(h.weather, "")
    draw.text((400, 20), track, fill=WHITE, font=_font(36, bold=True))
    draw.text((400, 65), f"{session}  |  {weather}", fill=DIM, font=_font(22))

    # Lap number
    draw.text((800, 20), f"LAP {h.lap_number}", fill=WHITE, font=_font(36, bold=True))

    # Lap time (big)
    time_str = _fmt_time(h.lap_time_ms)
    draw.text((1000, 12), time_str, fill=WHITE, font=_font(52, bold=True))

    # Sectors
    sx = 1350
    for label, ms in [("S1", h.sector1_ms), ("S2", h.sector2_ms), ("S3", h.sector3_ms)]:
        draw.text((sx, 20), label, fill=DIM, font=_font(16))
        draw.text((sx, 40), _fmt_time(ms), fill=WHITE, font=_font(22))
        sx += 120

    # Validity badge
    if h.lap_valid:
        draw.text((sx + 40, 30), "VALID", fill=GREEN, font=_font(22, bold=True))
    else:
        draw.rectangle([sx + 30, 22, sx + 150, 62], fill="#440000")
        draw.text((sx + 40, 28), "INVALID", fill=RED, font=_font(22, bold=True))

    # Game + format
    draw.text((40, 100), f"F1 20{h.game_year}  v{h.version}", fill=FAINT, font=_font(13))


def _draw_speed_trace(img, draw, samples, team_color):
    """Speed vs distance chart with line + translucent fill."""
    px, py, pw, ph = 30, 150, 570, 370
    _draw_panel(draw, px, py, pw, ph)
    draw.text((px + 15, py + 8), "SPEED", fill=WHITE, font=_font(16, bold=True))
    draw.text((px + 80, py + 8), "km/h", fill=DIM, font=_font(13))

    if not samples:
        return

    cx, cy = px + 50, py + 40
    cw, ch = pw - 65, ph - 60

    speeds = [s.speed for s in samples]
    dists = [s.lap_distance for s in samples]
    max_speed = max(speeds) or 1
    max_dist = max(dists) or 1

    # Grid lines + labels
    for frac in [0.25, 0.5, 0.75]:
        gy = cy + ch - int(frac * ch)
        draw.line([(cx, gy), (cx + cw, gy)], fill=BORDER, width=1)
        draw.text((px + 5, gy - 7), str(int(max_speed * frac)), fill=FAINT, font=_font(11))
    draw.text((px + 5, cy - 2), str(max_speed), fill=FAINT, font=_font(11))

    # Build points
    points = []
    for i, s in enumerate(samples):
        x = cx + int((dists[i] / max_dist) * cw)
        y = cy + ch - int((s.speed / max_speed) * ch)
        points.append((x, y))

    # Translucent fill
    fill_pts = list(points) + [(points[-1][0], cy + ch), (points[0][0], cy + ch)]
    _alpha_fill(img, fill_pts, _hex(team_color) + (40,))

    # Line
    if len(points) > 1:
        draw.line(points, fill=team_color, width=2)


def _draw_inputs(img, draw, samples):
    """Throttle + brake vs distance chart."""
    px, py, pw, ph = 30, 540, 570, 370
    _draw_panel(draw, px, py, pw, ph)
    draw.text((px + 15, py + 8), "INPUTS", fill=WHITE, font=_font(16, bold=True))

    # Legend
    draw.rectangle([px + 90, py + 10, px + 100, py + 20], fill=GREEN)
    draw.text((px + 105, py + 8), "Throttle", fill=DIM, font=_font(13))
    draw.rectangle([px + 185, py + 10, px + 195, py + 20], fill=RED)
    draw.text((px + 200, py + 8), "Brake", fill=DIM, font=_font(13))

    if not samples:
        return

    cx, cy = px + 50, py + 40
    cw, ch = pw - 65, ph - 60

    dists = [s.lap_distance for s in samples]
    max_dist = max(dists) or 1

    # Grid lines
    for frac in [0.25, 0.5, 0.75, 1.0]:
        gy = cy + ch - int(frac * ch)
        draw.line([(cx, gy), (cx + cw, gy)], fill=BORDER, width=1)
        draw.text((px + 5, gy - 7), f"{int(frac * 100)}%", fill=FAINT, font=_font(11))

    t_points = []
    b_points = []
    for s in samples:
        x = cx + int((s.lap_distance / max_dist) * cw)
        t_points.append((x, cy + ch - int(s.throttle * ch)))
        b_points.append((x, cy + ch - int(s.brake * ch)))

    # Throttle fill + line
    fill_t = list(t_points) + [(t_points[-1][0], cy + ch), (t_points[0][0], cy + ch)]
    _alpha_fill(img, fill_t, _hex(GREEN) + (35,))
    if len(t_points) > 1:
        draw.line(t_points, fill=GREEN, width=1)

    # Brake fill + line
    fill_b = list(b_points) + [(b_points[-1][0], cy + ch), (b_points[0][0], cy + ch)]
    _alpha_fill(img, fill_b, _hex(RED) + (35,))
    if len(b_points) > 1:
        draw.line(b_points, fill=RED, width=1)


def _draw_track_map(img, draw, samples, team_color):
    """Track map colored by speed — centerpiece panel."""
    px, py, pw, ph = 630, 150, 660, 770
    _draw_panel(draw, px, py, pw, ph)
    draw.text((px + 15, py + 8), "TRACK MAP", fill=WHITE, font=_font(16, bold=True))

    if len(samples) < 2:
        return

    xs = [s.world_position[0] for s in samples]
    zs = [s.world_position[2] for s in samples]
    speeds = [s.speed for s in samples]

    min_x, max_x = min(xs), max(xs)
    min_z, max_z = min(zs), max(zs)
    range_x = max_x - min_x or 1
    range_z = max_z - min_z or 1

    pad = 50
    cx, cy = px + pad, py + pad + 20
    cw, ch = pw - 2 * pad, ph - 2 * pad - 40

    # Uniform aspect ratio
    scale = min(cw / range_x, ch / range_z)
    ow = range_x * scale
    oh = range_z * scale
    ox = cx + (cw - ow) / 2
    oy = cy + (ch - oh) / 2

    min_speed = min(speeds)
    max_speed = max(speeds) or 1
    speed_range = max_speed - min_speed or 1

    def to_px(i):
        x = ox + (xs[i] - min_x) / range_x * ow
        y = oy + oh - (zs[i] - min_z) / range_z * oh
        return (int(x), int(y))

    # Draw colored line segments
    for i in range(len(samples) - 1):
        p0, p1 = to_px(i), to_px(i + 1)
        t = (speeds[i] - min_speed) / speed_range
        draw.line([p0, p1], fill=_speed_color(t), width=3)

    # Start/finish dot
    start = to_px(0)
    draw.ellipse([start[0] - 5, start[1] - 5, start[0] + 5, start[1] + 5], fill=WHITE)

    # Speed legend bar
    legend_x = px + 50
    legend_y = py + ph - 30
    legend_w = pw - 100
    for i in range(legend_w):
        c = _speed_color(i / legend_w)
        draw.line([(legend_x + i, legend_y), (legend_x + i, legend_y + 10)], fill=c)
    draw.text((legend_x - 5, legend_y + 14), str(min_speed), fill=DIM, font=_font(11))
    draw.text((legend_x + legend_w - 25, legend_y + 14), f"{max_speed} km/h", fill=DIM, font=_font(11))


def _draw_stats_cards(draw, samples, team_color):
    """2x2 stat cards: Top Speed, Avg Speed, Max G, DRS Usage."""
    px, py, pw, ph = 1320, 150, 570, 420
    _draw_panel(draw, px, py, pw, ph)

    if not samples:
        return

    n = len(samples)
    speeds = [s.speed for s in samples]
    top_speed = max(speeds)
    avg_speed = sum(speeds) / n
    max_g = max(math.sqrt(s.g_force[0] ** 2 + s.g_force[1] ** 2) for s in samples)
    drs_pct = sum(1 for s in samples if s.drs) / n * 100

    cards = [
        ("TOP SPEED", f"{top_speed}", "km/h"),
        ("AVG SPEED", f"{avg_speed:.0f}", "km/h"),
        ("MAX G-FORCE", f"{max_g:.1f}", "G"),
        ("DRS USAGE", f"{drs_pct:.0f}", "%"),
    ]

    card_w = (pw - 30) // 2
    card_h = (ph - 30) // 2

    for idx, (label, value, unit) in enumerate(cards):
        col, row = idx % 2, idx // 2
        cx = px + 10 + col * (card_w + 10)
        cy = py + 10 + row * (card_h + 10)
        draw.rectangle([cx, cy, cx + card_w, cy + card_h], fill="#1a1a1a")
        # Left accent stripe
        draw.rectangle([cx, cy, cx + 4, cy + card_h], fill=team_color)
        draw.text((cx + 15, cy + 12), label, fill=DIM, font=_font(14))
        draw.text((cx + 15, cy + 40), value, fill=WHITE, font=_font(52, bold=True))
        draw.text((cx + 15, cy + card_h - 35), unit, fill=FAINT, font=_font(18))


def _draw_gear_dist(draw, samples, team_color):
    """Gear distribution — horizontal bars."""
    px, py, pw, ph = 1320, 590, 570, 330
    _draw_panel(draw, px, py, pw, ph)
    draw.text((px + 15, py + 8), "GEAR DISTRIBUTION", fill=WHITE, font=_font(16, bold=True))

    if not samples:
        return

    n = len(samples)
    gear_counts = {}
    for s in samples:
        gear_counts[s.gear] = gear_counts.get(s.gear, 0) + 1

    gears = sorted(gear_counts.keys())
    if not gears:
        return

    bx = px + 50
    by = py + 40
    bw = pw - 80
    bar_h = min(28, (ph - 60) // max(len(gears), 1) - 4)
    max_pct = max(gear_counts[g] / n for g in gears) or 1

    for i, g in enumerate(gears):
        label = "R" if g == -1 else ("N" if g == 0 else str(g))
        pct = gear_counts[g] / n
        bar_len = int((pct / max_pct) * bw)
        gy = by + i * (bar_h + 4)
        draw.text((px + 15, gy + 2), label, fill=WHITE, font=_font(16, bold=True))
        draw.rectangle([bx, gy, bx + bar_len, gy + bar_h], fill=team_color)
        draw.text((bx + bar_len + 8, gy + 2), f"{pct * 100:.1f}%", fill=DIM, font=_font(14))


def _draw_bottom_strip(img, draw, samples, header, team_color):
    """Bottom strip: tyre, temps, ERS, fuel, DRS, damage."""
    py, ph = 920, 160
    _draw_panel(draw, 0, py, W, ph, border=False)
    draw.rectangle([0, py, W, py + 2], fill=team_color)

    if not samples:
        return

    last = samples[-1]
    n = len(samples)

    # ── Tyre compound + wear ──
    sx = 40
    compound = TYRE_NAMES.get(header.tyre_compound, f"C{header.tyre_compound}")
    tyre_clr = TYRE_CLR.get(header.tyre_compound, "#AAAAAA")

    draw.text((sx, py + 12), "TYRE", fill=DIM, font=_font(13))
    draw.text((sx, py + 30), compound, fill=tyre_clr, font=_font(28, bold=True))
    draw.text((sx, py + 65), f"Age: {last.tyre_age_laps} laps", fill=DIM, font=_font(14))

    wx = sx + 140
    wheel_labels = ["RL", "RR", "FL", "FR"]
    for i, lbl in enumerate(wheel_labels):
        wy = py + 15 + i * 32
        wear = last.tyre_wear[i]
        bar_w = 100
        fill_w = int((1 - wear / 100) * bar_w)
        wc = GREEN if wear < 20 else ("#FFD232" if wear < 50 else RED)
        draw.text((wx, wy), lbl, fill=DIM, font=_font(12))
        draw.rectangle([wx + 25, wy + 2, wx + 25 + bar_w, wy + 14], fill="#1a1a1a")
        draw.rectangle([wx + 25, wy + 2, wx + 25 + fill_w, wy + 14], fill=wc)
        draw.text((wx + 130, wy), f"{wear:.0f}%", fill=DIM, font=_font(12))

    # ── Tyre surface temps ──
    tx = 380
    draw.text((tx, py + 12), "TYRE TEMPS", fill=DIM, font=_font(13))
    for i, lbl in enumerate(wheel_labels):
        ty = py + 35 + i * 28
        temp = last.tyre_surface_temp[i]
        if temp < 80:
            tc = "#3C64FF"
        elif temp < 100:
            tc = GREEN
        elif temp < 110:
            tc = "#FFD232"
        else:
            tc = RED
        draw.text((tx, ty), f"{lbl}: {temp}\u00b0C", fill=tc, font=_font(16))

    # ── ERS + Fuel ──
    ex = 600
    draw.text((ex, py + 12), "ERS", fill=DIM, font=_font(13))
    ers_pct = last.ers_store_energy / 4_000_000
    ers_bar_w = 200
    draw.rectangle([ex, py + 35, ex + ers_bar_w, py + 55], fill="#1a1a1a")
    draw.rectangle([ex, py + 35, ex + int(ers_pct * ers_bar_w), py + 55], fill=team_color)
    draw.text((ex + ers_bar_w + 10, py + 35), f"{ers_pct * 100:.0f}%", fill=WHITE, font=_font(16))

    draw.text((ex, py + 70), "FUEL", fill=DIM, font=_font(13))
    fuel_delta = last.fuel_remaining_laps
    fuel_clr = GREEN if fuel_delta >= 0 else RED
    draw.text((ex, py + 90), f"{last.fuel_remaining:.1f} kg", fill=WHITE, font=_font(22))
    draw.text((ex + 130, py + 90), f"({fuel_delta:+.1f} laps)", fill=fuel_clr, font=_font(22))

    # ── DRS gauge ──
    dx = 950
    draw.text((dx, py + 12), "DRS", fill=DIM, font=_font(13))
    drs_open = sum(1 for s in samples if s.drs)
    drs_pct = drs_open / n * 100
    draw.text((dx, py + 35), f"{drs_pct:.0f}%", fill=WHITE, font=_font(36, bold=True))
    draw.text((dx, py + 80), f"{drs_open} samples open", fill=DIM, font=_font(14))
    if last.drs:
        draw.text((dx + 120, py + 40), "OPEN", fill=GREEN, font=_font(22, bold=True))

    # ── Damage ──
    dmx = 1200
    draw.text((dmx, py + 12), "DAMAGE", fill=DIM, font=_font(13))
    damage_items = [
        ("FL Wing", last.fl_wing_damage),
        ("FR Wing", last.fr_wing_damage),
        ("Rear Wing", last.rear_wing_damage),
        ("Floor", last.floor_damage),
        ("Diffuser", last.diffuser_damage),
        ("Sidepod", last.sidepod_damage),
        ("Gearbox", last.gearbox_damage),
        ("Engine", last.engine_damage),
    ]
    has_damage = any(v > 0 for _, v in damage_items)
    if not has_damage:
        draw.text((dmx, py + 40), "NO DAMAGE", fill=GREEN, font=_font(22, bold=True))
    else:
        col = 0
        for name, val in damage_items:
            if val == 0:
                continue
            dc = GREEN if val < 10 else ("#FFD232" if val < 30 else RED)
            draw.text((dmx + (col % 2) * 200, py + 35 + (col // 2) * 24),
                      f"{name}: {val}%", fill=dc, font=_font(14))
            col += 1

    # DRS/ERS faults
    fx = 1600
    fy = py + 35
    if last.drs_fault:
        draw.text((fx, fy), "DRS FAULT", fill=RED, font=_font(16, bold=True))
        fy += 25
    if last.ers_fault:
        draw.text((fx, fy), "ERS FAULT", fill=RED, font=_font(16, bold=True))

    # PU Wear
    draw.text((fx, py + 12), "PU WEAR", fill=DIM, font=_font(13))
    pu_items = [
        ("ICE", last.engine_ice_wear), ("TC", last.engine_tc_wear),
        ("MGU-H", last.engine_mguh_wear), ("MGU-K", last.engine_mguk_wear),
        ("ES", last.engine_es_wear), ("CE", last.engine_ce_wear),
    ]
    for i, (name, val) in enumerate(pu_items):
        pc = GREEN if val < 20 else ("#FFD232" if val < 50 else RED)
        draw.text((fx + (i // 3) * 130, py + 35 + (i % 3) * 22),
                  f"{name} {val}%", fill=pc, font=_font(13))


# ── Main Entry Point ────────────────────────────────────────────

def generate_infographic(lap: LapFile, output_path=None):
    """Generate a racing HUD infographic PNG from a LapFile.

    Args:
        lap: Decoded LapFile with header + samples.
        output_path: Where to save the PNG (defaults to <input>.png).

    Returns:
        Path to the saved PNG file.
    """
    if output_path is None:
        output_path = lap.path.with_suffix(".png") if lap.path else Path("infographic.png")
    output_path = Path(output_path)

    team_color = TEAM_COLORS.get(lap.header.team_id, "#FF8000")

    img = Image.new("RGBA", (W, H), BG)
    draw = ImageDraw.Draw(img)

    _draw_banner(img, draw, lap, team_color)
    _draw_speed_trace(img, draw, lap.samples, team_color)
    _draw_inputs(img, draw, lap.samples)
    _draw_track_map(img, draw, lap.samples, team_color)
    _draw_stats_cards(draw, lap.samples, team_color)
    _draw_gear_dist(draw, lap.samples, team_color)
    _draw_bottom_strip(img, draw, lap.samples, lap.header, team_color)

    img.convert("RGB").save(output_path, "PNG")
    return output_path
