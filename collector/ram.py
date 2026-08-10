#!/usr/bin/env python3
"""Collect RAM information: total capacity, slot count, speed, DDR type, manufacturer.

Uses dmidecode --type 17 for per-slot details.
"""

import logging
import re
import subprocess

logger = logging.getLogger("collector.ram")


def _run_dmidecode() -> list[str] | None:
    """Run dmidecode -t 17 and return output lines or None."""
    try:
        result = subprocess.run(
            ["dmidecode", "-t", "17"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.splitlines()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def _parse_dmidecode_ram(output: list[str]) -> list[dict]:
    """Parse dmidecode -t 17 output into per-slot dicts.

    Returns list of dicts with keys: size_mb, type, speed_mhz, manufacturer
    Only includes populated slots (non-empty size).
    """
    slots = []
    current = {}

    for line in output:
        line = line.strip()

        # Start of new memory device
        if line.startswith("Memory Device"):
            if current and current.get("size_mb") and current["size_mb"] > 0:
                slots.append(current)
            current = {}

        # Parse fields
        if "Size:" in line and "No Module Installed" not in line:
            match = re.search(r"(\d+)\s*(MB|GB)", line)
            if match:
                value = int(match.group(1))
                unit = match.group(2)
                current["size_mb"] = value * 1024 if unit == "GB" else value

        elif "Type:" in line:
            type_val = line.split("Type:")[1].strip()
            if type_val and type_val != "Unknown" and type_val != "<OUT OF SPEC>":
                current["type"] = type_val

        elif "Speed:" in line and "Unknown" not in line:
            match = re.search(r"(\d+)\s*MHz", line)
            if match:
                current["speed_mhz"] = int(match.group(1))

        elif "Manufacturer:" in line:
            mfr = line.split("Manufacturer:")[1].strip()
            if mfr and mfr != "Not Specified" and mfr != "Unknown":
                current["manufacturer"] = mfr

    # Don't forget the last slot
    if current and current.get("size_mb") and current["size_mb"] > 0:
        slots.append(current)

    return slots


def _parse_lscpu() -> dict:
    """Fallback: get basic RAM info from lscpu."""
    result = {}
    try:
        output = subprocess.run(
            ["lscpu"], capture_output=True, text=True, timeout=5
        ).stdout
        for line in output.splitlines():
            if "Model name" in line:
                pass  # CPU info, not RAM
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return result


def collect() -> dict:
    """Collect RAM information.

    Returns:
        dict with keys: total_gb, slot_count, used_slots, speed,
                       ddr_type, manufacturer
    """
    result = {
        "total_gb": None,
        "slot_count": None,
        "used_slots": None,
        "speed": None,        # MHz — maps to ERP ramSpeed
        "ddr_type": "N/A",
        "manufacturer": "N/A",
    }

    raw = _run_dmidecode()
    if not raw:
        logger.warning("dmidecode -t 17 failed — RAM info unavailable")
        return result

    slots = _parse_dmidecode_ram(raw)
    if not slots:
        logger.warning("No populated RAM slots detected")
        return result

    result["slot_count"] = len(slots)  # May not be total physical slots; dmidecode reports what it sees
    result["used_slots"] = len([s for s in slots if s.get("size_mb", 0) > 0])

    total_mb = sum(s.get("size_mb", 0) for s in slots)
    result["total_gb"] = round(total_mb / 1024, 1) if total_mb else None

    # Speed: use the speed of the first populated slot (all should match)
    if slots and slots[0].get("speed_mhz"):
        result["speed"] = slots[0]["speed_mhz"]

    # DDR type: use most common type across slots
    types = [s.get("type", "") for s in slots if s.get("type")]
    if types:
        result["ddr_type"] = max(set(types), key=types.count)

    # Manufacturer: use most common manufacturer across slots
    mfrs = [s.get("manufacturer", "") for s in slots if s.get("manufacturer")]
    if mfrs:
        result["manufacturer"] = max(set(mfrs), key=mfrs.count)

    logger.info(f"RAM: {result['total_gb']}GB {result['ddr_type']} "
                f"{result['speed']}MHz ({result['used_slots']}/{result['slot_count']} slots)")
    return result


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(collect(), indent=2))
