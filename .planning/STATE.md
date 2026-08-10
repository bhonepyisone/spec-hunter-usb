# Spec Hunter USB — Project State

## Current Phase
Phase 1 — collectors built, not yet verified on hardware. No `.planning/` existed before this bootstrap; corrected architecture (no PWA) is now reflected here.

## What's Built
- 9 collectors with fallback chains (`collector/`) + 9 pytest files (`tests/`)
- `uploader.py` — retry + exponential backoff, `/tmp/last_upload.json` save on fail
- `build-iso.sh`, `config.yaml`, `requirements.txt`
- SPEC.md, CLAUDE.md, TEST.md, LLM_Wiki, `.mcp.json`, pre-commit hook, `.env.example`

## What's Next
1. Run `pytest tests/` → green
2. Real-hardware verification of each collector
3. ERP `uploadLaptop` Firebase Function (Phase 2.2)
4. E2E upload → row in Electronic ERP inventory
5. `build-iso.sh` → bootable ISO → boot smoke test

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-06-24 | USB dedicated repo | Independent dev/maintenance |
| 2026-06-24 | Headless, no GUI | Interactive tests stay in web app |
| 2026-06-24 | No encryption on USB | API key per-session in config.yaml |
| 2026-08-10 | **Corrected arch: no separate PWA** | USB uploads directly to Electronic ERP's Firebase Function; ERP is the UI |