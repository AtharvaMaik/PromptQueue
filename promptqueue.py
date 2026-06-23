from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import shlex
import subprocess
import sys
import tempfile
import time
import uuid
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path


QUEUE_FILE = Path(os.getenv("PROMPTQUEUE_FILE", Path.home() / ".promptqueue.json"))

TARGETS = {
    "copy": "copy",
    "claude": "https://claude.ai/new",
    "claude-code": "claude",
    "chatgpt": "https://chatgpt.com/",
    "copilot": "https://copilot.microsoft.com/",
    "gemini": "https://gemini.google.com/app",
    "cursor": "cursor",
    "antigravity": "agy",
    "codex": "app:OpenAI.Codex_2p2nqsd0c76g0!App",
}

WINDOW_HINTS = {
    "claude": "Claude",
    "chatgpt": "ChatGPT",
    "copilot": "Copilot",
    "gemini": "Gemini",
    "cursor": "Cursor",
    "antigravity": "Antigravity",
    "codex": "Codex",
}

CLICK_HINTS = {target: "bottom" for target in WINDOW_HINTS}

COMMAND_TARGETS = {
    "claude-code": "claude -p {prompt}",
    "codex-exec": "codex exec {prompt}",
}

MAX_HISTORY = 25


def echo(text: str) -> None:
    encoding = sys.stdout.encoding or "utf-8"
    print(text.encode(encoding, errors="replace").decode(encoding))


def parse_when(value: str, now: datetime | None = None) -> datetime:
    now = now or datetime.now()
    value = value.strip()

    if re.fullmatch(r"\d{1,2}:\d{2}", value):
        hour, minute = map(int, value.split(":"))
        due = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return due if due > now else due + timedelta(days=1)

    return datetime.fromisoformat(value.replace(" ", "T", 1))


