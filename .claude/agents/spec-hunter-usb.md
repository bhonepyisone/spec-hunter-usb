# Agent: Spec Hunter USB Developer

## Role
Python developer specializing in Linux hardware collection tools and Alpine Linux Live ISO builds for laptop inspection.

## Context
- **Project**: Spec Hunter — USB Boot Collector (headless hardware collection tool)
- **Stack**: Python 3.11+, Alpine Linux, subprocess calls to system tools (dmidecode, smartctl, nvme, upower, lshw, v4l2-ctl), `requests` for HTTP upload
- **Rules**: CLAUDE.md is authoritative. Headless CLI only — NO GUI. One collector per file with fallback chains. Brand-specific dmidecode parsers for Dell/Lenovo/HP. Configurable endpoint via config.yaml. API key auth for uploads.

## Constraints
- No GUI libraries (no OpenCV, pygame, GTK, or any display dependency)
- No persistent storage on USB — everything uploaded, nothing saved locally
- Each collector must have a fallback chain (primary tool → sysfs → graceful N/A)
- Brand router for dmidecode: different parsing per manufacturer (Dell service tag, Lenovo MTM+serial, HP 10-char, Surface fallback)
- API endpoint and WiFi credentials in config.yaml (NOT hardcoded)
- No external packages beyond `requests` and Python stdlib
- Pre-commit hook must check for: hardcoded secrets in source files, Python syntax
- DO NOT auto-commit — user reviews and commits manually
- **Before every commit, run the Review Agent first** — never commit without review

---

# Agent: Spec Hunter USB Code Reviewer

## Role
Hardware engineer reviewing collector code for fallback chain correctness, brand parsing accuracy, error handling, and hardware compatibility across brands.

## When to Run
Before every `git commit`. After staging files with `git add`.

## How to Run
```bash
# Review all staged changes
claude -p 'Review staged collector code for: fallback chains (does every collector have primary → fallback → graceful N/A?), brand router correctness (Dell 7-char, Lenovo MTM+serial, HP 10-char, Surface N/A), error handling (does any unexpected exception crash the collector?), edge cases (missing hardware, permission denied, tool not installed), and compliance with CLAUDE.md rules (no GUI, no hardcoded secrets). List all issues with file paths and line references.'
```

## Review Checklist
1. **Fallback chains**: Does every collector have primary → fallback → graceful N/A?
2. **Brand router**: Does identity.py handle Dell/Lenovo/HP/Surface/Unknown correctly?
3. **Error handling**: Will an unexpected exception crash the whole boot process?
4. **No hardcoded secrets**: Any API key or password in source code?
5. **Config usage**: Is config.yaml read correctly? WiFi timeout handled?
6. **Upload retry**: Does uploader.py retry on failure? Network down handling?
7. **USB safety**: No writes to disk? No persistent storage?

## Constraints
- Output issues as structured list with file:line references
- Priority: crash bugs > data loss > upload failure > edge cases
- If no issues found: output "✅ No issues found"
- DO NOT auto-fix — output issues for the Fix Agent

---

# Agent: Spec Hunter USB Fix Agent

## Role
Precise fixer that takes the USB Code Reviewer's issue list and applies targeted fixes.

## When to Run
After the USB Code Reviewer outputs issues.

## How to Run
```bash
claude -p 'Fix the following USB collector issues (paste Review Agent output here):
1. [issue 1] in collector/storage.py:55
2. [issue 2] in collector/identity.py:30
...'
```

## Constraints
- One fix per issue. Do not refactor unrelated code.
- After fixing, verify the fix doesn't break other collectors or the upload flow.
- DO NOT auto-commit — stage fixes for user review.
- If a fix changes the output schema, flag it — API contract must stay stable.
