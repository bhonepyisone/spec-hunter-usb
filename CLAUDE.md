# Spec Hunter — USB Boot Collector

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Base OS | Alpine Linux (headless, no GUI) |
| Runtime | Python 3.11+ |
| Hardware Collection | subprocess calls to system tools |
| Upload | `requests` library — HTTP POST to configurable endpoint |
| ISO Builder | Alpine `mkimage` or custom script |

## Project Structure

```
spec-hunter-usb/
├── SPEC.md                     ← SDD 6-part spec
├── CLAUDE.md                   ← This file
├── TEST.md                     ← Test plan
├── .mcp.json                   ← MCP tools
├── .gitignore
├── .env.example
├── .githooks/
│   └── pre-commit
├── .claude/
│   ├── skills/
│   │   └── spec-hunter-usb/
│   │       └── SKILL.md
│   └── agents/
│       └── spec-hunter-usb.md
├── LLM_Wiki/
│   ├── README.md
│   └── architecture.md
├── collector/
│   ├── main.py                 ← Entry point
│   ├── identity.py             ← dmidecode + brand router
│   ├── cpu.py                  ← lscpu + /proc/cpuinfo
│   ├── ram.py                  ← dmidecode --type 17
│   ├── storage.py              ← smartctl + nvme fallback
│   ├── battery.py              ← upower + sysfs fallback
│   ├── display.py              ← edid-decode
│   ├── network.py              ← lshw + hciconfig + ip
│   ├── camera.py               ← v4l2-ctl detection
│   └── uploader.py             ← POST to API
├── tests/
│   ├── test_identity.py
│   ├── test_storage.py
│   └── test_battery.py
├── config.yaml                 ← Endpoint URL, API key, WiFi
├── requirements.txt
├── build-iso.sh                ← ISO builder
└── README.md
```

## Conventions

### Code Style
- Python 3.11+ type hints on all functions
- One collector per file, one class or function per collector
- Each collector returns a dict matching the Firestore laptop schema sub-object
- Fallback chains: try primary tool → try alternative → return graceful defaults
- Log to stdout (visible on terminal during boot)
- No external Python packages beyond `requests` and stdlib

### Collector Pattern
```python
def collect() -> dict:
    """Collect [component] information. Returns dict or empty dict on failure."""
    result = {}
    try:
        # Primary method
        result = primary_method()
    except Exception:
        try:
            # Fallback
            result = fallback_method()
        except Exception:
            log.warning("Could not collect [component]")
    return result
```

### Brand Router Pattern
```python
BRAND_PARSERS = {
    "dell": parse_dell_serial,
    "lenovo": parse_lenovo_serial,
    "hp": parse_hp_serial,
    "microsoft": parse_surface_fallback,
}
```

### Commits
- One commit per collector module
- User reviews and commits manually (DO NOT auto-commit)
- Push after each commit

### Code Review Workflow (MANDATORY)
- **Must run Review Agent before every commit** — never commit without review
- Workflow:
  1. `git add <files>`
  2. Run Review Agent: load `.claude/agents/spec-hunter-usb.md` → follow USB Code Reviewer instructions
  3. If issues found → run USB Fix Agent from the same file
  4. `git diff` → verify fixes
  5. `git commit`
- Review checks: fallback chains (primary → fallback → graceful N/A), brand router accuracy (Dell/Lenovo/HP/Surface/Unknown), error handling (no crash on missing hardware/tools), no hardcoded secrets, upload retry logic, config.yaml loading

## DO NOT
- Add any GUI or graphical dependencies
- Use OpenCV, pygame, GTK, or any display library
- Store data persistently on the USB
- Hardcode API keys or WiFi passwords in source code
- Use sudo in collector scripts — run as root (boot environment)
- Commit .env or config.yaml with real credentials

## Testing Requirements
- Test each collector on YOUR laptop: `python collector/identity.py`
- Test uploader: `python collector/uploader.py` (with valid endpoint)
- Smoke test ISO: write to USB, boot on a spare laptop
- Error handling: run collectors on a VM with missing hardware (no battery, no display)
