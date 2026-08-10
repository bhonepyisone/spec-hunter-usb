# Spec Hunter USB — Architecture

## Boot Flow

```
BIOS/UEFI
    │ F12 → select USB
    ▼
Alpine Linux initramfs loads
    │
    ▼
Kernel boots (headless, no X11/Wayland)
    │
    ▼
/etc/local.d/collector.start (auto-run script)
    │
    ├── 1. Load config.yaml
    ├── 2. Start wpa_supplicant + dhcpcd (WiFi connection)
    ├── 3. Wait for network (ping test, timeout 30s)
    ├── 4. Run collector modules
    │       ├── identity.py  → brand, model, serial, BIOS
    │       ├── cpu.py       → name, cores, clocks
    │       ├── ram.py       → capacity, slots, speed
    │       ├── storage.py   → SSD model, SMART, health
    │       ├── battery.py   → health %, cycles
    │       ├── display.py   → resolution, manufacturer
    │       ├── network.py   → WiFi card, MAC, BT
    │       └── camera.py    → v4l2 detection
    │
    ├── 5. Assemble JSON payload
    ├── 6. POST to configured API endpoint
    │       ├── Success → print laptop_id + URL
    │       └── Failure → print error, retry 3x
    │
    ├── 7. Wait 10 seconds (operator reads output)
    └── 8. poweroff
```

## Collector Architecture

```
Each collector follows the same interface:

def collect() -> dict:
    '''Returns a dict matching the Firestore sub-schema.'''

def _primary() -> dict | None:
    '''Primary tool (e.g. dmidecode, smartctl)'''

def _fallback() -> dict | None:
    '''Fallback (e.g. sysfs files)'''

def _collect() -> dict:
    data = _primary()
    if data is None:
        data = _fallback()
    if data is None:
        log.warning("Collector: returning empty")
    return data or {}
```

## Brand Router

```
identity.py parses dmidecode output through a brand-specific router:

1. Read system-manufacturer from dmidecode or /sys/class/dmi/id/
2. Normalize to lowercase: "dell", "lenovo", "hp", "microsoft", "unknown"
3. Route to brand-specific parser:
   - dell: 7-char service tag (strip "Service Tag:" prefix)
   - lenovo: Split MTM and serial (format: "20XJS0M100-PF3XYZ12")
   - hp: 10-char alphanumeric, handle "Not Specified"
   - microsoft: dmidecode likely empty, return "N/A (Surface)"
   - unknown: Return raw dmidecode output

Add new brands by extending the BRAND_PARSERS dict.
```

## Upload Contract

```python
# POST /uploadLaptop
# Headers: Content-Type: application/json, x-api-key: <config>
# Body: {
#   identity: {...},
#   cpu: {...},
#   ram: {...},
#   storage: {...},
#   battery: {...},
#   display: {...},
#   network: {...},
#   camera: {...}
# }
# Response 200: { laptopId: string, url: string }
# Response 401: { error: string }
```

## ISO Build Process

```bash
build-iso.sh:
  1. Download Alpine Linux minimal ISO
  2. Extract + modify initramfs
  3. Add Python + required packages
  4. Add collector/ directory
  5. Add config.yaml
  6. Add /etc/local.d/auto-start script
  7. Repack ISO
  8. Output: releases/spec-hunter-v1.x.iso
```

Alternative: Use `alpine-make-vm-image` for simpler Alpine ISO builds.
