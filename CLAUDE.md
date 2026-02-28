# Project Memory

## Build & Run
- This project uses **uv** as the package manager
- Run scripts with: `uv run <script>`
- Example: `uv run src/f1_udp_listener.py`

## CLI
- `uv run racing-adapter --help` — list available commands
- `uv run racing-adapter F1_listener_start` — start F1 UDP telemetry listener (default port 20777)
- `uv run racing-adapter F1_listener_start --port 30000` — use a custom port
- `uv run racing-adapter F1_listener_start --no-serial` — run without Arduino connection
- `uv run racing-adapter F1_listener_start --no-mqtt` — run without MQTT (serial only)
- `uv run racing-adapter firmware_upload` — compile and upload Arduino UNO R4 firmware
- `uv run racing-adapter circuitry-diagnostics` — upload and run Arduino hardware diagnostics (pin readback, servo sweep, motor ramp)
- `uv run racing-adapter diagnostics` — send test steering/throttle commands via MQTT
- `uv run racing-adapter calibrate` — interactive servo trim calibration via MQTT
- `uv run racing-adapter esp32-firmware-upload` — compile and upload ESP32 serial firmware
- `uv run racing-adapter esp32-diagnostics` — upload and run ESP32 hardware diagnostics

## Arduino Config
- **`arduino_config.json`** at project root controls Arduino serial connection
  - `serial_port`: `"auto"` for auto-detection, or explicit path like `"/dev/cu.usbmodem101"`
  - `baud_rate`: must match firmware (default 115200)
  - `servo_pin`: documents which Arduino pin the steering servo is on (pin 9 is hardcoded in firmware)