def load_queue(path: Path = QUEUE_FILE) -> dict:
    if not path.exists():
        return {"jobs": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save_queue(queue: dict, path: Path = QUEUE_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(queue, indent=2), encoding="utf-8")


def iso_now(now: datetime | None = None) -> str:
    return (now or datetime.now()).isoformat(timespec="seconds")


def parse_iso(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def append_history(job: dict, event: str, now: datetime | None = None, **fields) -> None:
    entry = {"at": iso_now(now), "event": event, **fields}
    job["history"] = [*job.get("history", [])[-(MAX_HISTORY - 1) :], entry]


def job_ready(job: dict, now: datetime | None = None) -> bool:
    now = now or datetime.now()
    if job.get("sent_at") or job.get("failed_at"):
        return False
    if parse_when(job["at"], now) > now:
        return False
    if (parse_iso(job.get("next_attempt_at")) or now) > now:
        return False
    if (parse_iso(job.get("leased_until")) or now) > now:
        return False
    return True


def mark_sent(job: dict, now: datetime | None = None) -> None:
    now = now or datetime.now()
    job["sent_at"] = iso_now(now)
    job.pop("last_error", None)
    job.pop("next_attempt_at", None)
    job.pop("leased_until", None)
    append_history(job, "sent", now, attempt=job.get("attempts", 0))


def mark_failed(job: dict, error: str, now: datetime | None = None) -> None:
    now = now or datetime.now()
    attempts = int(job.get("attempts", 0)) + 1
    max_attempts = int(job.get("max_attempts", 5))
    retry_base = float(job.get("retry_base", 30))
    retry_delay = min(retry_base * (2 ** (attempts - 1)), 3600)

    job["attempts"] = attempts
    job["last_error"] = error
    job.pop("leased_until", None)
    append_history(job, "failed", now, attempt=attempts, error=error)

    if attempts >= max_attempts:
        job["failed_at"] = iso_now(now)
        job.pop("next_attempt_at", None)
        return

    job["next_attempt_at"] = iso_now(now + timedelta(seconds=retry_delay))


def job_status(job: dict) -> str:
    if job.get("sent_at"):
        return "sent"
    if job.get("failed_at"):
        return "failed"
    if job.get("next_attempt_at"):
        return "retry"
    return "queued"


def tkinter_copy_clipboard(text: str) -> None:
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    root.clipboard_clear()
    root.clipboard_append(text)
    root.update()
    root.destroy()


def copy_clipboard(text: str, runner=subprocess.run, fallback=tkinter_copy_clipboard) -> None:
    if platform.system() == "Windows":
        try:
            runner(["clip"], input=text, text=True, check=True, capture_output=True)
            return
        except subprocess.CalledProcessError as exc:
            error = (exc.stderr or exc.stdout or str(exc)).strip()
            raise RuntimeError(f"clipboard unavailable: {error}") from exc
        except OSError as exc:
            raise RuntimeError(f"clipboard unavailable: {exc}") from exc

    fallback(text)


def split_command(command: str) -> list[str]:
    return shlex.split(command, posix=platform.system() != "Windows")


def protected_windowsapps_path(path: str, system=platform.system) -> bool:
    normalized = path.replace("/", "\\").lower()
    return system() == "Windows" and "\\program files\\windowsapps\\" in normalized


def command_issue(args: list[str], which=shutil.which) -> str | None:
    if not args:
        return "command required"
    path = which(args[0])
    if not path:
        return f"command not found: {args[0]}"
    if protected_windowsapps_path(path):
        return f"command not runnable: {args[0]} (protected WindowsApps package)"
    return None


def launch_status(launch: str, which=shutil.which) -> str:
    if launch in {"copy", "clipboard", "none"}:
        return "internal"
    if launch.startswith(("http://", "https://")):
        return "url"
    if launch.startswith("app:"):
        return "app"
    issue = command_issue(split_command(launch.replace("{prompt}", "prompt")), which)
    if issue and "not runnable" in issue:
        return "blocked"
    return "missing" if issue else "found"


def raise_command_error(action: str, command: str, exc: BaseException) -> None:
    raise RuntimeError(f"{action} not runnable: {command} ({exc})") from exc


def launch_target(target: str) -> None:
    target = TARGETS.get(target, target)
    if target in {"copy", "clipboard", "none"}:
        return
    if target.startswith(("http://", "https://")):
        webbrowser.open(target)
        return
    if target.startswith("app:"):
        if platform.system() != "Windows":
            raise RuntimeError("Windows app launch is Windows-only")
        subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{target[4:]}"])
        return

    issue = command_issue(split_command(target))
    if issue:
        raise RuntimeError(issue)
    try:
        process = subprocess.Popen(target, shell=True, stderr=subprocess.PIPE, text=True)
    except PermissionError as exc:
        raise_command_error("launcher", split_command(target)[0], exc)
    time.sleep(0.25)
    if process.poll() not in (None, 0):
        error = process.stderr.read().strip() if process.stderr else ""
        raise RuntimeError(f"launcher failed: {target}{': ' + error if error else ''}")


def command_args(template: str, prompt: str) -> list[str]:
    marker = "__PROMPTQUEUE_PROMPT__"
    if "{prompt}" not in template:
        template = f"{template} {{prompt}}"

    parts = shlex.split(
        template.replace("{prompt}", marker),
        posix=platform.system() != "Windows",
    )

    def clean(part: str) -> str:
        if len(part) >= 2 and part[0] == part[-1] and part[0] in {"'", '"'}:
            return part[1:-1]
        return part

    return [prompt if clean(part) == marker else clean(part) for part in parts]


def run_command_template(template: str, prompt: str, runner=subprocess.run, which=shutil.which) -> None:
    args = command_args(template, prompt)
    issue = command_issue(args, which)
    if issue:
        raise RuntimeError(issue)
    try:
        runner(args, check=True)
    except PermissionError as exc:
        raise_command_error("command", args[0], exc)


def visible_windows() -> list[tuple[int, int, str]]:
    if platform.system() != "Windows":
        return []

    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    rows = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True

        length = user32.GetWindowTextLengthW(hwnd)
        if not length:
            return True

        title = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title, length + 1)
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        rows.append((int(hwnd), int(pid.value), title.value))
        return True

    user32.EnumWindows(callback_type(callback), 0)
    return rows


def focus_window(query: str) -> tuple[int, str]:
    import ctypes
    from ctypes import wintypes

    matches = [row for row in visible_windows() if query.lower() in row[2].lower()]
    if not matches:
        raise RuntimeError(f"window not found: {query}")

    hwnd = wintypes.HWND(matches[0][0])
    user32 = ctypes.windll.user32

    # ponytail: title targeting is the cheap reliable-enough path; app APIs if titles collide.
    user32.ShowWindow(hwnd, 9)
    user32.keybd_event(0x12, 0, 0, 0)
    user32.keybd_event(0x12, 0, 2, 0)
    if not user32.SetForegroundWindow(hwnd):
        raise RuntimeError(f"could not focus window: {matches[0][2]}")
    return matches[0][0], matches[0][2]


def click_in_window(hwnd: int, click: str) -> None:
    import ctypes
    from ctypes import wintypes

    rect = wintypes.RECT()
    user32 = ctypes.windll.user32
    if not user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect)):
        raise RuntimeError("could not read window bounds")

    width = rect.right - rect.left
    height = rect.bottom - rect.top
    if click == "bottom":
        x = rect.left + width // 2
        y = rect.top + int(height * 0.88)
    else:
        raw_x, raw_y = click.split(",", 1)
        x = rect.left + int(raw_x)
        y = rect.top + int(raw_y)

    user32.SetCursorPos(x, y)
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    user32.mouse_event(0x0004, 0, 0, 0, 0)
    time.sleep(0.15)


