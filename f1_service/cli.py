"""CLI entry point for f1-service."""

import json
import os
import signal
import sys
import threading
import time
from pathlib import Path

import click

from f1_service import F1Dispatcher, InfluxDBPublisher, MqttPublisher, LapReporter, LapRecorder, RawRecorder
from f1_service.packets import PacketType

CONFIG_PATH = Path.cwd() / "arduino_config.json"


def _load_config():
    """Load arduino_config.json from project root."""
    if not CONFIG_PATH.exists():
        raise click.ClickException(f"Config not found: {CONFIG_PATH}")
    with open(CONFIG_PATH) as f:
        return json.load(f)


def _find_arduino_port():
    """Auto-detect Arduino serial port."""
    import serial.tools.list_ports

    ports = serial.tools.list_ports.comports()
    for port in ports:
        if "Arduino" in port.description or "usbmodem" in port.device or "ttyACM" in port.device:
            return port.device
    if ports:
        return ports[0].device
    return None


def _open_serial(config):
    """Open serial connection based on config. Returns serial.Serial or None."""
    import serial

    port = config.get("serial_port", "auto")
    baud = config.get("baud_rate", 115200)

    if port == "auto":
        port = _find_arduino_port()
        if not port:
            raise click.ClickException(
                "No Arduino found. Set serial_port in arduino_config.json or use --no-serial."
            )

    click.echo(f"Opening serial port {port} at {baud} baud...")
    try:
        ser = serial.Serial(port, baud, timeout=0.1)
    except serial.SerialException as e:
        raise click.ClickException(f"Failed to open serial port: {e}")

    time.sleep(2)  # wait for Arduino reset
    while ser.in_waiting:
        line = ser.readline().decode("utf-8", errors="ignore").strip()
        if line:
            click.echo(f"Arduino: {line}")

    return ser


@click.group()
def cli():
    """F1 telemetry service CLI."""


