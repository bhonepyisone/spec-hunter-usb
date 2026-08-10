#!/usr/bin/env python3
"""Collect display information: resolution, manufacturer, screen size, model.

Uses edid-decode as primary, falls back to /sys/class/drm/*/edid raw parsing.
"""

import logging
import re
import subprocess
from pathlib import Path

logger = logging.getLogger("collector.display")

DRM_PATH = Path("/sys/class/drm")


def _edid_decode() -> dict:
    """Parse display info via edid-decode."""
    result = {}
    try:
        output = subprocess.run(
            ["edid-decode"], capture_output=True, text=True, timeout=10
        )
        if output.returncode == 0:
            for line in output.stdout.splitlines():
                line = line.strip()
                if "Detailed mode:" in line:
                    match = re.search(r"(\d+)x(\d+)", line)
                    if match:
                        result["resolution"] = f"{match.group(1)}x{match.group(2)}"
                elif "Manufacturer:" in line:
                    result["manufacturer"] = line.split(":")[1].strip()
                elif "Display Product Name:" in line:
                    result["model"] = line.split(":")[1].strip()
                elif "Horizontal resolution" in line:
                    match = re.search(r"(\d+)", line)
                    if match:
                        if result.get("resolution"):
                            w = match.group(1)
                            # Resolution should already be set from Detailed mode
                            pass
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return result


def _parse_edid_binary(edid_path: Path) -> dict:
    """Parse raw EDID binary blob from sysfs."""
    result = {}
    try:
        data = edid_path.read_bytes()
        if len(data) < 128:
            return result

        # Manufacturer ID (bytes 8-9)
        mfr_id = ((data[8] << 8) | data[9])
        # Parse 5-5-5 bit pattern to letters
        char1 = chr(ord('A') + ((mfr_id >> 10) & 0x1F) - 1)
        char2 = chr(ord('A') + ((mfr_id >> 5) & 0x1F) - 1)
        char3 = chr(ord('A') + (mfr_id & 0x1F) - 1)
        if all(c.isalpha() for c in (char1, char2, char3)):
            result["manufacturer"] = f"{char1}{char2}{char3}"

        # Product code (bytes 10-11, little-endian)
        # Not human-readable, skip

        # Basic resolution from EDID Detailed Timing Descriptors
        # This is complex — use xrandr as a simpler method
    except (OSError, IndexError):
        pass
    return result


def _xrandr_resolution() -> str | None:
    """Get current resolution via xrandr (works if X11/Wayland is running)."""
    try:
        output = subprocess.run(
            ["xrandr", "--current"], capture_output=True, text=True, timeout=5
        )
        for line in output.stdout.splitlines():
            if " connected" in line:
                match = re.search(r"(\d+x\d+)", line)
                if match:
                    return match.group(1)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def collect() -> dict:
    """Collect display information.

    Returns:
        dict with keys: resolution, refresh_rate, manufacturer, screen_size_inch, model
    """
    result = {
        "resolution": "N/A",
        "refresh_rate": None,
        "manufacturer": "N/A",
        "screen_size_inch": None,
        "model": "N/A",
    }

    # Try edid-decode first
    edid_data = _edid_decode()
    if edid_data.get("resolution"):
        result["resolution"] = edid_data["resolution"]
    if edid_data.get("manufacturer"):
        result["manufacturer"] = edid_data["manufacturer"]
    if edid_data.get("model"):
        result["model"] = edid_data["model"]

    # Try sysfs EDID files if edid-decode didn't work
    if result["resolution"] == "N/A":
        for connector in DRM_PATH.glob("*-*/edid"):
            if connector.exists():
                edid_info = _parse_edid_binary(connector)
                if edid_info.get("manufacturer"):
                    result["manufacturer"] = edid_info["manufacturer"]
                break

    # Try xrandr as last resort for resolution
    if result["resolution"] == "N/A":
        xr = _xrandr_resolution()
        if xr:
            result["resolution"] = xr

    if result["resolution"]:
        logger.info(f"Display: {result['resolution']} ({result['manufacturer']})")
    else:
        logger.warning("Display: no display info collected")

    return result


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(collect(), indent=2))
