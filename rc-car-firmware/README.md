# RC Car Firmware

Arduino firmware for RC car control.

## Hardware

- **Board**: Arduino Uno R4 WiFi
- **FQBN**: `arduino:renesas_uno:unor4wifi`

## Requirements

- Arduino IDE 2.0+ or Arduino CLI
- USB-C cable

## Upload Instructions

### Using Arduino IDE

1. Open `rc-car-firmware.ino` in Arduino IDE
2. Select your board: **Tools > Board > Arduino UNO R4 Boards > Arduino Uno R4 WiFi**
3. Select the port: **Tools > Port** (e.g., `/dev/cu.usbmodem*` on macOS)
4. Click **Upload** (or press `Cmd+U` / `Ctrl+U`)

### Using Arduino CLI

```bash
# Install arduino-cli if not already installed
brew install arduino-cli

# Initialize configuration
arduino-cli config init

# Update core index
arduino-cli core update-index

# Install Arduino Uno R4 board core
arduino-cli core install arduino:renesas_uno

# Compile
arduino-cli compile --fqbn arduino:renesas_uno:unor4wifi rc-car-firmware

# Upload (replace port with yours, check with: arduino-cli board list)
arduino-cli upload -p /dev/cu.usbmodem* --fqbn arduino:renesas_uno:unor4wifi rc-car-firmware
```

### Common Board FQBNs

| Board | FQBN |
|-------|------|
| **Arduino Uno R4 WiFi** | `arduino:renesas_uno:unor4wifi` |
| Arduino Uno R4 Minima | `arduino:renesas_uno:minima` |
| Arduino Uno (classic) | `arduino:avr:uno` |
| Arduino Nano | `arduino:avr:nano` |
| ESP32 Dev Module | `esp32:esp32:esp32` |

## Troubleshooting

- **Port not found**: Ensure USB-C cable supports data transfer (not charge-only)
- **Permission denied**: Add user to `dialout` group (Linux) or check System Settings > Privacy & Security (macOS)
- **Board not found in IDE**: Install the Arduino UNO R4 Boards package via **Tools > Board > Boards Manager**
- **Find your port**: Run `arduino-cli board list` to see connected boards
