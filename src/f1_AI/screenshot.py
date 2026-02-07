"""Screenshot capture for Chiaki PS5 Remote Play window on macOS."""

import sys
from pathlib import Path

# Check platform - this module only works on macOS
if sys.platform != "darwin":
    raise ImportError("Screenshot capture only supported on macOS")

import Quartz
import numpy as np


def find_chiaki_window() -> tuple[int | None, str, int, int]:
    """
    Find the Chiaki streaming window.

    Returns:
        Tuple of (window_id, window_name, width, height).
        window_id is None if not found.
    """
    window_list = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
        Quartz.kCGNullWindowID
    )

    best_window = None
    best_area = 0

    for window in window_list:
        owner = window.get("kCGWindowOwnerName", "")
        name = window.get("kCGWindowName", "")
        layer = window.get("kCGWindowLayer", 0)

        if "chiaki" not in owner.lower():
            continue

        bounds = window.get("kCGWindowBounds", {})
        width = bounds.get("Width", 0)
        height = bounds.get("Height", 0)
        window_id = window.get("kCGWindowNumber")

        # Skip tiny windows (not the main stream window)
        if width < 640 or height < 360:
            continue

        # Skip non-main layer windows (menus, tooltips, etc.)
        if layer != 0:
            continue

        area = width * height
        if area > best_area:
            best_area = area
            best_window = (window_id, name if name else "Stream", width, height)

    if best_window:
        return best_window

    return None, "", 0, 0


def list_chiaki_windows() -> list[dict]:
    """
    List all Chiaki windows for debugging.

    Returns:
        List of window info dicts with id, name, width, height, layer.
    """
    window_list = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
        Quartz.kCGNullWindowID
    )

    chiaki_windows = []
    for window in window_list:
        owner = window.get("kCGWindowOwnerName", "")
        if "chiaki" in owner.lower():
            chiaki_windows.append({
                "id": window.get("kCGWindowNumber"),
                "name": window.get("kCGWindowName", ""),
                "width": window.get("kCGWindowBounds", {}).get("Width", 0),
                "height": window.get("kCGWindowBounds", {}).get("Height", 0),
                "layer": window.get("kCGWindowLayer", 0),
            })
    return chiaki_windows


def capture_window(window_id: int) -> np.ndarray | None:
    """
    Capture a specific window by its ID.

    Args:
        window_id: The macOS window ID to capture.

    Returns:
        numpy array in BGR format (OpenCV compatible), or None if capture failed.
    """
    image = Quartz.CGWindowListCreateImage(
        Quartz.CGRectNull,
        Quartz.kCGWindowListOptionIncludingWindow,
        window_id,
        Quartz.kCGWindowImageBoundsIgnoreFraming | Quartz.kCGWindowImageNominalResolution
    )

    if image is None:
        return None

    width = Quartz.CGImageGetWidth(image)
    height = Quartz.CGImageGetHeight(image)

    if width == 0 or height == 0:
        return None

    bytes_per_row = width * 4
    color_space = Quartz.CGColorSpaceCreateDeviceRGB()
    buffer = bytearray(height * bytes_per_row)

    context = Quartz.CGBitmapContextCreate(
        buffer,
        width,
        height,
        8,
        bytes_per_row,
        color_space,
        Quartz.kCGImageAlphaPremultipliedFirst | Quartz.kCGBitmapByteOrder32Little
    )

    if context is None:
        return None

    Quartz.CGContextDrawImage(context, Quartz.CGRectMake(0, 0, width, height), image)

    # Convert to numpy array in BGR format (OpenCV compatible)
    arr = np.frombuffer(bytes(buffer), dtype=np.uint8).reshape(height, width, 4)
    bgr = arr[:, :, :3].copy()

    return bgr


def capture_chiaki_screenshot(output_path: str | Path | None = None) -> tuple[np.ndarray | None, str]:
    """
    Find and capture the Chiaki streaming window.

    Args:
        output_path: Optional path to save the screenshot. If None, only returns the array.

    Returns:
        Tuple of (image_array, status_message).
        image_array is None if capture failed.
    """
    window_id, window_name, width, height = find_chiaki_window()

    if window_id is None:
        windows = list_chiaki_windows()
        if not windows:
            return None, "Chiaki is not running or no windows found"
        else:
            return None, f"Chiaki running but no stream window found. Windows: {windows}"

    frame = capture_window(window_id)

    if frame is None:
        return None, f"Failed to capture window {window_id} ({window_name})"

    if output_path:
        import cv2
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(path), frame)
        return frame, f"Captured {width}x{height} from '{window_name}' -> {path}"

    return frame, f"Captured {width}x{height} from '{window_name}'"


def wait_for_chiaki_window(timeout: float = 60, poll_interval: float = 1.0) -> tuple[int | None, str]:
    """
    Wait for Chiaki streaming window to appear.

    Args:
        timeout: Maximum seconds to wait.
        poll_interval: Seconds between checks.

    Returns:
        Tuple of (window_id, status_message).
    """
    import time

    start = time.time()
    while time.time() - start < timeout:
        window_id, name, width, height = find_chiaki_window()
        if window_id:
            return window_id, f"Found window '{name}' ({width}x{height}) after {time.time() - start:.1f}s"
        time.sleep(poll_interval)

    return None, f"Timeout after {timeout}s waiting for Chiaki window"
