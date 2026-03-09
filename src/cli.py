"""CLI entry point for racing-adapter."""

import json
import time
from pathlib import Path

import click

CONFIG_PATH = Path.cwd() / "arduino_config.json"


@click.group()
def cli():
    """Racing adapter CLI."""


@cli.command("firmware_upload")
@click.option("--fqbn", default="arduino:renesas_uno:unor4wifi", show_default=True, help="Fully qualified board name.")
@click.option("--port", default=None, help="Serial port (auto-detected if omitted).")
def firmware_upload(fqbn: str, port: str | None):
    """Compile and upload the Arduino firmware."""
    import shutil
    import subprocess

    if not shutil.which("arduino-cli"):
        raise click.ClickException("arduino-cli not found. Install it first: https://arduino.github.io/arduino-cli/installation/")

    sketch_dir = Path.cwd() / "rc-car-firmware"
    if not sketch_dir.exists():
        raise click.ClickException(f"Sketch directory not found: {sketch_dir}")

    # Auto-detect port
    if port is None:
        result = subprocess.run(
            ["arduino-cli", "board", "list", "--format", "json"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise click.ClickException(f"Failed to list boards: {result.stderr.strip()}")

        import json as _json
        boards = _json.loads(result.stdout)
        detected = boards.get("detected_ports", [])
        for entry in detected:
            matching = entry.get("matching_boards", [])
            if matching:
                port = entry.get("port", {}).get("address")
                board_name = matching[0].get("name", "Unknown")
                click.echo(f"Detected: {board_name} on {port}")
                break

        if not port:
            raise click.ClickException("No Arduino board detected. Connect the board or pass --port.")

    # Compile
    click.echo("Compiling...")
    comp = subprocess.run(
        ["arduino-cli", "compile", "--fqbn", fqbn, str(sketch_dir)],
        capture_output=True, text=True,
    )
    if comp.returncode != 0:
        raise click.ClickException(f"Compilation failed:\n{comp.stderr}")
    click.echo(comp.stdout.strip())

    # Upload
    click.echo(f"Uploading to {port}...")
    up = subprocess.run(
        ["arduino-cli", "upload", "-p", port, "--fqbn", fqbn, str(sketch_dir)],
        capture_output=True, text=True,
    )
    if up.returncode != 0:
        raise click.ClickException(f"Upload failed:\n{up.stderr}")
    click.echo(up.stdout.strip())

    click.echo("Firmware uploaded successfully.")


@cli.command("calibrate")
@click.option("--mqtt-broker", default="10.0.0.102:1883", show_default=True, help="MQTT broker host:port.")
@click.option("--throttle", default=0.1, show_default=True, help="Throttle level during calibration (0.0-1.0).")
def calibrate(mqtt_broker: str, throttle: float):
    """Interactive servo calibration. Runs motor at low power while you adjust steering trim.

    Use left/right arrow keys to adjust trim (10us steps).
    Hold Shift (use </>) for fine 1us steps.
    Press Enter to save, q to quit without saving.
    """
    import sys
    import termios
    import tty

    import paho.mqtt.client as mqtt

    broker_host, _, broker_port = mqtt_broker.partition(":")
    broker_port = int(broker_port) if broker_port else 1883

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    try:
        client.connect(broker_host, broker_port)
    except Exception as e:
        raise click.ClickException(f"Cannot connect to MQTT broker {broker_host}:{broker_port}: {e}")

    client.loop_start()
    click.echo(f"Connected to MQTT broker {broker_host}:{broker_port}")

    # Load existing trim
    config_path = Path.cwd() / "arduino_config.json"
    config = {}
    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)
    trim_us = config.get("steering_trim_us", 0)

    # Send initial trim and throttle
    client.publish("f1/steering_trim", str(trim_us), qos=0)
    client.publish("f1/steering", "0.0", qos=0)
    client.publish("f1/throttle", str(throttle), qos=0)

    click.echo(f"Throttle set to {throttle:.0%}")
    click.echo(f"Current trim: {trim_us}us")
    click.echo()
    click.echo("  left/right arrows  adjust trim +/- 10us")
    click.echo("  < / >              adjust trim +/- 1us")
    click.echo("  Enter              save and exit")
    click.echo("  q                  quit without saving")
    click.echo()

    def _print_trim():
        click.echo(f"\r  trim = {trim_us:+d}us  (servo center = {1500 + trim_us}us)    ", nl=False)

    _print_trim()

    # Raw terminal input
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        while True:
            ch = sys.stdin.read(1)
            if ch == "\r" or ch == "\n":
                # Save
                click.echo()
                config["steering_trim_us"] = trim_us
                with open(config_path, "w") as f:
                    json.dump(config, f, indent=2)
                    f.write("\n")
                click.echo(f"Saved steering_trim_us={trim_us} to {config_path.name}")
                break
            elif ch == "q" or ch == "Q":
                click.echo()
                click.echo("Quit without saving.")
                break
            elif ch == "\x1b":
                # Arrow key escape sequence
                seq = sys.stdin.read(2)
                if seq == "[D":  # left arrow
                    trim_us -= 10
                elif seq == "[C":  # right arrow
                    trim_us += 10
                client.publish("f1/steering_trim", str(trim_us), qos=0)
                client.publish("f1/steering", "0.0", qos=0)
                _print_trim()
            elif ch == "<" or ch == ",":
                trim_us -= 1
                client.publish("f1/steering_trim", str(trim_us), qos=0)
                client.publish("f1/steering", "0.0", qos=0)
                _print_trim()
            elif ch == ">" or ch == ".":
                trim_us += 1
                client.publish("f1/steering_trim", str(trim_us), qos=0)
                client.publish("f1/steering", "0.0", qos=0)
                _print_trim()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    # Stop motor
    client.publish("f1/throttle", "0.0", qos=0)
    client.publish("f1/steering", "0.0", qos=0)
    time.sleep(0.2)
    client.loop_stop()
    client.disconnect()
    click.echo("Motor stopped.")


@cli.command("diagnostics")
@click.option("--mqtt-broker", default="10.0.0.102:1883", show_default=True, help="MQTT broker host:port.")
def diagnostics(mqtt_broker: str):
    """Send test steering & throttle commands to the Arduino via MQTT."""
    import paho.mqtt.client as mqtt

    broker_host, _, broker_port = mqtt_broker.partition(":")
    broker_port = int(broker_port) if broker_port else 1883

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    try:
        client.connect(broker_host, broker_port)
    except Exception as e:
        raise click.ClickException(f"Cannot connect to MQTT broker {broker_host}:{broker_port}: {e}")

    client.loop_start()
    click.echo(f"Connected to MQTT broker {broker_host}:{broker_port}")
    click.echo("Starting steering & throttle test...\n")

    steps = [
        ("CENTER",        0.0, 0.0),
        ("FULL LEFT",    -1.0, 0.0),
        ("CENTER",        0.0, 0.0),
        ("FULL RIGHT",    1.0, 0.0),
        ("CENTER",        0.0, 0.0),
        ("HALF THROTTLE", 0.0, 0.5),
        ("FULL THROTTLE", 0.0, 1.0),
        ("IDLE",          0.0, 0.0),
    ]

    for label, steer, throttle in steps:
        click.echo(f"  -> {label:16s}  steer={steer:+.1f}  throttle={throttle:.1f}")
        client.publish("f1/steering", str(steer), qos=0)
        client.publish("f1/throttle", str(throttle), qos=0)
        time.sleep(1.5)

    client.loop_stop()
    client.disconnect()
    click.echo("\nDone. If the servo moved left-center-right and throttle responded, everything works.")


DIAG_STYLE = {
    "PASS": click.style(" PASS ", fg="white", bg="green", bold=True),
    "FAIL": click.style(" FAIL ", fg="white", bg="red", bold=True),
    "WARN": click.style(" WARN ", fg="black", bg="yellow", bold=True),
    "INFO": click.style(" INFO ", fg="white", bg="blue"),
}


def _read_diagnostics(port: str, baud: int = 115200, timeout_s: int = 45):
    """Open serial port and collect diagnostics lines until DIAG:END or timeout."""
    import serial as pyserial

    results = []
    ser = pyserial.Serial(port, baud, timeout=1)
    time.sleep(2)  # wait for Arduino reset

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        raw = ser.readline()
        if not raw:
            continue
        line = raw.decode("utf-8", errors="ignore").strip()
        if not line:
            continue
        if line == "DIAG:END":
            break
        if line.startswith("TEST:"):
            parts = line.split(":", 3)  # TEST : name : status : detail
            if len(parts) == 4:
                results.append((parts[1], parts[2], parts[3]))
        # Skip DIAG:START and other lines
    ser.close()
    return results


def _print_report(results):
    """Pretty-print the diagnostics report."""
    click.echo()
    click.echo(click.style("── Diagnostics Report ─────────────────────────", bold=True))
    click.echo()

    current_section = None
    counts = {"PASS": 0, "FAIL": 0, "WARN": 0, "INFO": 0}

    for name, status, detail in results:
        counts[status] = counts.get(status, 0) + 1

        # Section header when test name changes
        section = name.split("_")[0] if "_" in name else name
        if section != current_section:
            current_section = section
            click.echo()

        badge = DIAG_STYLE.get(status, status)
        click.echo(f"  {badge}  {name:20s}  {detail}")

    click.echo()
    click.echo(click.style("── Summary ────────────────────────────────────", bold=True))
    summary_parts = []
    if counts.get("PASS"):
        summary_parts.append(click.style(f'{counts["PASS"]} passed', fg="green"))
    if counts.get("FAIL"):
        summary_parts.append(click.style(f'{counts["FAIL"]} failed', fg="red", bold=True))
    if counts.get("WARN"):
        summary_parts.append(click.style(f'{counts["WARN"]} warnings', fg="yellow"))
    if counts.get("INFO"):
        summary_parts.append(f'{counts["INFO"]} info')
    click.echo("  " + ", ".join(summary_parts))
    click.echo()

    if counts.get("FAIL"):
        click.echo(click.style("  ✗ Issues detected — review FAIL lines above.", fg="red", bold=True))
    elif counts.get("WARN"):
        click.echo(click.style("  ⚠ Warnings present — review WARN lines above.", fg="yellow"))
    else:
        click.echo(click.style("  ✓ All automated checks passed.", fg="green", bold=True))
    click.echo()


@cli.command("circuitry-diagnostics")
@click.option("--fqbn", default="arduino:renesas_uno:unor4wifi", show_default=True, help="Fully qualified board name.")
@click.option("--port", default=None, help="Serial port (auto-detected if omitted).")
def circuitry_diagnostics(fqbn: str, port: str | None):
    """Upload and run automated hardware tests, then display a report.

    Tests pin readback (shorts to GND/VCC), analog voltages, LED matrix,
    servo sweep, and motor PWM ramp. Results are read back over serial
    and displayed as a colour-coded report.

    Run `firmware_upload` afterwards to restore the normal MQTT firmware.
    """
    import shutil
    import subprocess

    if not shutil.which("arduino-cli"):
        raise click.ClickException("arduino-cli not found. Install it first: https://arduino.github.io/arduino-cli/installation/")

    sketch_dir = Path.cwd() / "rc-car-firmware" / "circuitry-diagnostics"
    if not sketch_dir.exists():
        raise click.ClickException(f"Sketch directory not found: {sketch_dir}")

    # Auto-detect port
    if port is None:
        result = subprocess.run(
            ["arduino-cli", "board", "list", "--format", "json"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise click.ClickException(f"Failed to list boards: {result.stderr.strip()}")

        import json as _json
        boards = _json.loads(result.stdout)
        detected = boards.get("detected_ports", [])
        for entry in detected:
            matching = entry.get("matching_boards", [])
            if matching:
                port = entry.get("port", {}).get("address")
                board_name = matching[0].get("name", "Unknown")
                click.echo(f"Detected: {board_name} on {port}")
                break

        if not port:
            raise click.ClickException("No Arduino board detected. Connect the board or pass --port.")

    # Compile
    click.echo("Compiling circuitry diagnostics sketch...")
    comp = subprocess.run(
        ["arduino-cli", "compile", "--fqbn", fqbn, str(sketch_dir)],
        capture_output=True, text=True,
    )
    if comp.returncode != 0:
        raise click.ClickException(f"Compilation failed:\n{comp.stderr}")
    click.echo(comp.stdout.strip())

    # Upload
    click.echo(f"Uploading to {port}...")
    up = subprocess.run(
        ["arduino-cli", "upload", "-p", port, "--fqbn", fqbn, str(sketch_dir)],
        capture_output=True, text=True,
    )
    if up.returncode != 0:
        raise click.ClickException(f"Upload failed:\n{up.stderr}")
    click.echo(up.stdout.strip())

    # Read results from serial
    click.echo("\nRunning diagnostics (this takes ~15 seconds)...")
    results = _read_diagnostics(port)

    if not results:
        raise click.ClickException("No diagnostics data received. Check the serial connection.")

    _print_report(results)
    click.echo("Run `racing-adapter firmware_upload` to restore normal firmware.")


# ── ESP32 commands ────────────────────────────────────────────────────

ESP32_FQBN = "esp32:esp32:esp32doit-devkit-v1"


def _detect_board(fqbn_hint: str | None = None):
    """Auto-detect board port via arduino-cli. Returns (port, board_name)."""
    import json as _json
    import subprocess

    result = subprocess.run(
        ["arduino-cli", "board", "list", "--format", "json"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise click.ClickException(f"Failed to list boards: {result.stderr.strip()}")

    boards = _json.loads(result.stdout)
    detected = boards.get("detected_ports", [])
    for entry in detected:
        matching = entry.get("matching_boards", [])
        if matching:
            port = entry.get("port", {}).get("address")
            board_name = matching[0].get("name", "Unknown")
            return port, board_name

    return None, None


def _compile_and_upload(sketch_dir: Path, fqbn: str, port: str | None, label: str):
    """Compile and upload a sketch. Auto-detects port if None."""
    import shutil
    import subprocess

    if not shutil.which("arduino-cli"):
        raise click.ClickException(
            "arduino-cli not found. Install it first: https://arduino.github.io/arduino-cli/installation/"
        )

    if not sketch_dir.exists():
        raise click.ClickException(f"Sketch directory not found: {sketch_dir}")

    if port is None:
        port, board_name = _detect_board(fqbn)
        if not port:
            raise click.ClickException(
                "No board detected. Connect the board or pass --port."
            )
        click.echo(f"Detected: {board_name} on {port}")

    click.echo(f"Compiling {label}...")
    comp = subprocess.run(
        ["arduino-cli", "compile", "--fqbn", fqbn, str(sketch_dir)],
        capture_output=True, text=True,
    )
    if comp.returncode != 0:
        raise click.ClickException(f"Compilation failed:\n{comp.stderr}")
    click.echo(comp.stdout.strip())

    click.echo(f"Uploading to {port}...")
    up = subprocess.run(
        ["arduino-cli", "upload", "-p", port, "--fqbn", fqbn, str(sketch_dir)],
        capture_output=True, text=True,
    )
    if up.returncode != 0:
        raise click.ClickException(f"Upload failed:\n{up.stderr}")
    click.echo(up.stdout.strip())

    return port


@cli.command("esp32-firmware-upload")
@click.option("--fqbn", default=ESP32_FQBN, show_default=True, help="Fully qualified board name.")
@click.option("--port", default=None, help="Serial port (auto-detected if omitted).")
def esp32_firmware_upload(fqbn: str, port: str | None):
    """Compile and upload the ESP32 serial firmware."""
    sketch_dir = Path.cwd() / "esp32-firmware"
    _compile_and_upload(sketch_dir, fqbn, port, "ESP32 serial firmware")
    click.echo("ESP32 firmware uploaded successfully.")


@cli.command("esp32-diagnostics")
@click.option("--fqbn", default=ESP32_FQBN, show_default=True, help="Fully qualified board name.")
@click.option("--port", default=None, help="Serial port (auto-detected if omitted).")
def esp32_diagnostics(fqbn: str, port: str | None):
    """Upload and run ESP32 hardware diagnostics, then display a report.

    Tests pin readback (GPIO18/19), servo sweep, ESC ramp, and
    analog baseline. Results are read back over serial and displayed
    as a colour-coded report.

    Run `esp32-firmware-upload` afterwards to restore normal firmware.
    """
    sketch_dir = Path.cwd() / "esp32-firmware" / "esp32-diagnostics"
    port = _compile_and_upload(sketch_dir, fqbn, port, "ESP32 diagnostics sketch")

    click.echo("\nRunning diagnostics (this takes ~20 seconds)...")
    results = _read_diagnostics(port)

    if not results:
        raise click.ClickException("No diagnostics data received. Check the serial connection.")

    _print_report(results)
    click.echo("Run `racing-adapter esp32-firmware-upload` to restore normal firmware.")


# ── Radio commands ───────────────────────────────────────────────


@cli.command("radio-pull")
@click.option("--mount-point", default=None, help="Radio mount point (auto-detected if omitted).")
def radio_pull(mount_point: str | None):
    """Pull EdgeTX configs from mounted radio SD card into rc-radio/."""
    from radio_sync import find_radio_mount, pull_configs

    if mount_point:
        mount = Path(mount_point)
        if not mount.exists():
            raise click.ClickException(f"Mount point not found: {mount_point}")
    else:
        mount = find_radio_mount()
        if not mount:
            raise click.ClickException(
                "No EdgeTX radio found in /Volumes/. "
                "Connect the radio via USB and select 'USB Storage (SD)', "
                "or pass --mount-point."
            )

    click.echo(f"Radio found at {mount}")
    dest = Path.cwd() / "rc-radio"
    copied = pull_configs(mount, dest)

    if not copied:
        click.echo("No .yml config files found on radio.")
    else:
        for f in copied:
            click.echo(f"  ← {f}")
        click.echo(f"Pulled {len(copied)} file(s) into rc-radio/")


@cli.command("radio-push")
@click.option("--mount-point", default=None, help="Radio mount point (auto-detected if omitted).")
def radio_push(mount_point: str | None):
    """Push EdgeTX configs from rc-radio/ to mounted radio SD card."""
    from radio_sync import find_radio_mount, push_configs

    if mount_point:
        mount = Path(mount_point)
        if not mount.exists():
            raise click.ClickException(f"Mount point not found: {mount_point}")
    else:
        mount = find_radio_mount()
        if not mount:
            raise click.ClickException(
                "No EdgeTX radio found in /Volumes/. "
                "Connect the radio via USB and select 'USB Storage (SD)', "
                "or pass --mount-point."
            )

    click.echo(f"Radio found at {mount}")
    src = Path.cwd() / "rc-radio"
    if not src.exists():
        raise click.ClickException("rc-radio/ directory not found.")

    copied = push_configs(src, mount)

    if not copied:
        click.echo("No .yml config files found in rc-radio/.")
    else:
        for f in copied:
            click.echo(f"  → {f}")
        click.echo(f"Pushed {len(copied)} file(s) to radio")
