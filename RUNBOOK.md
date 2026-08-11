# Spec Hunter USB — Field Runbook

Build the bootable ISO, flash it, test a laptop end-to-end.

## Prereqs

- Docker Desktop (free) — provides the `linux/amd64` env we need. The Mac
  itself can't run `build-iso.sh` (no loop-mount, wrong-arch packages).
- BalenaEtcher (free, https://etcher.balena.io) — flash ISO → USB.
- A spare **Intel/AMD x86_64** laptop to test (arm64 will not boot this ISO).

## 1. Build the ISO

```bash
cd "/Users/voznolker/BPS/Dev/2nd-hand laptops ecommerce/Spec-Hunter/spec-hunter-usb"
docker build --platform linux/amd64 -t spec-iso .
docker run --rm -v "$(pwd):/build" spec-iso v1.0
```

Output: `releases/spec-hunter-v1.0.iso`

The build unpack the Alpine ISO with xorriso, injects the collector +
deps + auto-start hook into the initramfs, and repacks a hybrid (BIOS+UEFI)
ISO. WiFi creds and API key come from this repo's `config.yaml` (gitignored).

## 2. Flash the USB

Open BalenaEtcher → Select image → pick `releases/spec-hunter-v1.0.iso` →
Select target → the USB stick (double-check you pick the stick!) → Flash.

## 3. Boot the test laptop

1. Insert the USB into the target laptop.
2. Boot; enter the boot menu (common: F12 / F11 / Esc / Del).
   If legacy/CSM boot is disabled in BIOS, enable it, or use the UEFI entry.
3. The ISO auto-starts: connect `Kodung_5G` → collect specs → serve the UI.

## 4. Run the on-machine UI

On the **tested laptop itself**, open a browser → `http://127.0.0.1:8080`:

- Confirm the auto-collected specs match this machine.
- Enter the customer name.
- Run the 6 physical tests: keyboard, display, sound, microphone,
  touchpad, ports — each Pass/Fail + a free-text failure point
  (e.g. "spacebar unresponsive", "dead pixel lower-left").
- **Submit** → row lands in `vozz-erp` Firestore → laptop powers off ~10s
  later.

To keep it running instead of powering off (debug), boot to the shell and:
```sh
export SPEC_HUNTER_NO_POWEROFF=1
```
then `python3 /opt/spec-hunter/collector/main.py`.

## 5. Verify the row landed

Firestore console → `vozz-erp` → collection `laptops` → newest doc.

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| `docker build` fails on `linux/amd64` | Docker Desktop not on Linux containers — enable its Settings → BuildKit / platform support. |
| Laptop won't boot the USB | Wrong boot key or secure boot / CSM off. Try the other boot-menu key; disable Secure Boot; enable Legacy. |
| No WiFi / curl to 8.8.8.8 fails | `Kodung_5G` reachable? `config.yaml` has the right ssid/password? Interface may not be `wlan0` — Alpine runs interface discovery; check `ip a`. |
| Upload error in UI | API key mismatch or endpoint wrong. `config.yaml` endpoint + key must match the deployed function. Writes are `400` (missing identity), `401` (bad key), `503` (Firestore denied). |
| Specs show N/A / empty | Collector degraded (missing dmidecode/smartctl/edid-decode on that build). Those tools are optional fallbacks; collect what's present. |
| Powering off before you're done | It's supposed to. Use `SPEC_HUNTER_NO_POWEROFF=1`. |

## What the USB does, end to end

1. Boot Alpine (read-only initramfs).
2. `collector.start`: wait for `config.yaml`, WPA3-connect `Kodung_5G`, run
   `main.py`.
3. `main.py`: wait for network → run 8 collectors → serve the local UI →
   block on submit/abort → POST `{...specs, customer_name, test_results}`
   to the function (with retry) → write `/tmp/last_upload.json` on failure →
   poweroff.

API key is baked into the ISO. Treat the ISO as the secret — don't share it
beyond the shop. The repo `config.yaml` stays gitignored so creds never
commit.