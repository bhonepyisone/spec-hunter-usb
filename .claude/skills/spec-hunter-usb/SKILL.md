---
name: spec-hunter-usb
description: "Complete development workflows for the Spec Hunter USB boot collector — build collectors, handle brand-specific dmidecode, build ISO, test on hardware."
tags: [usb-boot, alpine-linux, hardware-collection, iso-builder, code-review]
---

# Spec Hunter USB — Development Skills

---

## Skill 1: Write a Collector Module

When creating or modifying a collector file in `collector/`.

### Collector Pattern

```python
"""collector/[name].py — Collect [hardware component] information."""

import logging
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


def collect() -> dict:
    """Collect [component] data. Returns dict matching Firestore schema or empty dict."""
    data = _try_primary()
    if data is None:
        data = _try_fallback()
    if data is None:
        logger.warning("[Component] collector: all methods failed")
        return {}
    return data


def _try_primary() -> Optional[dict]:
    """Primary method using [tool command]."""
    try:
        result = subprocess.run(
            ["tool-command", "--flag"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            return _parse(result.stdout)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        logger.warning(f"[Component] primary failed: {e}")
    return None


def _try_fallback() -> Optional[dict]:
    """Fallback using [alternative method, e.g. reading sysfs]."""
    try:
        with open("/sys/class/path/to/file") as f:
            return _parse_fallback(f.read())
    except (FileNotFoundError, PermissionError, OSError) as e:
        logger.warning(f"[Component] fallback failed: {e}")
    return None


def _parse(output: str) -> dict:
    """Parse [tool] output into dict."""
    # Brand-specific parsing logic here
    return {}


def _parse_fallback(output: str) -> dict:
    """Parse fallback output into dict."""
    return {}
```

### Steps

1. Create file `collector/[name].py` using the pattern above
2. Implement `_try_primary` with the system tool command
3. Implement `_try_fallback` with alternative method (sysfs, /proc, etc.)
4. Implement `_parse` to convert tool output to dict
5. Add to `main.py` import and `collect_all()` function
6. Test locally: `python3 collector/[name].py`

### Pitfalls
- `subprocess.run(timeout=10)` — always set timeout to prevent hanging
- `FileNotFoundError` = tool not installed (common on Alpine minimal) — never crash
- `PermissionError` = running without root (shouldn't happen on boot, but can during local testing)
- Parse output defensively — tool output varies by OS version and locale

---

## Skill 2: Add a Brand to the Brand Router

When adding a new brand to `collector/identity.py`.

### Brand Router Pattern

```python
BRAND_PARSERS: dict[str, callable] = {
    "dell":      _parse_dell_serial,
    "lenovo":    _parse_lenovo_serial,
    "hp":        _parse_hp_serial,
    "microsoft": _parse_surface_serial,
    "unknown":   _parse_unknown_serial,
}

def collect() -> dict:
    manufacturer = _get_manufacturer().lower()
    parser = BRAND_PARSERS.get(manufacturer, BRAND_PARSERS["unknown"])
    # ... common logic, then route to parser
```

### Adding a New Brand

1. Get sample dmidecode output from that brand
2. Identify the serial number format
3. Add parser function (e.g. `_parse_acer_serial`)
4. Add to `BRAND_PARSERS` dict: `"acer": _parse_acer_serial`
5. Add test case to `tests/test_identity.py`
6. Update `LLM_Wiki/references/brand-dmi-reference.md` with the new brand

### Pitfalls
- Some manufacturers return different strings: "Dell Inc." vs "Dell" vs "Dell Computer Corporation"
- Normalize: `manufacturer.lower().replace(" inc.", "").replace(" corporation", "").replace(" computer", "").strip()`
- Test with actual dmidecode output — don't guess the format

---

## Skill 3: Build and Test the ISO

When building a bootable ISO for the first time or updating packages.

### ISO Build Steps

```bash
# 1. Ensure dependencies are installed
apk add alpine-sdk grub xorriso squashfs-tools

# 2. Run build script
bash build-iso.sh

# 3. Output in releases/
ls releases/spec-hunter-v*.iso

# 4. Write to USB
sudo dd if=releases/spec-hunter-v1.0.iso of=/dev/sdX bs=4M status=progress
sync

# 5. Insert USB, reboot, F12 → select USB
# 6. Watch terminal output on the laptop screen
# 7. Check web app for new laptop record
```

### Testing Without USB (VM)

```bash
# Convert ISO to VMDK for VirtualBox
qemu-img convert -f raw -O vmdk releases/spec-hunter-v1.0.iso spec-hunter.vmdk

# Or boot directly in QEMU
qemu-system-x86_64 -cdrom releases/spec-hunter-v1.0.iso -m 2048
```

### Pitfalls
- Alpine uses `apk` not `apt` — don't use Ubuntu package names in build script
- `dhcpcd` must start after `wpa_supplicant` connects — use proper init order in `/etc/local.d/`
- Some laptops need `nomodeset` kernel parameter — add to boot config
- UEFI vs BIOS boot — build ISO with both support (grub + isolinux)

---

## Skill 4: Code Review Before Commit

Run before every git commit. Must not be skipped.

### Review Workflow

```
1. git add <files>
2. claude -p 'Review staged collector code for: fallback chains, 
   brand router accuracy, error handling, hardcoded secrets, 
   upload retry logic, compliance with CLAUDE.md rules. List issues.'
3. If issues → claude -p 'Fix the following: [issue list]'
4. git diff → verify fixes
5. git commit
```

---

## Skill 5: Test on Real Hardware

When testing a collector on an actual laptop.

### Test Sequence

```bash
# For each collector, run individually first
cd collector/

python3 identity.py
# Expected: {"brand": "Dell", "model": "Latitude 5420", ...}

python3 storage.py
# Expected: {"model": "Samsung PM981", "health_pct": 96, ...}

python3 battery.py
# Expected: {"health_pct": 89, "cycle_count": 336, ...}

# Then test full assembly (dry run, no upload)
python3 main.py --dry-run
# Expected: complete JSON payload printed to stdout

# Test upload (with valid endpoint in config.yaml)
python3 main.py
# Expected: "Uploading..." → "Laptop ID: xxx" → "Shutting down in 10s"
```

### Minimum Test Hardware
- 1 Dell laptop
- 1 Lenovo laptop
- 1 HP laptop
- 1 desktop (no battery, no webcam — tests fallback chains)
- 1 VM (tests boot process without real hardware)
