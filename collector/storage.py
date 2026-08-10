#!/usr/bin/env python3
"""Collect storage information: primary + secondary drive.

Uses smartctl (SATA) or nvme-cli (NVMe) for SMART data.
Detects dual-storage (SSD + HDD, or dual SSD) via lsblk.
Falls back to /sys/block for basic capacity info.

Output includes both `storage` and `storage2` (if second drive exists).
"""

import json
import logging
import re
import subprocess

logger = logging.getLogger("collector.storage")


def _get_block_devices() -> list[dict]:
    """Get list of physical drives (not partitions) via lsblk.

    Returns list of dicts with: name, model, size_bytes, rota (1=HDD, 0=SSD)
    """
    devices = []
    try:
        result = subprocess.run(
            ["lsblk", "-d", "-o", "NAME,MODEL,SIZE,ROTA", "-J", "--bytes"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            for dev in data.get("blockdevices", []):
                name = dev.get("name", "")
                # Skip loop, ram, zram devices
                if name.startswith(("loop", "ram", "zram")):
                    continue
                devices.append({
                    "name": name,
                    "model": dev.get("model", "").strip() or f"/dev/{name}",
                    "size_bytes": dev.get("size", 0),
                    "rota": dev.get("rota", 1),  # 1=HDD, 0=SSD
                })
    except (FileNotFoundError, json.JSONDecodeError, subprocess.TimeoutExpired) as e:
        logger.warning(f"lsblk failed: {e}")
    return devices


def _smartctl_info(device: str) -> dict:
    """Get SMART data for a SATA or NVMe device.

    Returns dict with SMART fields or empty dict on failure.
    """
    result = {
        "model": "N/A",
        "capacity_gb": None,
        "interface": "unknown",
        "health_pct": None,
        "power_on_hours": None,
        "power_cycles": None,
        "total_bytes_written": None,
        "remaining_life_pct": None,
        "temperature": None,
        "bad_sectors": None,
        "smart_status": "N/A",
    }

    dev_path = f"/dev/{device}"

    # Check if NVMe (nvme0n1, nvme1n1, etc.)
    is_nvme = device.startswith("nvme")

    try:
        if is_nvme:
            # Use nvme-cli for NVMe drives
            result["interface"] = "NVMe"
            smart_log = subprocess.run(
                ["nvme", "smart-log", dev_path],
                capture_output=True, text=True, timeout=10
            )
            if smart_log.returncode == 0:
                for line in smart_log.stdout.splitlines():
                    line = line.strip()
                    if "percentage_used" in line:
                        # NVMe reports wear as percentage_used (0-100)
                        match = re.search(r"(\d+)", line.split(":")[1])
                        if match:
                            # Convert "used" to "remaining"
                            result["remaining_life_pct"] = 100 - int(match.group(1))
                            result["health_pct"] = result["remaining_life_pct"]
                    elif "power_on_hours" in line:
                        match = re.search(r"(\d+)", line.split(":")[1])
                        if match:
                            result["power_on_hours"] = int(match.group(1))
                    elif "power_cycles" in line:
                        match = re.search(r"(\d+)", line.split(":")[1])
                        if match:
                            result["power_cycles"] = int(match.group(1))
                    elif "temperature" in line:
                        match = re.search(r"(\d+)", line.split(":")[1])
                        if match:
                            result["temperature"] = int(match.group(1))
                    elif "data_units_written" in line:
                        match = re.search(r"(\d+)", line.split(":")[1])
                        if match:
                            # Convert from 1000-byte units to bytes
                            result["total_bytes_written"] = int(match.group(1)) * 1000

            # Get NVMe model from id-ctrl
            id_ctrl = subprocess.run(
                ["nvme", "id-ctrl", dev_path],
                capture_output=True, text=True, timeout=10
            )
            if id_ctrl.returncode == 0:
                for line in id_ctrl.stdout.splitlines():
                    if "mn" in line:  # Model number field
                        model_val = line.split(":")[1].strip().strip('"')
                        if model_val:
                            result["model"] = model_val
                            break
        else:
            # Use smartctl for SATA drives
            result["interface"] = "SATA" if not device.startswith("sd") else "SATA"
            smart_output = subprocess.run(
                ["smartctl", "-a", dev_path],
                capture_output=True, text=True, timeout=15
            )
            if smart_output.returncode in (0, 1):  # smartctl returns 1 for some PASS conditions
                output = smart_output.stdout

                # Model
                match = re.search(r"Device Model:\s+(.+)", output)
                if match:
                    result["model"] = match.group(1).strip()

                # SMART status
                if "SMART overall-health self-assessment test result: PASSED" in output:
                    result["smart_status"] = "PASS"
                elif "SMART overall-health" in output:
                    result["smart_status"] = "FAIL"
                else:
                    result["smart_status"] = "N/A"

                # Parse SMART attributes
                in_table = False
                for line in output.splitlines():
                    if "ID# ATTRIBUTE_NAME" in line:
                        in_table = True
                        continue
                    if in_table and line.strip() == "":
                        in_table = False
                        continue
                    if in_table:
                        parts = line.split()
                        if len(parts) >= 10:
                            attr_name = parts[1]
                            raw_value = parts[9] if len(parts) > 9 else parts[-1]

                            if "Power_On_Hours" in attr_name:
                                try:
                                    result["power_on_hours"] = int(raw_value)
                                except ValueError:
                                    pass
                            elif "Power_Cycle_Count" in attr_name:
                                try:
                                    result["power_cycles"] = int(raw_value)
                                except ValueError:
                                    pass
                            elif "Temperature_Celsius" in attr_name:
                                try:
                                    result["temperature"] = int(raw_value)
                                except ValueError:
                                    pass
                            elif "Reallocated_Sector_Ct" in attr_name:
                                try:
                                    result["bad_sectors"] = int(raw_value)
                                except ValueError:
                                    pass
                            elif "Total_LBAs_Written" in attr_name:
                                try:
                                    result["total_bytes_written"] = int(raw_value) * 512
                                except ValueError:
                                    pass
                            elif "Wear_Leveling_Count" in attr_name:
                                # Some SSDs report wear leveling as a proxy for health
                                try:
                                    result["remaining_life_pct"] = int(raw_value)
                                except ValueError:
                                    pass
                            elif "Percentage_Used" in attr_name:
                                try:
                                    used = int(raw_value)
                                    result["remaining_life_pct"] = 100 - used
                                except ValueError:
                                    pass
                            elif "Available_Reserved_Space" in attr_name:
                                try:
                                    result["health_pct"] = int(raw_value)
                                except ValueError:
                                    pass

    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        logger.warning(f"SMART collection failed for {dev_path}: {e}")

    return result


def _capacity_from_sysfs(device: str) -> int | None:
    """Fallback: get capacity from /sys/block/<dev>/size (512-byte sectors)."""
    try:
        path = f"/sys/block/{device}/size"
        with open(path) as f:
            sectors = int(f.read().strip())
            return sectors * 512  # bytes
    except (FileNotFoundError, ValueError, OSError):
        return None


def collect() -> dict:
    """Collect storage information for primary and secondary drives.

    Returns:
        dict with 'storage' and optionally 'storage2' keys.
        Each sub-dict has: model, capacity_gb, interface, health_pct,
                          power_on_hours, power_cycles, total_bytes_written,
                          remaining_life_pct, temperature, bad_sectors, smart_status
        'storage2' is omitted entirely if no second drive detected.
    """
    result = {
        "model": "N/A",
        "capacity_gb": None,
        "interface": "unknown",
        "health_pct": None,
        "power_on_hours": None,
        "power_cycles": None,
        "total_bytes_written": None,
        "remaining_life_pct": None,
        "temperature": None,
        "bad_sectors": None,
        "smart_status": "N/A",
    }

    devices = _get_block_devices()
    if not devices:
        logger.warning("No block devices detected")
        return result

    # Primary drive = first physical drive
    primary = devices[0]
    primary_name = primary["name"]

    # Get SMART data for primary
    smart = _smartctl_info(primary_name)
    result.update(smart)

    # If SMART didn't give us a model, use lsblk model
    if result["model"] == "N/A" and primary.get("model"):
        result["model"] = primary["model"]

    # Capacity from SMART or fallback to sysfs
    if not result["capacity_gb"]:
        raw_capacity = _capacity_from_sysfs(primary_name)
        if raw_capacity:
            result["capacity_gb"] = round(raw_capacity / (1024**3), 1)

    # Interface from device name
    if primary_name.startswith("nvme"):
        result["interface"] = "NVMe"
    elif primary["rota"] == 1:
        result["interface"] = "SATA (HDD)"
    else:
        result["interface"] = "SATA (SSD)"

    # If no health_pct from SMART attributes, use remaining_life_pct as proxy
    if result["health_pct"] is None and result["remaining_life_pct"] is not None:
        result["health_pct"] = result["remaining_life_pct"]

    logger.info(f"Storage: {result['model']} ({result['capacity_gb']}GB, "
                f"{result['interface']}, health={result['health_pct']}%)")

    # --- Second drive (storage2) ---
    if len(devices) > 1:
        secondary = devices[1]
        secondary_name = secondary["name"]
        smart2 = _smartctl_info(secondary_name)

        storage2 = {
            "model": smart2.get("model", secondary["model"]) if smart2.get("model") != "N/A" else secondary["model"],
            "capacity_gb": smart2.get("capacity_gb"),
            "interface": smart2.get("interface", "unknown"),
            "health_pct": smart2.get("health_pct"),
            "power_on_hours": smart2.get("power_on_hours"),
            "smart_status": smart2.get("smart_status", "N/A"),
        }

        # Capacity fallback
        if not storage2["capacity_gb"]:
            raw_cap2 = _capacity_from_sysfs(secondary_name)
            if raw_cap2:
                storage2["capacity_gb"] = round(raw_cap2 / (1024**3), 1)

        # Interface
        if secondary_name.startswith("nvme"):
            storage2["interface"] = "NVMe"
        elif secondary["rota"] == 1:
            storage2["interface"] = "SATA (HDD)"
        else:
            storage2["interface"] = "SATA (SSD)"

        result["storage2"] = storage2
        logger.info(f"Storage2: {storage2['model']} ({storage2['capacity_gb']}GB, "
                    f"{storage2['interface']})")

    return result


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(collect(), indent=2))
