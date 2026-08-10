# OpenCode Prompt — Build Spec Hunter USB Collector

## First

Read `SPEC.md`, `CLAUDE.md`, `LLM_Wiki/architecture.md`, and `LLM_Wiki/references/upload-contract-spec.md` to understand the full architecture. Then read all files in `collector/` — I've created stubs with full implementations for most modules.

## Current state

The `collector/` directory has working code for:

| File | Status |
|------|--------|
| `main.py` | ✅ Entry point — needs `requests` + `pyyaml` in requirements |
| `identity.py` | ✅ Full implementation with brand router (Dell/Lenovo/HP/Surface) |
| `cpu.py` | ✅ Full implementation with generation extractor |
| `ram.py` | ✅ Full implementation with dmidecode parsing (includes `speed` = ramSpeed) |
| `storage.py` | ✅ Full implementation with primary + secondary drive (includes `health_pct` = storageHealth, `power_on_hours`, `storage2`) |
| `battery.py` | ✅ Full implementation with upower + sysfs fallback |
| `display.py` | ✅ Full implementation with edid-decode + sysfs + xrandr fallback |
| `network.py` | ✅ Full implementation with lshw + ip link + Bluetooth |
| `camera.py` | ✅ Full implementation with v4l2 detection |
| `uploader.py` | ✅ Full implementation with retry logic + Config loader |
| `__init__.py` | ✅ Package init (empty) |

## What needs to be done (in order)

### Step 1: Add dependencies

Edit `requirements.txt` to include:
```
requests>=2.31.0
pyyaml>=6.0
```

No other external packages — all collectors use stdlib + subprocess.

Commit: `Add: requests and pyyaml to requirements.txt`

### Step 2: Create tests

The `tests/` directory has `test_identity.py`, `test_storage.py`, `test_battery.py` already. Review them — they may be stubs or incomplete. For each test:

- Test with mocked subprocess calls (use `unittest.mock.patch`)
- Test fallback chains (primary tool fails → fallback succeeds → returns graceful defaults)
- Test brand router (Dell, Lenovo, HP, Surface, Unknown)
- Test edge cases (no battery, no display, no camera)

Commit: `Add: unit tests for collector modules`

### Step 3: Create build-iso.sh

Create `build-iso.sh` that:

1. Downloads Alpine Linux minimal ISO
2. Extracts + modifies initramfs to include:
   - Python 3.11+ + pip
   - `requests` + `pyyaml`
   - `smartmontools`, `nvme-cli`, `dmidecode`, `upower`, `edid-decode`, `lshw`, `v4l-utils`, `wpa_supplicant`, `dhcpcd`, `util-linux`
   - The entire `collector/` directory
   - `config.yaml`
   - `/etc/local.d/collector.start` (auto-run script)
3. Repacks into `releases/spec-hunter-v1.0.iso`

Alternatively, use `alpine-make-vm-image` for simpler builds.

Commit: `Add: ISO builder script (build-iso.sh)`

### Step 4: Complete config.yaml

Create `config.yaml` from `.env.example`:

```yaml
endpoint:
  url: "https://us-central1-<project>.cloudfunctions.net/uploadLaptop"
  api_key: "your-shared-secret"
wifi:
  ssid: "JM505-Shop"
  password: "wifi-password"
```

Commit: `Add: config.yaml template`

### Step 5: Verify on real hardware

Run each collector on the user's own laptop:
```bash
cd spec-hunter-usb
python3 collector/identity.py
python3 collector/cpu.py
python3 collector/ram.py
python3 collector/storage.py
python3 collector/battery.py
python3 collector/display.py
python3 collector/network.py
python3 collector/camera.py
```

Each should output valid JSON. If any collector crashes or returns empty dict, fix it.

Commit: `Fix: collector issues found during hardware testing`

### Step 6: Full integration test

Run the full pipeline:
```bash
python3 collector/main.py
```

This should:
1. Check for config.yaml
2. Wait for network
3. Run all collectors
4. Try to upload
5. Print result or save fallback

If upload fails (no endpoint yet), verify it saves to `/tmp/last_upload.json` correctly.

## What NOT to touch

| Area | Reason |
|------|--------|
| CLAUDE.md | Already complete |
| LLM_Wiki/architecture.md | Already complete |
| LLM_Wiki/api-docs.md | Already complete |
| SPEC.md (sections 1-4) | Already complete |
| SPEC.md DoD (rows 1-17) | Already complete |
| `.githooks/`, `.mcp.json`, `.env.example`, `.gitignore` | Already configured |
| `.claude/skills/`, `.claude/agents/` | Already created |

## Upload JSON format (what each collector outputs)

The final payload sent to the API looks like this (matching `upload-contract-spec.md`):

```json
{
  "identity": { "brand": "Dell", "model": "Latitude 5420", "serial_number": "ABC123", ... },
  "cpu": { "name": "Intel Core i5-1145G7", "cores": 4, "threads": 8, ... },
  "ram": { "total_gb": 16, "speed": 3200, "ddr_type": "DDR4", ... },
  "storage": { "model": "Samsung PM981", "capacity_gb": 512, "health_pct": 96, "power_on_hours": 1742, ... },
  "storage2": { "model": "WD Blue 1TB HDD", "capacity_gb": 1000, "health_pct": 84, ... },
  "battery": { "health_pct": 89, "cycle_count": 336, ... },
  "display": { "resolution": "1920x1080", "manufacturer": "LG Display", ... },
  "network": { "wifi_card": "Intel Wi-Fi 6 AX201", "bluetooth": "Bluetooth 5.2", ... },
  "camera": { "exists": true, "device_path": "/dev/video0", ... }
}
```

After each step, run the relevant collector to verify it works. DO NOT auto-commit — user reviews and commits manually.
