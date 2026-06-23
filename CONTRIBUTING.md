# Contributing

Thanks for helping make PromptQueue more useful.

## Setup

```powershell
git clone https://github.com/AtharvaMaik/PromptQueue.git
cd PromptQueue
python promptqueue.py selftest
```

No install step is needed. The project is one Python file and uses only the standard library.

## Before Opening A PR

Run:

```powershell
python -m py_compile promptqueue.py
python promptqueue.py selftest
python -m build
python -m twine check dist/*
```

If you change scheduling, retries, command parsing, target detection, clipboard behavior, or GUI paste behavior, add the smallest selftest assertion that would fail without your fix.

## Releasing

1. Update `version` in `pyproject.toml`.
2. Run `python -m build` and `python -m twine check dist/*`.
3. Push to `main` and wait for CI.
4. Upload with `python -m twine upload dist/*`.
5. Publish a GitHub release like `v0.1.0`.

The `Publish` workflow can upload to PyPI manually after PyPI Trusted Publishing is configured for this repo.

## Good First Contributions

- Add or improve a target alias.
- Improve README examples for a real workflow.
- Make paste/click behavior more reliable for a specific app.
- Improve Windows, macOS, or Linux behavior without adding dependencies.
- Turn a bug report into one failing selftest, then fix it.

## Project Rules

- Keep it dependency-free unless there is a very strong reason.
- Prefer one boring fix over a new framework, daemon, service, or config layer.
- Do not add private API integrations for AI tools.
- Keep PRs focused. One behavior change per PR is easiest to review.
- Do not include secrets, tokens, private prompts, or personal queue files in issues or PRs.

## Reporting Bugs

Include:

- OS and Python version.
- Target used, such as `claude`, `codex`, or `cursor`.
- Command you ran.
- Output from `python promptqueue.py targets` when target launch is involved.
- Whether the job was queued, retried, failed, or marked sent.

For GUI paste bugs, also include the relevant window title from:

```powershell
python promptqueue.py windows
```

## License

By contributing, you agree that your contribution will be licensed under the MIT license.
