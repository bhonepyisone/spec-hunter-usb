#!/usr/bin/env python3
"""Collect brand, model, serial number, BIOS version.

Uses dmidecode with brand-specific parser (Dell, Lenovo, HP, Surface, Unknown).
Falls back to /sys/class/dmi/id/ sysfs files.
"""

import logging
import subprocess
import re
from pathlib import Path

logger = logging.getLogger("collector.identity")

SYSFS_DMI = Path("/sys/class/dmi/id")


def _run_dmidecode(keyword: str) -> str | None:
    """Run 'dmidecode -s <keyword>' and return stripped output or None."""
    try:
        result = subprocess.run(
            ["dmidecode", "-s", keyword],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def _sysfs_read(filename: str) -> str | None:
    """Read a sysfs dmi file."""
    path = SYSFS_DMI / filename
    if path.exists():
        try:
            return path.read_text().strip()
        except OSError:
            pass
    return None


def _parse_dell_serial(raw: str) -> str:
    """Dell: extract 7-char service tag from dmidecode output."""
    # Strip "Service Tag:" prefix if present
    raw = raw.replace("Service Tag:", "").replace("Service Tag ", "").strip()
    # Return first 7 uppercase chars (Dell service tag format)
    match = re.match(r"^([A-Z0-9]{7})", raw)
    return match.group(1) if match else raw[:7]


def _parse_lenovo_serial(raw: str) -> str:
    """Lenovo: return the serial portion after the dash (PF-XXXXX format)."""
    # Format is typically "MTM-SERIAL" (e.g., "20XJS0M100-PF3XYZ12")
    parts = raw.split("-", 1)
    return parts[1].strip() if len(parts) > 1 else raw


def _parse_hp_serial(raw: str) -> str:
    """HP: handle 'Not Specified' fallback."""
    if raw.lower() in ("not specified", "not provided", ""):
        return ""
    return raw


def collect() -> dict:
    """Collect identity information.

    Returns:
        dict with keys: brand, model, serial_number, bios_version,
                        manufacture_date, motherboard_model, uuid, asset_tag
    """
    result = {
        "brand": "Unknown",
        "model": "Unknown",
        "serial_number": "N/A",
        "bios_version": "N/A",
        "manufacture_date": None,
        "motherboard_model": "N/A",
        "uuid": "N/A",
        "asset_tag": "",
    }

    # --- Brand ---
    brand = _run_dmidecode("system-manufacturer") or _sysfs_read("product_name")
    if brand:
        result["brand"] = brand.strip()

    # --- Model ---
    model = _run_dmidecode("system-product-name") or _sysfs_read("product_version")
    if model:
        result["model"] = model.strip()

    # --- Serial Number (brand-specific) ---
    raw_serial = _run_dmidecode("system-serial-number") or _sysfs_read("product_serial")
    if raw_serial:
        brand_lower = result["brand"].lower()
        if "dell" in brand_lower:
            result["serial_number"] = _parse_dell_serial(raw_serial)
        elif "lenovo" in brand_lower or "thinkpad" in brand_lower:
            result["serial_number"] = _parse_lenovo_serial(raw_serial)
        elif "hp" in brand_lower or "hewlett" in brand_lower:
            result["serial_number"] = _parse_hp_serial(raw_serial)
        elif "microsoft" in brand_lower or "surface" in brand_lower:
            result["serial_number"] = "N/A (Surface — serial unavailable via dmidecode)"
        else:
            result["serial_number"] = raw_serial

    # --- BIOS ---
    bios = _run_dmidecode("bios-version")
    if bios:
        result["bios_version"] = bios

    # --- Manufacture date ---
    date = _run_dmidecode("bios-release-date")
    if date:
        result["manufacture_date"] = date

    # --- Motherboard ---
    mobo = _run_dmidecode("baseboard-product-name") or _sysfs_read("board_name")
    if mobo:
        result["motherboard_model"] = mobo

    # --- UUID ---
    uuid = _run_dmidecode("system-uuid") or _sysfs_read("product_uuid")
    if uuid:
        result["uuid"] = uuid

    # --- Asset tag ---
    tag = _run_dmidecode("chassis-asset-tag") or _sysfs_read("chassis_asset_tag")
    if tag:
        result["asset_tag"] = tag

    logger.info(f"Identity: {result['brand']} {result['model']} (SN: {result['serial_number']})")
    return result


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(collect(), indent=2))