@cli.command("f1-router")
@click.option("--port", default=20777, show_default=True, help="UDP port to listen on.")
@click.option("--no-serial", "no_serial", is_flag=True, default=False, help="Skip Arduino serial connection.")
@click.option("--mqtt/--no-mqtt", default=True, show_default=True, help="Enable/disable MQTT publishing.")
@click.option("--mqtt-broker", default="10.0.0.102:1883", show_default=True, help="MQTT broker host:port.")
@click.option("--scoreboard/--no-scoreboard", default=True, show_default=True, help="Enable/disable lap record reporting.")
@click.option("--record/--no-record", default=True, show_default=True, help="Enable/disable binary lap recording.")
@click.option("--laps-dir", default="laps", show_default=True, help="Directory for recorded .f1lap files.")
@click.option("--record-raw/--no-record-raw", default=False, show_default=True, help="Enable/disable raw UDP packet recording.")
@click.option("--captures-dir", default="captures", show_default=True, help="Directory for raw .f1raw capture files.")
@click.option("--influxdb/--no-influxdb", default=False, show_default=True, help="Enable/disable InfluxDB telemetry publishing.")
@click.option("--influxdb-url", default="http://localhost:8086", show_default=True, help="InfluxDB server URL.")
def f1_router(port: int, no_serial: bool, mqtt: bool, mqtt_broker: str, scoreboard: bool, record: bool, laps_dir: str, record_raw: bool, captures_dir: str, influxdb: bool, influxdb_url: str):
    """F1 telemetry router — listens for UDP data and fans out to MQTT, serial, and scoreboard."""
    ser = None
    if not no_serial:
        config = _load_config()
        ser = _open_serial(config)
        click.echo("Arduino connected.")

    dispatcher = F1Dispatcher(port=port)

    mqtt_pub = None
    if mqtt:
        broker_host, _, broker_port = mqtt_broker.partition(":")
        broker_port = int(broker_port) if broker_port else 1883
        mqtt_pub = MqttPublisher(host=broker_host, port=broker_port)
        mqtt_pub.register(dispatcher)
        mqtt_pub.connect()
        click.echo(f"MQTT publishing to {broker_host}:{broker_port}")

    lap_reporter = None
    if scoreboard:
        lap_reporter = LapReporter()
        lap_reporter.register(dispatcher)

    lap_recorder = None
    if record:
        lap_recorder = LapRecorder(laps_dir=laps_dir)
        lap_recorder.register(dispatcher)
        click.echo(f"Lap recording to {laps_dir}/")

    raw_recorder = None
    if record_raw:
        raw_recorder = RawRecorder(captures_dir=captures_dir)
        raw_recorder.register(dispatcher)
        click.echo(f"Raw recording to {captures_dir}/")

    influx_pub = None
    if influxdb:
        influx_token = os.environ.get("INFLUXDB_TOKEN", "")
        influx_org = os.environ.get("INFLUXDB_ORG", "")
        influx_bucket = os.environ.get("INFLUXDB_BUCKET", "f1")
        if not influx_token:
            raise click.ClickException("INFLUXDB_TOKEN env var is required when --influxdb is enabled.")
        if not influx_org:
            raise click.ClickException("INFLUXDB_ORG env var is required when --influxdb is enabled.")
        influx_pub = InfluxDBPublisher(url=influxdb_url, token=influx_token, org=influx_org, bucket=influx_bucket)
        influx_pub.register(dispatcher)
        influx_pub.connect()
        click.echo(f"InfluxDB publishing to {influxdb_url} (bucket: {influx_bucket})")

    # ── live console state ──────────────────────────────────────────
    console = {
        "tel": None, "lap": None, "session": None, "status": None,
        "lines_drawn": 0,
    }

    def _format_time_ms(ms):
        if ms == 0:
            return "--:--.---"
        m = ms // 60000
        s = (ms % 60000) / 1000
        return f"{m}:{s:06.3f}"

    def _bar(value, width=20, fill="█", empty="░"):
        n = int(value * width)
        return fill * n + empty * (width - n)

    def _render():
        tel = console["tel"]
        lap = console["lap"]
        ses = console["session"]
        sta = console["status"]
        if tel is None:
            return

        lines = []

        # Row 1: track / session / lap
        hdr = console.get("header")
        track = ""
        if ses:
            track_name = ses.track.name.replace("_", " ").title() if hasattr(ses.track, "name") else str(ses.track)
            ses_name = ses.session_type.name.replace("_", " ") if hasattr(ses.session_type, "name") else str(ses.session_type)
            track = f"{track_name}  {ses_name}"
        game_info = f"F1 {hdr.game_year}  car#{hdr.player_car_index}" if hdr else ""
        lap_num = f"Lap {lap.current_lap}" if lap else ""
        pos = f"P{lap.position}" if lap else ""
        lines.append(f"  {track:30s}  {lap_num:8s}  {pos:4s}  {game_info}")

        # Row 2: lap time / sectors
        if lap:
            cur = _format_time_ms(lap.current_lap_time_ms)
            last = _format_time_ms(lap.last_lap_time_ms)
            sector = f"S{lap.sector + 1}"
            invalid = " INVALID" if lap.current_lap_invalid else ""
            lines.append(f"  {cur}  last {last}  {sector}{invalid}")
        else:
            lines.append("")

        # Row 3: speed / gear / rpm
        gear = tel.gear_str
        rpm_pct = tel.engine_rpm / 15000 if tel.engine_rpm else 0
        lines.append(f"  {tel.speed:3d} km/h  gear {gear}  {tel.engine_rpm:5d} rpm  [{_bar(min(rpm_pct, 1.0), 15)}]")

        # Row 4: throttle / brake / steer
        lines.append(f"  throttle [{_bar(tel.throttle)}] {tel.throttle:4.0%}")
        lines.append(f"  brake    [{_bar(tel.brake)}] {tel.brake:4.0%}")
        steer_pos = int((tel.steer + 1) / 2 * 20)
        steer_bar = "░" * steer_pos + "█" + "░" * (20 - steer_pos)
        lines.append(f"  steer    [{steer_bar}] {tel.steer:+.2f}")

        # Row 5: tyres / fuel / ERS
        if sta:
            compound = sta.actual_tyre_compound.name if hasattr(sta.actual_tyre_compound, "name") else str(sta.actual_tyre_compound)
            ers_pct = sta.ers_store_energy / 4_000_000 * 100 if sta.ers_store_energy else 0
            lines.append(f"  {compound} age {sta.tyre_age_laps}  fuel {sta.fuel_remaining:.1f}kg ({sta.fuel_remaining_laps:+.1f} laps)  ERS {ers_pct:.0f}%")
        else:
            lines.append("")

        # Row 6: DRS
        drs = "DRS OPEN" if tel.drs else "drs"
        drs_allowed = ""
        if sta and sta.drs_allowed:
            drs_allowed = f" ({sta.drs_activation_distance}m)"
        lines.append(f"  {drs}{drs_allowed}  engine {tel.engine_temperature}°C")

        # Row 7: recording status
        if lap_recorder and lap_recorder._recording:
            fname = lap_recorder._lap_filepath.name if lap_recorder._lap_filepath else "—"
            samples = lap_recorder._sample_count
            size_kb = samples * 402 / 1024
            lines.append(f"  REC  {fname}  {samples} samples  {size_kb:.0f} KB")

        # Move cursor up to overwrite previous frame
        if console["lines_drawn"] > 0:
            sys.stdout.write(f"\033[{console['lines_drawn']}A\r")

        for line in lines:
            # Clear line and print
            sys.stdout.write(f"\033[2K{line}\n")
        sys.stdout.flush()
        console["lines_drawn"] = len(lines)

    @dispatcher.on(PacketType.CAR_TELEMETRY)
    def _on_telemetry(header, data):
        console["tel"] = data
        console["header"] = header
        _render()

        if ser and ser.is_open:
            cmd = f"S:{data.steer:.4f}\nT:{data.throttle:.4f}\n"
            ser.write(cmd.encode())

    @dispatcher.on(PacketType.LAP_DATA)
    def _on_lap(header, data):
        console["lap"] = data

    @dispatcher.on(PacketType.SESSION)
    def _on_session(header, data):
        console["session"] = data

    @dispatcher.on(PacketType.CAR_STATUS)
    def _on_status(header, data):
        console["status"] = data

    stop_event = threading.Event()

    def _handle_signal(signum, frame):
        click.echo("\nStopping f1-router...")
        stop_event.set()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    parts = []
    if ser:
        parts.append("serial")
    if mqtt_pub:
        parts.append("mqtt")
    if lap_reporter:
        parts.append("scoreboard")
    if lap_recorder:
        parts.append("recorder")
    if raw_recorder:
        parts.append("raw-recorder")
    if influx_pub:
        parts.append("influxdb")
    parts.append("terminal")
    mode = " + ".join(parts)
    click.echo(f"f1-router listening on UDP :{port} ({mode})  Ctrl+C to stop")
    dispatcher.start()

    stop_event.wait()
    dispatcher.stop()
    if lap_recorder:
        lap_recorder.close()
    if raw_recorder:
        raw_recorder.close()
    if influx_pub:
        influx_pub.close()
    if mqtt_pub:
        mqtt_pub.disconnect()
    if ser and ser.is_open:
        ser.close()
    click.echo("Stopped.")


