"""Sync EdgeTX radio configs between git and mounted SD card."""

import shutil
from pathlib import Path

# Directories to sync between radio SD card and local rc-radio/
# SOUNDS excluded — too large for git (~104MB of language packs).
# Re-download from https://github.com/EdgeTX/edgetx-sdcard-sounds/releases
SYNC_DIRS = ["MODELS", "RADIO", "FIRMWARE", "SCRIPTS", "BACKUP"]
VOLUMES_ROOT = Path("/Volumes")


def find_radio_mount() -> Path | None:
    """Scan /Volumes/ for a mounted EdgeTX SD card (contains RADIO/radio.yml)."""
    if not VOLUMES_ROOT.exists():
        return None
    for vol in VOLUMES_ROOT.iterdir():
        if vol.is_dir() and (vol / "RADIO" / "radio.yml").exists():
            return vol
    return None


def _sync_dir(src_dir: Path, dst_dir: Path) -> list[str]:
    """Recursively copy all files from src_dir to dst_dir, skipping macOS metadata.

    Returns list of copied file paths (relative to src_dir).
    """
    copied = []
    if not src_dir.exists():
        return copied
    for src_file in sorted(src_dir.rglob("*")):
        if not src_file.is_file():
            continue
        if src_file.name.startswith("._"):
            continue
        rel = src_file.relative_to(src_dir)
        dst_file = dst_dir / rel
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dst_file)
        copied.append(str(rel))
    return copied


def pull_configs(mount: Path, dest: Path) -> list[str]:
    """Copy all synced directories from radio to local dest.

    Returns list of copied file paths (relative to dest).
    """
    copied = []
    for dir_name in SYNC_DIRS:
        for rel in _sync_dir(mount / dir_name, dest / dir_name):
            copied.append(f"{dir_name}/{rel}")
    return copied


def push_configs(src: Path, mount: Path) -> list[str]:
    """Copy all synced directories from local src to radio.

    Returns list of copied file paths (relative to src).
    """
    copied = []
    for dir_name in SYNC_DIRS:
        for rel in _sync_dir(src / dir_name, mount / dir_name):
            copied.append(f"{dir_name}/{rel}")
    return copied
