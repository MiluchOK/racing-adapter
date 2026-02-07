# Racing Adapter

HID device adapter for racing peripherals.

## Setup

This project is managed with [`uv`](https://github.com/astral-sh/uv). Install
all dependencies (or resync after editing `pyproject.toml`) with:

```
uv sync
```

`uv` will create an isolated environment under `.venv` and install the packages
declared in `pyproject.toml` / `uv.lock`, including `hidapi`.

## List HID Devices

To list all connected HID devices:

```bash
uv run python src/list_hid_devices.py
```

## Calibration

Before using the wheel reader, run the calibration wizard to map your inputs:

```bash
uv run python src/calibrate.py
```

The wizard will guide you through:
1. Recording baseline (nothing pressed)
2. Steering calibration (turn wheel left/right)
3. Throttle, brake, and clutch pedal mapping
4. Button mapping (optional)

This creates a `calibration_profile.json` file in the project root.

## Read Wheel Data

After calibration, view live wheel data with a human-readable display:

```bash
uv run python src/read_fanatec.py
```

`uv run` ensures the script uses the environment prepared by `uv sync`.
