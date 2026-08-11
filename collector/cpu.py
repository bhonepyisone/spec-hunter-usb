#!/usr/bin/env python3
"""Collect CPU information: name, generation, cores, threads, base/turbo clock.

Uses lscpu and /proc/cpuinfo.
"""

import logging
import re
import subprocess

logger = logging.getLogger("collector.cpu")


def _extract_generation(name: str) -> int | None:
    """Extract CPU generation from name string.
    E.g., 'Intel Core i5-1145G7' → 11, 'Intel Core i7-1360P' → 13,
    'Intel Core i3-6100U' → 6 (NOT 61).
    """
    match = re.search(r"i[3-9]-(\d{1,2})", name)
    if match:
        gen = int(match.group(1))
        # 2-digit gens are 10..14 (e.g. i5-1145G7 → 11); anything else is a
        # 1-digit gen with a model suffix (i3-6100U → 61, so → 6).
        return gen if 10 <= gen <= 14 else gen // 10
    # AMD: Ryzen 5 5600U → 5000 series
    match = re.search(r"(\d{4})[A-Z]", name)
    if match:
        return int(match.group(1)[:2])
    return None


def collect() -> dict:
    """Collect CPU information.

    Returns:
        dict with keys: name, generation, cores, threads, base_clock, turbo_clock
    """
    result = {
        "name": "N/A",
        "generation": None,
        "cores": None,
        "threads": None,
        "base_clock": None,
        "turbo_clock": None,
    }

    try:
        output = subprocess.run(
            ["lscpu"], capture_output=True, text=True, timeout=5
        ).stdout

        for line in output.splitlines():
            line = line.strip()

            if "Model name" in line:
                name = line.split(":")[1].strip()
                if name:
                    result["name"] = name
                    result["generation"] = _extract_generation(name)

            elif "CPU(s)" in line and not line.startswith("On-line"):
                try:
                    result["threads"] = int(line.split(":")[1].strip())
                except (ValueError, IndexError):
                    pass

            elif "Core(s) per socket" in line:
                try:
                    result["cores"] = int(line.split(":")[1].strip())
                except (ValueError, IndexError):
                    pass

            elif "CPU max MHz" in line:
                try:
                    result["turbo_clock"] = round(
                        float(line.split(":")[1].strip()), 1
                    )
                except (ValueError, IndexError):
                    pass

            elif "CPU min MHz" in line:
                try:
                    result["base_clock"] = round(
                        float(line.split(":")[1].strip()), 1
                    )
                except (ValueError, IndexError):
                    pass

        # Alternative: parse /proc/cpuinfo for core count
        if not result["cores"]:
            try:
                with open("/proc/cpuinfo") as f:
                    cores = set()
                    for line in f:
                        if "physical id" in line:
                            cores.add(line.split(":")[1].strip())
                    result["cores"] = len(cores) if cores else None
            except OSError:
                pass

        logger.info(f"CPU: {result['name']} ({result['cores']}C/{result['threads']}T, "
                    f"{result['base_clock']}/{result['turbo_clock']}GHz)")

    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        logger.warning(f"CPU collection failed: {e}")

    return result


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(collect(), indent=2))
