# PromptQueue Agent Instructions

Use this repo to schedule prompts for later delivery through `promptqueue.py`.

## When To Use

When the user says their AI limits reset at a time, asks to send/paste a prompt later, or asks to queue a prompt for an AI tool, schedule it here.

Example user request:

```text
my limits reset at 7:30 pm, schedule prompt "ABC"
```

## Schedule

Run commands from the repo root.

Prefer `--stdin` so quoted and multiline prompts survive shell parsing:

```powershell
@'
ABC
'@ | python promptqueue.py add --stdin 19:30 TARGET
```

Use local machine time. Convert natural times like `7:30 pm` to `19:30`. `HH:MM` schedules today if still future, otherwise tomorrow. Use a dated time when the user gives a date:

```powershell
@'
ABC
'@ | python promptqueue.py add --stdin "2026-06-24 19:30" TARGET
```

After queueing, make sure a runner will be alive when the job is due:

```powershell
python promptqueue.py run
```

Use `run --once` only for already-due jobs or smoke tests.

## Targets

Infer the target from the user's wording. If no target is named, use the AI tool the user is currently talking to when it has a matching target.

```text
claude       Claude web UI
claude-code  Claude CLI
codex        Codex desktop UI
codex-exec   Codex CLI
cursor       Cursor UI
antigravity  Google Antigravity UI
chatgpt      ChatGPT web UI
gemini       Gemini web UI
copilot      Copilot web UI
copy         clipboard only; use only if asked
```

Run this if target availability is unclear:

```powershell
python promptqueue.py targets
```

Use `--no-submit` only when the user asks to paste but not send.

After scheduling, tell the user the printed job id, target, and scheduled time.
