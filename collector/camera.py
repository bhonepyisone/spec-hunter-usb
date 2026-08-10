#!/usr/bin/env python3
"""Detect camera presence: check for video devices and v4l2 capabilities.

Uses v4l2-ctl and /dev/video* enumeration.
"""

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger("collector.camera")


def collect() -> dict:
    """Detect camera presence.

    Returns:
        dict with keys: exists (bool), device_path (str), model (str)
    """
    result = {
        "exists": False,
        "device_path": "",
        "model": "N/A",
    }

    # Check /dev/video* devices
    video_devs = sorted(Path("/dev").glob("video*"))
    if not video_devs:
        logger.info("Camera: no /dev/video* devices found")
        return result

    # Try v4l2-ctl for details
    for dev in video_devs:
        try:
            output = subprocess.run(
                ["v4l2-ctl", "-D", "-d", str(dev)],
                capture_output=True, text=True, timeout=5
            )
            if output.returncode == 0:
                model = "N/A"
                for line in output.stdout.splitlines():
                    if "Card type" in line:
                        model = line.split(":")[1].strip()
                        break
                    elif "Model" in line:
                        model = line.split(":")[1].strip()
                        break

                # Check if it's a camera (not a video capture card, TV tuner, etc.)
                # Most internal laptop cameras show "Integrated Camera" or "Integrated Webcam"
                is_camera = any(kw in output.stdout.lower() for kw in
                                ["camera", "webcam", "integrated"])

                if is_camera or len(video_devs) <= 2:
                    result["exists"] = True
                    result["device_path"] = str(dev)
                    if model != "N/A":
                        result["model"] = model
                    logger.info(f"Camera: found at {dev} ({result['model']})")
                    return result
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    # Fallback: just report that /dev/video* exists
    if video_devs:
        result["exists"] = True
        result["device_path"] = str(video_devs[0])
        logger.info(f"Camera: detected at {video_devs[0]} (v4l2 unavailable)")
    else:
        logger.info("Camera: no camera detected")

    return result


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(collect(), indent=2))