# ── Raw capture commands ─────────────────────────────────────────


@cli.command("replay")
@click.argument("file", type=click.Path(exists=True))
@click.option("--host", default="127.0.0.1", show_default=True, help="Destination host.")
@click.option("--port", default=20777, show_default=True, help="Destination UDP port.")
@click.option("--speed", default=1.0, show_default=True, help="Playback speed (2.0 = double, 0 = no delay).")
@click.option("--loop", is_flag=True, default=False, help="Replay continuously until Ctrl+C.")
def replay_cmd(file: str, host: str, port: int, speed: float, loop: bool):
    """Replay a .f1raw capture file as UDP packets."""
    from f1_service.raw_replayer import file_info, replay

    info = file_info(file)
    mins = int(info.duration_s) // 60
    secs = info.duration_s % 60
    size_mb = info.file_size / (1024 * 1024)

    click.echo(f"File:     {info.path.name}")
    click.echo(f"Packets:  {info.packet_count}")
    click.echo(f"Duration: {mins}m{secs:04.1f}s")
    click.echo(f"Size:     {size_mb:.1f} MB")
    click.echo(f"Types:    {', '.join(f'{k}={v}' for k, v in sorted(info.packet_types.items()))}")
    click.echo()

    speed_label = "max" if speed == 0 else f"{speed}x"
    loop_label = " (loop)" if loop else ""
    click.echo(f"Replaying to {host}:{port} at {speed_label}{loop_label}...")

    last_pct = [-1]

    def _progress(sent, total):
        pct = sent * 100 // total
        if pct != last_pct[0]:
            last_pct[0] = pct
            click.echo(f"\r  {sent}/{total} packets ({pct}%)", nl=False)

    try:
        replay(file, host=host, port=port, speed=speed, loop=loop, callback=_progress)
    except KeyboardInterrupt:
        pass

    click.echo()
    click.echo("Done.")


