#!/usr/bin/env python3
"""Spec Hunter USB — Main entry point.

Corrected workflow:
  1. Load config.yaml
  2. Connect WiFi (handled by /etc/local.d/collector.start before main.py)
  3. Wait for network (max 30s)
  4. Run all 8 collectors → assemble JSON payload
  5. Serve the LOCAL UI on this laptop: http://127.0.0.1:8080
       shows collected specs, takes customer name, runs manual tests
       (keyboard/display/sound/mic/touchpad/ports) with pass/fail + failure
       point. BLOCKS until the operator submits or aborts.
  6. On submit: POST { ...payload, customer_name, test_results } to the
     configured endpoint (with retry). On abort/idle: save payload locally.
  7. Wait 10s, poweroff.
"""

import json
import logging
import subprocess
import sys
import time
from pathlib import Path

from collector import identity, cpu, ram, storage, battery, display, network, camera
from collector.uploader import Config, load_config, upload
from collector import ui

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("spec-hunter")


def assemble_payload() -> dict:
    """Run all collectors and assemble the JSON payload."""
    logger.info("=== Collecting hardware info ===")
    payload = {
        "identity": identity.collect(),
        "cpu": cpu.collect(),
        "ram": ram.collect(),
        "storage": storage.collect(),
        "battery": battery.collect(),
        "display": display.collect(),
        "network": network.collect(),
        "camera": camera.collect(),
    }
    brand = payload["identity"].get("brand", "Unknown")
    model = payload["identity"].get("model", "Unknown")
    serial = payload["identity"].get("serial_number", "N/A")
    logger.info(f"Collected: {brand} {model} (SN: {serial})")
    logger.info(f"  CPU: {payload['cpu'].get('name', 'N/A')}")
    logger.info(f"  RAM: {payload['ram'].get('total_gb', '?')}GB")
    logger.info(f"  Storage: {payload['storage'].get('model', 'N/A')} ({payload['storage'].get('capacity_gb', '?')}GB)")
    logger.info(f"  Battery: {payload['battery'].get('health_pct', '?')}%")
    logger.info(f"  Display: {payload['display'].get('resolution', 'N/A')}")
    logger.info(f"  Camera: {'Yes' if payload['camera'].get('exists') else 'No'}")
    return payload


def save_fallback(payload: dict) -> None:
    path = "/tmp/last_upload.json"
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    logger.warning(f"Payload saved to {path}")


def wait_for_network(timeout_s: int = 30) -> bool:
    for attempt in range(max(1, timeout_s // 5)):
        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "5", "8.8.8.8"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                logger.info("Network OK")
                return True
        except Exception:  # noqa: BLE001
            pass
        logger.warning(f"Waiting for network ({attempt + 1}/{timeout_s // 5})...")
        time.sleep(5)
    return False


def main() -> None:
    logger.info("Spec Hunter USB Collector v1.0 — Starting")

    config_path = Path(__file__).parent.parent / "config.yaml"
    if not config_path.exists():
        logger.error("config.yaml not found. Create one from .env.example")
        sys.exit(1)
    config = load_config(str(config_path))
    logger.info(f"Endpoint: {config.endpoint.url}")

    if not wait_for_network():
        logger.error("No network — collecting and saving locally")
        payload = assemble_payload()
        save_fallback(payload)
        sys.exit(1)

    payload = assemble_payload()

    logger.info("=== Starting UI — open http://127.0.0.1:8080 on THIS laptop ===")
    upl = ui.serve_ui(payload, config, upload)

    if upl.ok:
        logger.info(f"Uploaded laptop {upl.laptop_id}. Powering off in 10 seconds...")
    else:
        logger.warning("No upload — payload saved. Powering off in 10 seconds...")

    time.sleep(10)
    subprocess.run(["poweroff"], timeout=5)


if __name__ == "__main__":
    main()