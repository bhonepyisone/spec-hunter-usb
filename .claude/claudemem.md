# Claude Mem — Spec Hunter USB

## Durable Facts

- Headless Alpine Linux — NO GUI, NO display dependencies
- Python 3.11+, stdlib + requests only (no OpenCV, pygame, etc.)
- Each collector has fallback chain: primary → sysfs → graceful N/A
- Brand router: Dell(7-char service tag), Lenovo(MTM+serial), HP(10-char), Surface(N/A)
- API endpoint + WiFi credentials in config.yaml (never hardcoded)
- Auto-poweroff 10s after upload
- Upload via POST to Firebase Function with x-api-key header
- ~500MB ISO built with build-iso.sh

## User Preferences

- One collector per file
- Type hints on all functions
- Fallback before crash — graceful N/A over errors
- DO NOT auto-commit — user reviews and commits manually

## Project State

- Phase: Planning — all GSD artifacts created
- Next: Build collector modules, test on real hardware
