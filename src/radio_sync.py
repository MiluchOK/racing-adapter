"""Sync EdgeTX radio configs between git and mounted SD card."""

import shutil
from pathlib import Path

# Directories to sync between radio SD card and local rc-radio/
SYNC_DIRS = ["MODELS", "RADIO"]
VOLUMES_ROOT = Path("/Volumes")


def find_radio_mount() -> Path | None:
    """Scan /Volumes/ for a mounted EdgeTX SD card (contains RADIO/radio.yml)."""
    if not VOLUMES_ROOT.exists():
        return None
    for vol in VOLUMES_ROOT.iterdir():
        if vol.is_dir() and (vol / "RADIO" / "radio.yml").exists():
            return vol
    return None


def pull_configs(mount: Path, dest: Path) -> list[str]:
    """Copy MODELS/*.yml and RADIO/*.yml from radio to local dest.

    Returns list of copied file paths (relative to dest).
    """
    copied = []
    for dir_name in SYNC_DIRS:
        src_dir = mount / dir_name
        dst_dir = dest / dir_name
        if not src_dir.exists():
            continue
        dst_dir.mkdir(parents=True, exist_ok=True)
        for src_file in sorted(src_dir.glob("*.yml")):
            if src_file.name.startswith("._"):
                continue
            dst_file = dst_dir / src_file.name
            shutil.copy2(src_file, dst_file)
            copied.append(f"{dir_name}/{src_file.name}")
    return copied


def push_configs(src: Path, mount: Path) -> list[str]:
    """Copy MODELS/*.yml and RADIO/*.yml from local src to radio.

    Returns list of copied file paths (relative to src).
    """
    copied = []
    for dir_name in SYNC_DIRS:
        src_dir = src / dir_name
        dst_dir = mount / dir_name
        if not src_dir.exists():
            continue
        dst_dir.mkdir(parents=True, exist_ok=True)
        for src_file in sorted(src_dir.glob("*.yml")):
            if src_file.name.startswith("._"):
                continue
            dst_file = dst_dir / src_file.name
            shutil.copy2(src_file, dst_file)
            copied.append(f"{dir_name}/{src_file.name}")
    return copied