def send_keys(keys: str) -> None:
    if platform.system() != "Windows":
        raise RuntimeError("window paste/submit is Windows-only")

    script = f"$w=New-Object -ComObject WScript.Shell; $w.SendKeys({json.dumps(keys)});"
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        check=True,
    )


def paste_into_active_window(
    submit: bool,
    window: str | None = None,
    click: str | None = None,
    pre_keys: str | None = None,
) -> None:
    hwnd = None
    if window:
        hwnd, _title = focus_window(window)
    if click:
        if hwnd is None:
            raise RuntimeError("--click needs --window or a target with a window hint")
        click_in_window(hwnd, click)
    if pre_keys:
        send_keys(pre_keys)

    send_keys("^v")
    if submit:
        time.sleep(0.15)
        send_keys("{ENTER}")


def send_job(job: dict) -> None:
    template = job.get("command_template") or COMMAND_TARGETS.get(job["target"])
    if template:
        run_command_template(template, job["prompt"])
        return

    copy_clipboard(job["prompt"])
    launch_target(job["target"])

    target = job["target"].lower()
    window = job.get("window") or WINDOW_HINTS.get(target)
    click = job.get("click") or CLICK_HINTS.get(target)
    if window or click or job.get("pre_keys"):
        time.sleep(float(job.get("delay", 5)))
        paste_into_active_window(
            job.get("submit", True),
            window,
            click,
            job.get("pre_keys"),
        )


def run_due(
    path: Path = QUEUE_FILE,
    now: datetime | None = None,
    send=send_job,
) -> int:
    now = now or datetime.now()
    queue = load_queue(path)
    sent = 0
    changed = False

    for job in queue["jobs"]:
        if not job_ready(job, now=now):
            continue

        try:
            send(job)
        except Exception as exc:
            mark_failed(job, str(exc), now)
            changed = True
            print(f"failed {job['id']} -> {job['target']}: {exc}")
        else:
            mark_sent(job, now)
            sent += 1
            changed = True
            print(f"sent {job['id']} -> {job['target']}")

    if changed:
        save_queue(queue, path)
    return sent


def read_prompt(args: argparse.Namespace) -> str:
    parts = []
    if args.file:
        parts.append(Path(args.file).read_text(encoding="utf-8-sig"))
    if args.stdin:
        parts.append(sys.stdin.read())
    if args.prompt:
        parts.append(" ".join(args.prompt))
    return "\n".join(part.strip("\n") for part in parts if part.strip()).strip()


