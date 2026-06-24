# Spec Hunter — USB Boot Collector

Headless Linux Live USB that boots any laptop, collects hardware info (CPU, RAM, storage, battery, display, network), and uploads JSON to a configurable API endpoint. No GUI. Just plug → boot → collect → upload.

**For JM505 shop. Built with Alpine Linux + Python.**

## Stack

| Layer | Technology |
|-------|-----------|
| Base OS | Alpine Linux (headless, ~500MB ISO) |
| Runtime | Python 3.11+ |
| Hardware | subprocess calls to dmidecode, smartctl, nvme, upower, lshw, v4l2 |
| Upload | HTTP POST via `requests` library |
| Config | config.yaml (endpoint URL, API key, WiFi) |

## Quick Start

```bash
# Test collectors on your own laptop
cd collector
python3 identity.py
python3 cpu.py
python3 storage.py

# Build ISO
bash build-iso.sh

# Write to USB
sudo dd if=releases/spec-hunter-v1.0.iso of=/dev/sdX bs=4M status=progress
sync
```

## Project Map

See `SPEC.md` — SDD 6-part specification
See `CLAUDE.md` — Rules of engagement for Claude Code
See `TEST.md` — Test plan with hardware test cases

## Collector Modules

| Module | What It Collects | Primary Tool | Fallback |
|--------|-----------------|--------------|----------|
| identity.py | Brand, model, serial, BIOS | dmidecode | /sys/class/dmi/id/ |
| cpu.py | Name, cores, clocks | lscpu | /proc/cpuinfo |
| ram.py | Capacity, slots, speed | dmidecode | N/A |
| storage.py | SSD model, SMART health | smartctl | nvme-cli, /sys/block/ |
| battery.py | Health %, cycles | upower | /sys/class/power_supply/ |
| display.py | Resolution, manufacturer | edid-decode | /sys/class/drm/*/edid |
| network.py | WiFi, BT, MAC, LAN | lshw | /sys/class/net/ |
| camera.py | Camera detection | v4l2-ctl | /dev/video* |

## Brand Support

Dell, Lenovo, HP, ASUS, Acer, MSI, Huawei, Microsoft Surface, Unknown
