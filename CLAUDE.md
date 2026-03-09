# Project Memory

## Build & Run
- This project uses **uv** as the package manager
- Run scripts with: `uv run <script>`
- Example: `uv run src/f1_udp_listener.py`

## CLI — racing-adapter (hardware/firmware)
- `uv run racing-adapter --help` — list available commands
- `uv run racing-adapter firmware_upload` — compile and upload Arduino UNO R4 firmware
- `uv run racing-adapter circuitry-diagnostics` — upload and run Arduino hardware diagnostics (pin readback, servo sweep, motor ramp)
- `uv run racing-adapter diagnostics` — send test steering/throttle commands via MQTT
- `uv run racing-adapter calibrate` — interactive servo trim calibration via MQTT
- `uv run racing-adapter esp32-firmware-upload` — compile and upload ESP32 serial firmware
- `uv run racing-adapter esp32-diagnostics` — upload and run ESP32 hardware diagnostics
- `uv run racing-adapter radio-pull` — pull EdgeTX configs from mounted radio SD card into `rc-radio/`
- `uv run racing-adapter radio-push` — push EdgeTX configs from `rc-radio/` to mounted radio SD card
- `uv run racing-adapter radio-pull --mount-point /Volumes/EDGETX` — specify mount point manually

## CLI — f1-service (F1 telemetry, in `f1-service/`)
- `cd f1-service && uv run f1-service --help` — list available commands
- `uv run f1-service f1-router` — start F1 telemetry router: UDP → MQTT + serial + scoreboard (default port 20777)
- `uv run f1-service f1-router --port 30000` — use a custom port
- `uv run f1-service f1-router --no-serial` — run without Arduino connection
- `uv run f1-service f1-router --no-mqtt` — run without MQTT (serial only)
- `uv run f1-service f1-router --no-scoreboard` — run without lap record reporting
- `uv run f1-service f1-router --record-raw` — enable raw UDP packet capture to `captures/`
- `uv run f1-service f1-router --record-raw --captures-dir my_caps` — custom captures directory
- `uv run f1-service f1-router --influxdb` — enable InfluxDB telemetry publishing (requires `INFLUXDB_TOKEN` and `INFLUXDB_ORG` env vars)
- `uv run f1-service f1-router --influxdb --influxdb-url http://host:8086` — custom InfluxDB URL (default: `http://localhost:8086`)
- InfluxDB env vars: `INFLUXDB_TOKEN` (required), `INFLUXDB_ORG` (required), `INFLUXDB_BUCKET` (default: `f1`)
- `uv run f1-service replay captures/<file>.f1raw` — replay a capture as UDP packets
- `uv run f1-service replay <file> --speed 2 --loop` — replay at 2x speed, looping
- `uv run f1-service captures` — list .f1raw capture files with stats
- `uv run f1-service analyze <file.f1lap>` — analyze a recorded lap with full telemetry report
- `uv run f1-service infographic <file.f1lap>` — generate a racing HUD infographic PNG from a lap file
- `uv run f1-service infographic <file.f1lap> -o output.png` — specify output PNG path

## CAD — rc-cad/
- `rc-cad/src/` — source CAD files (OpenSCAD, FreeCAD, etc.)
- `rc-cad/stl/` — exported STL files ready for slicing/printing
- Physical parts design for the RC car (mounts, brackets, chassis components, etc.)

## Arduino Config
- **`arduino_config.json`** at project root controls Arduino serial connection
  - `serial_port`: `"auto"` for auto-detection, or explicit path like `"/dev/cu.usbmodem101"`
  - `baud_rate`: must match firmware (default 115200)
  - `servo_pin`: documents which Arduino pin the steering servo is on (pin 9 is hardcoded in firmware)
