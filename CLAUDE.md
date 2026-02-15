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

## Arduino Config
- **`arduino_config.json`** at project root controls Arduino serial connection
  - `serial_port`: `"auto"` for auto-detection, or explicit path like `"/dev/cu.usbmodem101"`
  - `baud_rate`: must match firmware (default 115200)
  - `servo_pin`: documents which Arduino pin the steering servo is on (pin 9 is hardcoded in firmware)
