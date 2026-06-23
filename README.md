# Promptqueue

Schedule AI prompts for the moment your limits reset.

Promptqueue is a tiny, dependency-free prompt scheduler for Claude, Codex, ChatGPT, Gemini, Copilot, Cursor, Antigravity, and anything else you can launch from your machine.

When an AI tool says "try again at 7:30 PM", do not keep the tab open, set a reminder, or paste the same prompt later. Queue it now. Promptqueue waits, opens or focuses the target app, pastes the prompt, and submits it when the time arrives.

```powershell
python promptqueue.py add 19:30 claude finish the migration plan
python promptqueue.py run
```

One Python file. Standard library only. No accounts, no server, no private APIs.

## Why This Exists

AI rate limits waste the worst kind of time: attention.

You already know what you want to ask next. The only problem is the clock. Promptqueue turns "come back later" into a queued job you can trust.

Use it when:

- Claude, Codex, ChatGPT, Gemini, or Copilot tells you to wait for a reset
- you want a long prompt to run after you sleep
- you want a coding agent to resume work when capacity returns
- you want a dead-simple local queue instead of another SaaS dashboard

If this saves you one context switch, it has already done its job.

## 30 Second Demo

Queue a Claude prompt for 11:30 PM:

```powershell
python promptqueue.py add 23:30 claude write a first draft of the launch email
python promptqueue.py run
```

Queue a Codex CLI prompt:

```powershell
python promptqueue.py add 23:30 codex-exec add tests for the queue runner
python promptqueue.py run
```

Queue a multiline prompt safely:

```powershell
@'
Review this repo.
Find the smallest useful next improvement.
Then implement it.
'@ | python promptqueue.py add --stdin 23:30 claude
python promptqueue.py run
```

View what is waiting:

```powershell
python promptqueue.py list --full
python promptqueue.py show JOB_ID
```

## Supported Targets

```text
antigravity  Google Antigravity UI
chatgpt      ChatGPT web UI
claude       Claude web UI
claude-code  Claude CLI
codex        Codex desktop UI
codex-exec   Codex CLI
copilot      Copilot web UI
copy         clipboard only
cursor       Cursor UI
gemini       Gemini web UI
```

Run this to see the built-in aliases on your machine:

```powershell
python promptqueue.py targets
```

UI targets open or focus the app, click near the composer, paste, then press Enter by default.

CLI targets run the command directly with the prompt as one argument.

## Agent Ready

This repo includes instruction files for common AI coding tools:

```text
AGENTS.md                         Codex and general agents
CLAUDE.md                         Claude Code
GEMINI.md                         Gemini CLI
.cursor/rules/promptqueue.mdc     Cursor
.agents/skills/promptqueue/       Antigravity-style skill
```

That means you can tell an agent:

```text
My limits reset at 7:30 pm. Schedule this prompt for Claude:
"Continue the refactor and run the tests."
```

The agent should queue it with Promptqueue instead of making you remember.

## Install

Clone the repo and run the single Python file:

```powershell
git clone https://github.com/AtharvaMaik/PromptQueue.git
cd PromptQueue
python promptqueue.py selftest
```

Promptqueue stores jobs in:

```text
%USERPROFILE%\.promptqueue.json
```

Override the queue path when you want an isolated queue:

```powershell
$env:PROMPTQUEUE_FILE="C:\path\queue.json"
```

## How It Works

1. `add` writes a job to the local queue file.
2. `run` checks for due jobs.
3. When a job is due, Promptqueue copies the prompt to the clipboard.
4. For UI targets, it opens or focuses the app, clicks the composer, pastes, and optionally submits.
5. For CLI targets, it launches the command directly.
6. Attempts, failures, retries, and history stay visible in the queue file.

If the machine wakes up after the scheduled time, `run` catches overdue jobs.

## Commands

### `add`

Queue a prompt.

```powershell
python promptqueue.py add [options] WHEN TARGET PROMPT...
```

`WHEN` can be a local time like `23:30` or an ISO-ish datetime like `2026-06-24 01:15`.

Options:

```text
--click bottom                 Click near the bottom of the focused window before paste.
--click x,y                    Click x/y pixels from the target window top-left.
--command-template TEMPLATE    Run a custom command; use {prompt}.
--delay SECONDS                Wait before paste/submit. Default: 5.
--file FILE                    Read prompt text from a UTF-8 file.
--max-attempts N               Attempts before marking failed. Default: 5.
--no-submit                    Paste only; do not press Enter.
--pre-keys KEYS                Windows SendKeys before paste, e.g. "{ESC}".
--retry-base SECONDS           Initial retry delay. Default: 30.
--stdin                        Read prompt text from stdin.
--window TITLE                 Focus a window whose title contains TITLE.
```

Examples:

```powershell
python promptqueue.py add 23:30 claude summarize this paper
python promptqueue.py add --window Codex 23:30 copy this lands in Codex
python promptqueue.py add --no-submit 23:30 claude paste this but do not send it
python promptqueue.py add --file prompt.txt 23:30 claude
"prompt from stdin" | python promptqueue.py add --stdin 23:30 copy
python promptqueue.py add --command-template "claude -p {prompt}" 23:30 command review this repo
```

### `run`

Start the queue worker:

```powershell
python promptqueue.py run
```

Check once and exit:

```powershell
python promptqueue.py run --once
```

Poll faster or slower:

```powershell
python promptqueue.py run --poll 5
```

The runner must be alive when jobs are due.

### `list`

Show queued jobs:

```powershell
python promptqueue.py list
python promptqueue.py list --all
python promptqueue.py list --full
```

### `show`

Show one job as JSON:

```powershell
python promptqueue.py show JOB_ID
```

### `remove`

Delete one job:

```powershell
python promptqueue.py remove JOB_ID
```

### `windows`

List visible Windows window titles. Use this to find the right `--window` value.

```powershell
python promptqueue.py windows
```

### `targets`

List built-in target aliases:

```powershell
python promptqueue.py targets
```

### `selftest`

Run the built-in smoke test:

```powershell
python promptqueue.py selftest
```

## Retries And History

Every job stores attempts and history. Failures stay visible in `list` and `show`.

```powershell
python promptqueue.py add --max-attempts 8 --retry-base 60 23:30 claude retry this more patiently
python promptqueue.py list --all
python promptqueue.py show JOB_ID
```

Backoff is exponential and capped at one hour.

## Notes

Promptqueue intentionally does the boring thing: it uses local files, the clipboard, app launching, and keyboard paste. That keeps it portable and inspectable.

For GUI apps, it does not use private app APIs. If one app misses the composer, adjust `--window`, `--click`, `--delay`, or `--pre-keys`.

Star the repo if it saves you from waiting around for an AI limit reset. That is the whole point.
