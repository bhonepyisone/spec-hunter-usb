# Spec Hunter USB — Project Context

## Overview

A headless Alpine Linux Live USB that boots any laptop, collects hardware info (CPU, RAM, storage, battery, display, network, camera), and uploads JSON to Electronic ERP's Firebase Function (`uploadLaptop`). No GUI. Plug → boot → collect → upload.

**For:** JM505 shop (single operator, internal tool)
**Target users:** Bhone (shop owner) processing 20+ laptops/day

## Key Constraints

- No GUI, no persistent storage on the USB, no encryption on the payload
- API key lives in `config.yaml` (updatable per session), sent via `x-api-key` header
- Collectors shell out to: dmidecode, lscpu, smartctl, nvme, upower, edid-decode, lshw, v4l2-ctl
- Every collector has a fallback chain (primary tool → sysfs → graceful N/A)
- Upload is HTTP POST to the configured endpoint, retry + backoff, save to `/tmp/last_upload.json` on failure
- **Corrected architecture: no separate web PWA. The UI is Electronic ERP.** USB uploads directly to Electronic ERP's Firebase Function → `products` collection → `variants[].individualItems[]`

## Stack

| Layer | Technology |
|-------|-----------|
| Base OS | Alpine Linux (headless) |
| Runtime | Python 3.11+ |
| Hardware collection | subprocess calls to system tools |
| Upload | `requests` (HTTP POST, x-api-key) |
| Config | `config.yaml` |
| ISO Builder | `build-iso.sh` |

## External Dependencies

- Electronic ERP `functions/` — provides the `uploadLaptop` endpoint (to build)
- No external APIs needed beyond the endpoint