# Spec: Spec Hunter — USB Boot Collector

## 1. The Gist

A headless Linux Live USB that boots any laptop, collects hardware info (CPU, RAM, storage, battery, display, network), and uploads the JSON to a configurable API endpoint. No GUI. Just plug → boot → collect → upload.

## 2. The Story

A batch of 20 used laptops arrives. Bhone needs to record specs for each one without opening Windows or running installers. He inserts the USB, boots via F12, the laptop auto-connects to shop WiFi, collects everything in 30 seconds, uploads to the web app, and a new row appears. He pulls the USB and moves to the next laptop.

## 3. The "Why"

Manual spec entry takes 5-10 minutes per laptop and is error-prone. The USB tool collects everything in under a minute — brand, model, serial, CPU, RAM, SSD health, battery health, display info — all automatically. No typing, no mistakes, no skipped fields.

## 4. The "Why Not" (Anti-Goals) 🛑

- **No GUI** — Headless CLI only. All interactive tests are in the web app PWA.
- **No OpenCV/pygame** — No graphics libraries on the USB.
- **No build-integrity checking per se** — Just upload what you collect.
- **Only Linux Live USB** — No Windows PE, no macOS boot.
- **Not a diagnostic tool** — Just collection + upload. No stress tests, no burn-in.
- **No persistent storage** — Everything is uploaded. Nothing saved on the USB.
- **No encryption** — API key is in config.yaml on the USB (can be updated per session).
- **No multi-tenant** — Single endpoint per boot session.

## 5. Technical Spec

### Stack

| Layer | Technology |
|-------|-----------|
| Base OS | Alpine Linux (minimal) |
| Runtime | Python 3.11+ |
| Hardware Collection | subprocess calls to: dmidecode, lscpu, smartctl, nvme, upower, edid-decode, lshw, v4l2-ctl, hciconfig |
| Upload | requests library (HTTP POST) |
| Config | config.yaml (endpoint URL, API key, WiFi credentials) |
| ISO Builder | Alpine `mkimage` or Ubuntu `live-build` |

### Architecture

```
USB Inserted → Boot from F12
     │
     ▼
Alpine Linux loads (headless)
     │
     ▼
/etc/local.d/collector.start → main.py
     │
     ├── 1. Connect WiFi (wpa_supplicant + dhcpcd)
     ├── 2. Run all collectors (with fallback chains)
     ├── 3. Assemble JSON
     ├── 4. POST to configured API endpoint
     ├── 5. Print laptop ID + URL
     └── 6. Wait 10s → poweroff
```

### Collector Modules

| Module | Data Collected | Commands Used | Fallback |
|--------|---------------|---------------|----------|
| identity.py | brand, model, serial, BIOS, UUID, motherboard, asset tag | `dmidecode -s system-*` + brand-specific parsing | /sys/class/dmi/id/* |
| cpu.py | name, generation, cores, threads, base/turbo clock | `lscpu`, `/proc/cpuinfo` | Parse /proc/cpuinfo directly |
| ram.py | total, slots, speed, DDR type, manufacturer | `dmidecode -t 17` | N/A |
| storage.py | model, capacity, interface, SMART health, hours, writes, temp | `smartctl -a`, `nvme smart-log` | Parse /sys/block/*/size |
| battery.py | design/current capacity, cycles, health %, manufacturer, serial | `upower -i /org/freedesktop/UPower/devices/battery_BAT0` | /sys/class/power_supply/BAT0/* |
| display.py | resolution, manufacturer, size, model | `edid-decode` | Parse /sys/class/drm/*/edid |
| network.py | WiFi card, Bluetooth, MAC, LAN | `lshw -class network`, `hciconfig`, `ip link` | /sys/class/net/*/address |
| camera.py | camera exists, device path | `v4l2-ctl --list-devices`, `ls /dev/video*` | N/A, camera exists = bool |

### Brand-Specific dmidecode Parsing

| Brand | Serial Command | Quirk |
|-------|---------------|-------|
| Dell | `dmidecode -s system-serial-number` | Some models return "Service Tag" from chassis |
| Lenovo | `dmidecode -s system-serial-number` | Returns MTM + Serial concatenated; parse separately |
| HP | `dmidecode -s system-serial-number` | Some return "Not Specified"; fall back to UUID |
| Microsoft Surface | Not readable via dmidecode | Return empty and log "Surface detected, serial unavailable via dmidecode" |

### Upload API (Configurable)

```yaml
# config.yaml
endpoint:
  url: "https://us-central1-<project>.cloudfunctions.net/uploadLaptop"
  api_key: "shared-secret-here"
wifi:
  ssid: "JM505-Shop"
  password: "wifi-password"
```

### ISO Build

```
Build command:  bash build-iso.sh
Base:           Alpine Linux (~200MB)
With packages:  ~500MB
Destination:    releases/spec-hunter-v1.0.iso
```

Packages included: python3, py3-pip, smartmontools, nvme-cli, dmidecode, upower, edid-decode, lshw, v4l-utils, wpa_supplicant, dhcpcd, util-linux

## 6. Definition of Done

| # | Feature | How to Verify |
|---|---------|---------------|
| 1 | Alpine ISO builds successfully | `bash build-iso.sh` produces a bootable .iso file |
| 2 | ISO boots to terminal on real laptop | Boot USB → see Alpine login prompt (no graphical desktop) |
| 3 | WiFi connects automatically | After boot, check: `ping -c 1 google.com` succeeds |
| 4 | identity.py — brand, model, serial collected | Run on a laptop → JSON has brand/model/serial filled |
| 5 | cpu.py — name, cores, threads, clocks collected | JSON has all CPU fields populated |
| 6 | ram.py — total, slots, speed, DDR type collected | JSON has RAM fields populated |
| 7 | storage.py — model, capacity, SMART data collected | JSON has storage fields with health_pct and power_on_hours |
| 8 | battery.py — health %, cycles collected | JSON has battery fields populated |
| 9 | display.py — resolution, manufacturer collected | JSON has display fields |
| 10 | network.py — WiFi, BT, MAC, LAN collected | JSON has all network fields |
| 11 | camera.py — camera detection | JSON has camera.exists boolean |
| 12 | uploader.py — POST JSON to endpoint | JSON appears in web app as new laptop record |
| 13 | Fallback chains work (dmidecode fails → sysfs) | Test on Surface or VM → graceful fallback |
| 14 | Brand router for Dell/Lenovo/HP serials | Test on each brand → correct serial format |
| 15 | Auto-poweroff after successful upload | Wait 10s after upload → machine powers off |
| 16 | Error handling — no crash on missing hardware | Run on a VM with no battery, no display → graceful N/A values |
| 17 | Code Review — USB Review Agent run before commit | git add → load USB Reviewer → issues fixed or "✅ No issues" → commit |
| 18 | Fix Agent — issues from review are fixed | Reviewer issues resolved, verified with git diff |