@cli.command("captures")
@click.option("--captures-dir", default="captures", show_default=True, help="Directory with .f1raw files.")
def captures_cmd(captures_dir: str):
    """List raw .f1raw capture files."""
    from datetime import datetime

    from f1_service.raw_replayer import file_info

    captures_path = Path(captures_dir)
    if not captures_path.exists():
        click.echo(f"No captures directory: {captures_dir}/")
        return

    files = sorted(captures_path.glob("*.f1raw"))
    if not files:
        click.echo(f"No .f1raw files found in {captures_dir}/")
        return

    click.echo()
    for f in files:
        info = file_info(f)
        mins = int(info.duration_s) // 60
        secs = info.duration_s % 60
        size_mb = info.file_size / (1024 * 1024)

        # Extract date from filename (YYYYMMDD_HHMMSS.f1raw)
        stem = f.stem
        try:
            dt = datetime.strptime(stem, "%Y%m%d_%H%M%S")
            date_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            date_str = stem

        types_str = ", ".join(f"{k}={v}" for k, v in sorted(info.packet_types.items()))
        click.echo(
            f"  {f.name:28s}  {date_str}  {mins}m{secs:04.1f}s"
            f"  {info.packet_count:6d} pkts  {size_mb:5.1f} MB"
        )
        click.echo(f"    {types_str}")
        click.echo()


# ── Lap listing ──────────────────────────────────────────────────

_TRACK_NAMES = {
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

_SESSION_NAMES = {
    0: "Unknown", 1: "P1", 2: "P2", 3: "P3", 4: "Short P",
    5: "Q1", 6: "Q2", 7: "Q3", 8: "Short Q", 9: "OSQ",
    10: "Race", 11: "Race 2", 12: "Race 3", 13: "Time Trial",
}


def _format_lap_time(ms: int) -> str:
    if ms == 0:
        return "--:--.---"
    mins = ms // 60000
    secs = (ms % 60000) / 1000
    return f"{mins}:{secs:06.3f}"


@cli.command("laps")
@click.option("--laps-dir", default="laps", show_default=True, help="Directory with recorded .f1lap files.")
def list_laps_cmd(laps_dir: str):
    """List recorded lap files."""
    from f1_service.lap_reader import list_laps

    laps = list_laps(laps_dir)
    if not laps:
        click.echo(f"No .f1lap files found in {laps_dir}/")
        return

    click.echo()
    for lap in laps:
        track = _TRACK_NAMES.get(lap.track_id, f"Track {lap.track_id}")
        session = _SESSION_NAMES.get(lap.session_type, f"S{lap.session_type}")
        time_str = _format_lap_time(lap.lap_time_ms)
        valid = "" if lap.lap_valid else click.style(" INVALID", fg="red")
        size_kb = lap.path.stat().st_size / 1024

        click.echo(
            f"  {lap.path.name:36s}  Lap {lap.lap_number:2d}  {time_str}"
            f"  {track:16s}  {session:5s}  {lap.num_samples:4d} samples"
            f"  {size_kb:6.0f} KB{valid}"
        )


@cli.command("analyze")
@click.argument("file", type=click.Path(exists=True))
def analyze_cmd(file: str):
    """Analyze a recorded .f1lap file."""
    from f1_service.lap_reader import read_lap
    from f1_service.lap_analyzer import analyze_lap

    lap = read_lap(file)
    click.echo(analyze_lap(lap))


@cli.command("infographic")
@click.argument("file", type=click.Path(exists=True))
@click.option("--output", "-o", default=None, help="Output PNG path (defaults to <input>.png).")
def infographic_cmd(file: str, output):
    """Generate a racing HUD infographic from a .f1lap file."""
    from f1_service.lap_reader import read_lap
    from f1_service.lap_infographic import generate_infographic

    lap = read_lap(file)
    out = generate_infographic(lap, output)
    click.echo(f"Infographic saved to {out}")

    import sys
    if sys.platform == "darwin":
        os.system(f'open "{out}"')
