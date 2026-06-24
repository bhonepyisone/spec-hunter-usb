# Test Plan: Spec Hunter — USB Boot Collector

## Test Levels

| Level | What | When | Tool |
|-------|------|------|------|
| Unit | Individual collector functions | After each collector module | pytest |
| Integration | JSON assembly → upload | After all collectors wired | Manual script test |
| E2E | Boot USB on real hardware → upload | Before release | Physical USB test on 3-5 laptops |
| Edge | Missing hardware, permission errors | Before release | VM with stripped config |

## Test Cases

### Feature: identity.py

| # | Test Case | Steps | Expected | Status |
|---|-----------|-------|----------|--------|
| TC1 | Dell laptop | Run on Dell Latitude | serial=7-char service tag, brand="Dell" | ☐ |
| TC2 | Lenovo laptop | Run on ThinkPad T14 | serial includes MTM, brand="Lenovo" | ☐ |
| TC3 | HP laptop | Run on HP EliteBook | serial=10-char, brand="HP" | ☐ |
| TC4 | Unknown/unbranded | Run on custom PC or VM | brand="Unknown", model from dmidecode or empty | ☐ |
| TC5 | dmidecode not available | Run in minimal container without dmidecode | Returns empty dict, logs warning | ☐ |

### Feature: storage.py

| # | Test Case | Steps | Expected | Status |
|---|-----------|-------|----------|--------|
| TC1 | SATA SSD | Run with SATA SSD | model, capacity, health, power_on_hours all populated | ☐ |
| TC2 | NVMe SSD | Run with NVMe drive | Same fields, sourced from `nvme smart-log` | ☐ |
| TC3 | HDD | Run with spinning disk | Returns HDD model, capacity, health (wear-leveling may show as N/A) | ☐ |
| TC4 | No storage detected | Run in RAM-only environment | Returns empty dict, logs warning | ☐ |

### Feature: battery.py

| # | Test Case | Steps | Expected | Status |
|---|-----------|-------|----------|--------|
| TC1 | Battery present | Run on laptop with battery | health_pct, cycle_count, manufacturer, serial populated | ☐ |
| TC2 | Battery removed | Run with battery physically removed | health_pct=null, cycle_count=null, note in log | ☐ |
| TC3 | Desktop (no battery) | Run on desktop PC | Returns empty dict, logs "No battery detected" | ☐ |

### Feature: network.py

| # | Test Case | Steps | Expected | Status |
|---|-----------|-------|----------|--------|
| TC1 | WiFi + BT + LAN | Run on standard laptop | wifi_card, bluetooth, mac_address, lan_adapter populated | ☐ |
| TC2 | No WiFi (desktop) | Run on desktop with only ethernet | wifi_card=null, lan_adapter set | ☐ |
| TC3 | No network at all | Run in isolated environment | All null but no crash | ☐ |

### Feature: camera.py

| # | Test Case | Steps | Expected | Status |
|---|-----------|-------|----------|--------|
| TC1 | Camera present | Run on laptop with webcam | exists=true, device_path="/dev/video0" | ☐ |
| TC2 | Camera disabled in BIOS | Run with BIOS camera disabled | exists=false, but check /dev/video* first | ☐ |
| TC3 | No camera | Run on desktop without camera | exists=false | ☐ |

### Feature: uploader.py

| # | Test Case | Steps | Expected | Status |
|---|-----------|-------|----------|--------|
| TC1 | Valid endpoint + API key | POST valid JSON | HTTP 200, returns laptopId | ☐ |
| TC2 | Wrong API key | POST with bad key | HTTP 401, error message | ☐ |
| TC3 | Endpoint unreachable | POST with wrong URL | Retry 3x, then log failure, continue | ☐ |
| TC4 | Network down | POST without internet | Retry 3x, log "Upload failed — no network" | ☐ |

### Feature: Full Boot Flow (E2E)

| # | Test Case | Steps | Expected | Status |
|---|-----------|-------|----------|--------|
| TC1 | Boot → collect → upload → poweroff | Boot USB on real laptop | Logo → terminal → "Connecting WiFi" → "Collecting" → "Uploading" → "Laptop ID: xyz" → poweroff in 10s | ☐ |
| TC2 | Boot with no WiFi config | Boot without config.yaml | "No WiFi configured" → collect → save locally? → "Upload failed — no network" → poweroff | ☐ |
| TC3 | Boot on VM (VirtualBox) | Boot VMDK | All collectors return gracefully, upload to test endpoint | ☐ |
| TC4 | Boot on Surface | Boot on Surface Laptop | identity returns serial as N/A, other collectors work | ☐ |

## Acceptance Criteria Checklist

| # | Category | Check | How to verify |
|---|----------|-------|---------------|
| 1 | ✅ Happy path | Full boot → collect → upload → poweroff | Physical USB test on 3 different brands |
| 2 | ❌ Error case | Missing hardware, bad config, no network | Graceful logging, no crash, continues to poweroff |
| 3 | ⚠️ Edge case | Unusual HW configs (USB-only boot, VM, stripped system) | Returns graceful N/A values |
| 4 | 🚫 Missing tools | dmidecode not installed | Falls back to sysfs, logs fallback used |