def add_job(args: argparse.Namespace) -> None:
    prompt = read_prompt(args)
    if not prompt:
        raise SystemExit("prompt required")

    queue = load_queue()
    job = {
        "id": uuid.uuid4().hex[:8],
        "at": parse_when(args.when).isoformat(timespec="seconds"),
        "target": args.target,
        "prompt": prompt,
        "delay": args.delay,
        "submit": not args.no_submit,
        "attempts": 0,
        "max_attempts": args.max_attempts,
        "retry_base": args.retry_base,
        "window": args.window,
        "click": args.click,
        "pre_keys": args.pre_keys,
        "command_template": args.command_template,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    queue["jobs"].append(job)
    save_queue(queue)
    print(f"queued {job['id']} for {job['at']} -> {job['target']}")


def list_jobs(args: argparse.Namespace) -> None:
    jobs = load_queue()["jobs"]
    rows = []
    for job in sorted(jobs, key=lambda item: item["at"]):
        if job.get("sent_at") and not args.all:
            continue
        status = job_status(job)
        preview = job["prompt"].replace("\n", " ")[:70]
        attempts = f"  attempts={job.get('attempts', 0)}/{job.get('max_attempts', 5)}"
        next_try = f"  next={job['next_attempt_at']}" if job.get("next_attempt_at") else ""
        error = f"  error={job['last_error']}" if job.get("last_error") else ""
        rows.append(f"{job['id']}  {job['at']}  {status:6}  {job['target']}  {preview}{attempts}{next_try}{error}")
        if args.full:
            rows.append(job["prompt"])

    echo("\n".join(rows) if rows else "queue empty")


def show_job(args: argparse.Namespace) -> None:
    for job in load_queue()["jobs"]:
        if job["id"] == args.id:
            echo(json.dumps(job, indent=2))
            return
    raise SystemExit("not found")


def remove_job(args: argparse.Namespace) -> None:
    queue = load_queue()
    before = len(queue["jobs"])
    queue["jobs"] = [job for job in queue["jobs"] if job["id"] != args.id]
    save_queue(queue)
    print("removed" if len(queue["jobs"]) != before else "not found")


def list_windows(_args: argparse.Namespace) -> None:
    rows = [f"{hwnd}  {pid}  {title}" for hwnd, pid, title in visible_windows()]
    echo("\n".join(rows) if rows else "no windows found")


def list_targets(_args: argparse.Namespace) -> None:
    rows = []
    for name in sorted(set(TARGETS) | set(COMMAND_TARGETS)):
        launch = COMMAND_TARGETS.get(name) or TARGETS.get(name)
        window = WINDOW_HINTS.get(name, "")
        click = CLICK_HINTS.get(name, "")
        rows.append(f"{name:12} launch={launch} window={window} click={click} status={launch_status(launch)}")
    echo("\n".join(rows))


def run_loop(args: argparse.Namespace) -> None:
    print(f"promptqueue running; queue file: {QUEUE_FILE}")
    while True:
        run_due()
        if args.once:
            return
        time.sleep(args.poll)


def selftest() -> None:
    now = datetime(2026, 1, 1, 10, 0)
    assert parse_when("10:01", now) == datetime(2026, 1, 1, 10, 1)
    assert parse_when("09:59", now) == datetime(2026, 1, 2, 9, 59)
    assert parse_when("2026-01-02 03:04") == datetime(2026, 1, 2, 3, 4)
    assert command_args("tool {prompt}", "hello world") == ["tool", "hello world"]
    assert command_args("tool", "hi") == ["tool", "hi"]
    assert launch_status("copy", which=lambda _name: None) == "internal"
    assert launch_status("https://example.com/", which=lambda _name: None) == "url"
    assert launch_status("app:Example.App!App", which=lambda _name: None) == "app"
    assert launch_status("missing --flag", which=lambda _name: None) == "missing"
    assert launch_status("tool --flag", which=lambda name: f"C:/bin/{name}") == "found"
    assert command_issue(["missing"], which=lambda _name: None) == "command not found: missing"
    assert command_issue(["tool"], which=lambda name: f"C:/bin/{name}") is None
    protected_path = "C:/Program Files/WindowsApps/Vendor.App_1.0.0_x64__abc/app/resources/tool.exe"
    assert protected_windowsapps_path(protected_path, system=lambda: "Windows")
    assert command_issue(["tool"], which=lambda _name: protected_path) == (
        "command not runnable: tool (protected WindowsApps package)"
    )
    assert launch_status("tool --flag", which=lambda _name: protected_path) == "blocked"
    try:
        run_command_template(
            "tool {prompt}",
            "hi",
            runner=lambda *_args, **_kwargs: (_ for _ in ()).throw(PermissionError("locked")),
            which=lambda name: f"C:/bin/{name}",
        )
    except RuntimeError as exc:
        assert "command not runnable: tool" in str(exc)
    else:
        raise AssertionError("PermissionError should become a useful RuntimeError")
    try:
        copy_clipboard(
            "hi",
            runner=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                subprocess.CalledProcessError(1, ["clip"], stderr="denied")
            ),
            fallback=lambda _text: (_ for _ in ()).throw(AssertionError("no Windows fallback")),
        )
    except RuntimeError as exc:
        assert "clipboard unavailable" in str(exc)
    else:
        raise AssertionError("failed Windows clipboard writes should not be marked sent")

    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "queue.json"
        prompt_path = Path(temp_dir) / "prompt.txt"
        prompt_path.write_text("from file", encoding="utf-8-sig")
        prompt_args = argparse.Namespace(file=str(prompt_path), stdin=False, prompt=[])
        assert read_prompt(prompt_args) == "from file"

        save_queue(
            {"jobs": [{"id": "abc", "at": "2026-01-01T09:00:00", "target": "copy", "prompt": "hi"}]},
            path,
        )
        seen = []
        assert run_due(path, now, send=lambda job: seen.append(job["prompt"])) == 1
        assert seen == ["hi"]
        assert load_queue(path)["jobs"][0]["sent_at"] == "2026-01-01T10:00:00"

        save_queue(
            {"jobs": [{"id": "bad", "at": "2026-01-01T09:00:00", "target": "copy", "prompt": "hi"}]},
            path,
        )
        assert run_due(path, now, send=lambda _job: (_ for _ in ()).throw(RuntimeError("boom"))) == 0
        failed = load_queue(path)["jobs"][0]
        assert failed["last_error"] == "boom"
        assert "sent_at" not in failed
        assert failed["attempts"] == 1
        assert failed["next_attempt_at"]
        assert failed["history"][-1]["event"] == "failed"

    events = []
    originals = copy_clipboard, launch_target, paste_into_active_window
    try:
        globals()["copy_clipboard"] = lambda text: events.append(("copy", text))
        globals()["launch_target"] = lambda target: events.append(("launch", target))
        globals()["paste_into_active_window"] = (
            lambda submit, window=None, click=None, pre_keys=None: events.append(
                ("paste", submit, window, click, pre_keys)
            )
        )

        send_job({"target": "claude", "prompt": "hi", "delay": 0})
        assert events == [("copy", "hi"), ("launch", "claude"), ("paste", True, "Claude", "bottom", None)]

        events.clear()
        send_job({"target": "copy", "prompt": "hi", "delay": 0})
        assert events == [("copy", "hi"), ("launch", "copy")]

        events.clear()
        send_job({"target": "copy", "prompt": "hi", "delay": 0, "window": "Codex", "submit": False})
        assert events == [("copy", "hi"), ("launch", "copy"), ("paste", False, "Codex", None, None)]
    finally:
        globals()["copy_clipboard"], globals()["launch_target"], globals()["paste_into_active_window"] = originals

    print("selftest ok")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Dependency-free prompt scheduler. Run `targets` to see built-in aliases."
    )
    sub = parser.add_subparsers(required=True)

    add = sub.add_parser("add")
    add.add_argument("--click", help='Click before paste: "bottom" or "x,y" pixels from the target window top-left.')
    add.add_argument("--command-template", help='Run a command instead of UI paste. Use {prompt}, e.g. "claude -p {prompt}".')
    add.add_argument("--delay", type=float, default=5, help="Seconds to wait before paste/submit.")
    add.add_argument("--file", help="Read the prompt from a UTF-8 text file.")
    add.add_argument("--max-attempts", type=int, default=5, help="Attempts before marking the job failed. Default: 5.")
    add.add_argument("--no-submit", action="store_true", help="Paste only; do not press Enter.")
    add.add_argument("--pre-keys", help='Windows SendKeys string to send before paste, e.g. "{ESC}".')
    add.add_argument("--retry-base", type=float, default=30, help="Initial retry delay in seconds. Default: 30.")
    add.add_argument("--stdin", action="store_true", help="Read the prompt from stdin.")
    add.add_argument("--window", help='Window title substring to focus before paste, like "Codex" or "Claude".')
    add.add_argument("when", help='Local time, like "23:30" or "2026-06-24 01:15".')
    add.add_argument("target", help="copy, claude, chatgpt, copilot, gemini, cursor, codex, URL, or command.")
    add.add_argument("prompt", nargs=argparse.REMAINDER)
    add.set_defaults(func=add_job)

    show = sub.add_parser("list")
    show.add_argument("--all", action="store_true")
    show.add_argument("--full", action="store_true")
    show.set_defaults(func=list_jobs)

    show_one = sub.add_parser("show")
    show_one.add_argument("id")
    show_one.set_defaults(func=show_job)

    remove = sub.add_parser("remove")
    remove.add_argument("id")
    remove.set_defaults(func=remove_job)

    windows = sub.add_parser("windows")
    windows.set_defaults(func=list_windows)

    targets = sub.add_parser("targets")
    targets.set_defaults(func=list_targets)

    run = sub.add_parser("run")
    run.add_argument("--once", action="store_true")
    run.add_argument("--poll", type=float, default=15)
    run.set_defaults(func=run_loop)

    check = sub.add_parser("selftest")
    check.set_defaults(func=lambda _args: selftest())

    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main(sys.argv[1:])
