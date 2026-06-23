# Security

PromptQueue is local automation. It can copy text to your clipboard, launch apps, focus windows, paste, and press Enter.

## Safe Use

- Do not schedule secrets, passwords, API keys, recovery codes, payment details, or private personal data.
- Use `--no-submit` when you want to inspect a prompt before it is sent.
- Use `copy` when you only want the prompt on the clipboard.
- Keep the queue file private; prompts are stored in plain JSON.

The default queue file is:

```text
%USERPROFILE%\.promptqueue.json
```

## Reporting A Vulnerability

Do not put secrets or working exploit details in a public issue.

If GitHub private vulnerability reporting is enabled for the repo, use it. Otherwise, open a minimal public issue that says a security report is available and avoid sensitive details until the maintainer gives you a private contact path.
