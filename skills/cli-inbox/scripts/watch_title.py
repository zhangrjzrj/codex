from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import sys
import time
from pathlib import Path


PREFIX_RE = re.compile(r"^●\s+\d+\s+")


def default_file() -> Path:
    env = os.environ.get("INBOX_FILE") or os.environ.get("CODEX_INBOX_FILE")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".task-inbox.txt"


def load_count(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        json.loads(line)
        count += 1
    return count


def process_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def get_window_text(hwnd: int) -> str:
    user32 = ctypes.windll.user32
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def set_window_text(hwnd: int, text: str) -> bool:
    try:
        return bool(ctypes.windll.user32.SetWindowTextW(hwnd, text))
    except Exception:
        return False


def strip_prefix(title: str) -> str:
    return PREFIX_RE.sub("", title).strip()


def build_title(base_title: str, count: int) -> str:
    base = base_title.strip() or "CLI"
    if count > 0:
        return f"● {count} {base}"
    return base


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Watch inbox count and refresh one window title.")
    parser.add_argument("--hwnd", type=int, required=True)
    parser.add_argument("--owner-pid", type=int, required=True)
    parser.add_argument("--file", default="")
    parser.add_argument("--poll-ms", type=int, default=800)
    args = parser.parse_args(argv)

    inbox = Path(args.file).expanduser() if args.file else default_file()
    hwnd = int(args.hwnd)
    poll_seconds = max(args.poll_ms, 200) / 1000.0

    base_title = strip_prefix(get_window_text(hwnd)) or "CLI"
    last_written = ""

    while process_exists(args.owner_pid):
        current_title = get_window_text(hwnd)
        current_base = strip_prefix(current_title)
        if current_base and current_title != last_written:
            base_title = current_base

        try:
            count = load_count(inbox)
        except Exception:
            count = 0

        desired = build_title(base_title, count)
        if desired != current_title:
            set_window_text(hwnd, desired)
            last_written = desired

        time.sleep(poll_seconds)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
