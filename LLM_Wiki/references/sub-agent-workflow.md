# Sub-Agent Workflow — Spec Hunter USB

## Primary Pattern: Review → Fix → Commit

This is the **mandatory flow before every commit**. Do not skip.

```
┌─────────────────────────────────────────────────────────────────┐
│  1. git add <files>                                              │
│                                                                  │
│  2. LOAD: .claude/agents/spec-hunter-usb.md                     │
│     RUN: USB Code Reviewer persona                               │
│     PROMPT: 'Review staged collector code for fallback chains,   │
│              brand router accuracy, error handling...'           │
│          │                                                       │
│          ▼                                                       │
│     OUTPUT: Structured issue list (or "✅ No issues found")      │
│          │                                                       │
│          ▼                                                       │
│  3. IF ISSUES: RUN USB Fix Agent persona                         │
│     PROMPT: 'Fix the following issues: [paste list]'             │
│          │                                                       │
│          ▼                                                       │
│  4. git diff → verify fixes                                      │
│  5. git add <fixed files>                                        │
│  6. git commit                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Review Agent Prompt (Full Template)

```bash
claude -p 'Review staged collector code for:
1. Fallback chains — does EVERY collector have primary → fallback → graceful N/A?
2. Brand router — identity.py handles Dell(7-char)/Lenovo(MTM+serial)/HP(10-char)/Surface(N/A)?
3. Error handling — will a missing tool, permission error, or unexpected exception crash the boot?
4. Hardcoded secrets — any API key, password, or WiFi credential in source code?
5. Config loading — config.yaml read correctly? WiFi timeout handled?
6. Upload retry — does uploader.py retry 3x on failure? Network down handled gracefully?
7. USB safety — no writes to disk? No persistent storage?
8. Parsing — does _parse() handle edge cases (empty output, unexpected format)?

List every issue with file path and line reference. Priority: crash > data loss > upload failure > edge case.
If no issues: output "✅ No issues found"'
```

## Cost Strategy

| Layer | Model | Work | Cost |
|-------|-------|------|------|
| Review | gpt-4o-mini / haiku | 80%: collector review, fallback checks | Cheap |
| Fix | sonnet / claude-sonnet-4 | 20%: brand router bugs, edge cases | More |

## Pre-Commit Verification — USB

1. Static security scan — no hardcoded secrets, no config.yaml leaks
2. Python syntax check on all staged .py files
3. Self-review: fallback chains, brand router, error handling
4. Independent reviewer: `delegate_task` with diff for fresh-context review
5. Auto-fix: max 2 cycles, NEVER same agent as implementer
