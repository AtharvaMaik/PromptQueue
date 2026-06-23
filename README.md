# Promptqueue

Dependency-free prompt scheduling for AI tools.

Promptqueue is for the annoying moment when an AI app says "rate limit resets later" or you are about to sleep but want a prompt sent at a specific time. Queue the prompt, keep the runner alive, and Promptqueue sends it later by copying/pasting into the target app or by launching a CLI command.

It is one Python file and uses only the standard library.

## Quick Example

Queue a Claude prompt for 11:30 PM and send it automatically:

```powershell
python promptqueue.py add 23:30 claude write a first draft of the launch email
python promptqueue.py run
```

Queue a Codex CLI prompt instead:

```powershell
python promptqueue.py add 23:30 codex-exec add tests for the queue runner
python promptqueue.py run
```

View queued prompts:

```powershell
python promptqueue.py list --full
python promptqueue.py show JOB_ID
```

## How It Works

Promptqueue stores jobs in:

```text
%USERPROFILE%\.promptqueue.json
```

Override that path with:

```powershell
$env:PROMPTQUEUE_FILE="C:\path\queue.json"
```

When the machine wakes up after the scheduled time, `run` catches overdue jobs and sends them.

## Targets

```text
antigravity  launch=agy                         window=Antigravity  click=bottom
chatgpt      launch=https://chatgpt.com/         window=ChatGPT      click=bottom
claude       launch=https://claude.ai/new        window=Claude       click=bottom
claude-code  launch=claude -p {prompt}
codex        launch=codex app                    window=Codex        click=bottom
codex-exec   launch=codex exec {prompt}
copilot      launch=https://copilot.microsoft.com/ window=Copilot    click=bottom
copy         launch=copy
cursor       launch=cursor                       window=Cursor       click=bottom
gemini       launch=https://gemini.google.com/app window=Gemini      click=bottom
```

UI targets open/focus the app, click near the bottom, paste, then press Enter by default.

CLI targets run the command directly with the prompt as one argument.

## Retry And History

Every job stores attempts and history in the queue file. Failures stay visible in `list` and `show`.

```powershell
python promptqueue.py add --max-attempts 8 --retry-base 60 23:30 claude retry this more patiently
python promptqueue.py list --all
python promptqueue.py show JOB_ID
```

Backoff is exponential and capped at one hour.

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

### `list`

Show queued jobs.

```powershell
python promptqueue.py list
python promptqueue.py list --all
python promptqueue.py list --full
```

Options:

```text
--all      Include sent jobs.
--full     Print full prompt text.
```

### `show`

Show one job as JSON.

```powershell
python promptqueue.py show JOB_ID
```

### `remove`

Delete a job.

```powershell
python promptqueue.py remove JOB_ID
```

### `windows`

List visible Windows window titles. Use this to find the right `--window` value.

```powershell
python promptqueue.py windows
```

### `targets`

List built-in target aliases.

```powershell
python promptqueue.py targets
```

### `run`

Run the legacy queue worker. This is best for CLI targets and window-paste targets.

```powershell
python promptqueue.py run
python promptqueue.py run --once
python promptqueue.py run --poll 5
```

Options:

```text
--once          Check once and exit.
--poll SECONDS  Sleep between checks. Default: 15.
```

### `selftest`

Run the built-in smoke test.

```powershell
python promptqueue.py selftest
```

## Notes

Promptqueue does not use private app APIs. For GUI apps, it focuses a window, clicks the composer area, pastes, and presses Enter unless `--no-submit` is set. If one app misses the composer, adjust `--window`, `--click`, `--delay`, or `--pre-keys`.
