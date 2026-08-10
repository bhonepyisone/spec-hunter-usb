#!/usr/bin/env python3
"""Collect network information: WiFi card, Bluetooth, MAC, LAN adapter.

Uses lshw, hciconfig, ip link.
"""

import logging
import re
import subprocess

logger = logging.getLogger("collector.network")


def _classify_device(device: dict) -> dict:
    """Classify a network device dict into results."""
    result = {}
    desc = device.get("description", "").lower()
    if "wireless" in desc or "wifi" in desc:
        result["wifi_card"] = device.get("product", "N/A")
        result["wifi_vendor"] = device.get("vendor", "")
    elif "ethernet" in desc:
        result["lan_adapter"] = device.get("product", "N/A")
        if not result.get("mac_address"):
            result["mac_address"] = device.get("serial", "N/A")
    return result


def _lshw_network() -> dict:
    """Get network hardware info via lshw."""
    result = {}
    try:
        output = subprocess.run(
            ["lshw", "-class", "network"], capture_output=True, text=True, timeout=10
        )
        if output.returncode == 0:
            current = {}
            for line in output.stdout.splitlines():
                if "*-network" in line:
                    if current and current.get("logical_name"):
                        result.update(_classify_device(current))
                    current = {}
                elif ":" in line and current is not None:
                    key, val = line.split(":", 1)
                    key = key.strip().lower().replace(" ", "_")
                    val = val.strip()
                    if key in ("product", "vendor", "serial", "logical_name", "description"):
                        current[key] = val
            # Process last device
            if current and current.get("logical_name"):
                result.update(_classify_device(current))
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return result


def _ip_mac() -> dict:
    """Get MAC addresses via ip link."""
    result = {}
    try:
        output = subprocess.run(
            ["ip", "link"], capture_output=True, text=True, timeout=5
        )
        current_iface = ""
        for line in output.stdout.splitlines():
            line = line.strip()
            # Track interface name: "3: wlp2s0: <...>"
            iface_match = re.match(r"\d+:\s+(\S+):", line)
            if iface_match:
                current_iface = iface_match.group(1)
            # Look for link/ether
            match = re.search(r"link/ether\s+([0-9a-f:]{17})", line, re.IGNORECASE)
            if match:
                mac = match.group(1).lower()
                # Prefer WiFi MAC
                if "wlan" in current_iface or "wlp" in current_iface:
                    result["mac_address"] = mac
                elif "eth" in current_iface or "enp" in current_iface:
                    if "mac_address" not in result:
                        result["mac_address"] = mac
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return result


def _bluetooth_info() -> str:
    """Get Bluetooth version via hciconfig or btmgmt."""
    try:
        # Try hciconfig first
        output = subprocess.run(
            ["hciconfig"], capture_output=True, text=True, timeout=5
        )
        if output.returncode == 0:
            for line in output.stdout.splitlines():
                if "BD Address" in line:
                    return "Bluetooth detected"
                if "UP RUNNING" in line:
                    return "Bluetooth (active)"

        # Try btmgmt as fallback
        output = subprocess.run(
            ["btmgmt", "info"], capture_output=True, text=True, timeout=5
        )
        if output.returncode == 0 and "hci" in output.stdout.lower():
            return "Bluetooth detected"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return "N/A"


def collect() -> dict:
    """Collect network information.

    Returns:
        dict with keys: wifi_card, bluetooth, mac_address, lan_adapter
    """
    result = {
        "wifi_card": "N/A",
        "bluetooth": "N/A",
        "mac_address": "N/A",
        "lan_adapter": "N/A",
    }

    # Primary: lshw
    lshw = _lshw_network()
    if lshw.get("wifi_card"):
        result["wifi_card"] = lshw["wifi_card"]
    if lshw.get("lan_adapter"):
        result["lan_adapter"] = lshw["lan_adapter"]
    if not result["lan_adapter"] and lshw.get("mac_address"):
        result["mac_address"] = lshw["mac_address"]

    # MAC from ip link (more reliable)
    ip_info = _ip_mac()
    if ip_info.get("mac_address"):
        result["mac_address"] = ip_info["mac_address"]

    # Bluetooth
    result["bluetooth"] = _bluetooth_info()

    logger.info(f"Network: WiFi={result['wifi_card']}, BT={result['bluetooth']}, "
                f"MAC={result['mac_address']}")
    return result


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(collect(), indent=2))
