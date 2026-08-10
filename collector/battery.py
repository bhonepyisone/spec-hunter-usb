#!/usr/bin/env python3
"""Collect battery information: health %, cycle count, capacities.

Uses upower as primary, falls back to /sys/class/power_supply/BAT0 sysfs files.
"""

import logging
import re
import subprocess
from pathlib import Path

logger = logging.getLogger("collector.battery")

SYSFS_BAT0 = Path("/sys/class/power_supply/BAT0")


def _upower_path() -> str | None:
    """Find the upower battery path."""
    try:
        result = subprocess.run(
            ["upower", "-e"], capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            if "BAT" in line:
                return line.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def _upower_collect(device_path: str) -> dict:
    """Collect battery data via upower."""
    result = {}
    try:
        output = subprocess.run(
            ["upower", "-i", device_path],
            capture_output=True, text=True, timeout=10
        ).stdout

        for line in output.splitlines():
            line = line.strip()
            if "energy-full-design" in line:
                val = line.split(":")[1].strip().split()[0]
                try:
                    result["design_capacity"] = round(float(val) * 1000)  # Wh → mWh
                except ValueError:
                    pass
            elif "energy-full" in line:
                val = line.split(":")[1].strip().split()[0]
                try:
                    result["current_capacity"] = round(float(val) * 1000)
                except ValueError:
                    pass
            elif "cycle count" in line:
                try:
                    result["cycle_count"] = int(line.split(":")[1].strip())
                except ValueError:
                    pass
            elif "percentage" in line:
                val = line.split(":")[1].strip().replace("%", "")
                try:
                    result["health_pct"] = round(float(val))
                except ValueError:
                    pass
            elif "vendor" in line.lower():
                result["manufacturer"] = line.split(":")[1].strip()
            elif "serial" in line.lower():
                serial = line.split(":")[1].strip()
                if serial and serial != "Unknown":
                    result["serial"] = serial

    except (subprocess.TimeoutExpired, IndexError) as e:
        logger.warning(f"upower failed: {e}")

    return result


def _sysfs_collect() -> dict:
    """Fallback: read battery info from sysfs."""
    result = {}
    if not SYSFS_BAT0.exists():
        return result

    try:
        mappings = {
            "design_capacity": "energy_full_design",
            "current_capacity": "energy_full",
            "cycle_count": "cycle_count",
            "manufacturer": "manufacturer",
            "serial": "serial_number",
        }
        for key, sysfs_file in mappings.items():
            path = SYSFS_BAT0 / sysfs_file
            if path.exists():
                val = path.read_text().strip()
                if val:
                    if key in ("design_capacity", "current_capacity"):
                        result[key] = int(val)  # μWh
                    elif key == "cycle_count":
                        result[key] = int(val)
                    else:
                        result[key] = val

        # Calculate health %
        if result.get("design_capacity") and result.get("current_capacity"):
            result["health_pct"] = round(
                result["current_capacity"] / result["design_capacity"] * 100
            )
    except (OSError, ValueError) as e:
        logger.warning(f"sysfs battery failed: {e}")

    return result


def collect() -> dict:
    """Collect battery information.

    Returns:
        dict with keys: design_capacity, current_capacity, cycle_count,
                       health_pct, manufacturer, serial
    """
    result = {
        "design_capacity": None,
        "current_capacity": None,
        "cycle_count": None,
        "health_pct": None,
        "manufacturer": "N/A",
        "serial": "N/A",
    }

    # Primary: upower
    upower_dev = _upower_path()
    if upower_dev:
        data = _upower_collect(upower_dev)
        result.update(data)

    # Fallback: sysfs (if upower returned nothing)
    if not result["health_pct"] and not result["cycle_count"]:
        data = _sysfs_collect()
        result.update(data)

    # Calculate health % if we have capacities but no health
    if result["health_pct"] is None:
        if result.get("current_capacity") and result.get("design_capacity"):
            result["health_pct"] = round(
                result["current_capacity"] / result["design_capacity"] * 100
            )

    logger.info(f"Battery: {result['health_pct']}% health, "
                f"{result['cycle_count']} cycles")
    return result


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(collect(), indent=2))
