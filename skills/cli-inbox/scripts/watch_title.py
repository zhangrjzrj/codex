from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from task_inbox import default_file as inbox_default_file
from task_inbox import load_rows, write_rows


PREFIX_RE = re.compile(r"^●\s+\d+\s+")
SESSION_RE = re.compile(r"(?i)(?:^|\s)resume\s+([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(?:\s|$)")
def default_file() -> Path:
    return inbox_default_file()


def load_count(path: Path) -> int:
    return len(load_rows(path))


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


def resolve_session_id(owner_pid: int) -> str:
    script = rf"""
$ownerPid = {int(owner_pid)}
$procs = Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,CommandLine
$queue = New-Object System.Collections.Generic.Queue[int]
$queue.Enqueue($ownerPid)
$seen = New-Object 'System.Collections.Generic.HashSet[int]'
while($queue.Count -gt 0) {{
  $current = $queue.Dequeue()
  if(-not $seen.Add($current)) {{ continue }}
  foreach($p in $procs) {{
    if([int]$p.ParentProcessId -eq $current) {{
      $cmd = [string]$p.CommandLine
      if($cmd -match '(?i)(?:^|\s)resume\s+([0-9a-f]{{8}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{12}})(?:\s|$)') {{
        Write-Output $Matches[1]
        return
      }}
      $queue.Enqueue([int]$p.ProcessId)
    }}
  }}
}}
"""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return ""
    if result.returncode != 0:
        return ""
    text = (result.stdout or "").strip()
    match = SESSION_RE.search(" " + text)
    return match.group(1) if match else text


def resolve_session_file(session_id: str) -> Path | None:
    if not session_id:
        return None
    sessions_root = Path.home() / ".codex" / "sessions"
    if not sessions_root.exists():
        return None
    matches = list(sessions_root.rglob(f"rollout-*{session_id}.jsonl"))
    if not matches:
        return None
    matches.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    return matches[0]


def ack_thread(path: Path, thread_id: str) -> bool:
    if not thread_id:
        return False
    rows = load_rows(path)
    kept = [row for row in rows if row.get("session_id") != thread_id]
    if len(kept) == len(rows):
        return False
    write_rows(path, kept)
    return True


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def scan_user_message_since(path: Path | None, offset: int, min_timestamp: str) -> tuple[int, bool]:
    if path is None or not path.exists():
        return offset, False
    size = path.stat().st_size
    if size < offset:
        offset = 0
    if size == offset:
        return offset, False
    saw_user_message = False
    with path.open("r", encoding="utf-8") as handle:
        handle.seek(offset)
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if row.get("type") != "event_msg":
                continue
            row_timestamp = str(row.get("timestamp") or "")
            if row_timestamp and row_timestamp < min_timestamp:
                continue
            payload = row.get("payload") or {}
            if payload.get("type") == "user_message":
                saw_user_message = True
        offset = handle.tell()
    return offset, saw_user_message


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Watch inbox count and refresh one window title.")
    parser.add_argument("--hwnd", type=int, required=True)
    parser.add_argument("--owner-pid", type=int, required=True)
    parser.add_argument("--file", default="")
    parser.add_argument("--session-id", default="")
    parser.add_argument("--session-file", default="")
    parser.add_argument("--poll-ms", type=int, default=800)
    args = parser.parse_args(argv)

    inbox = Path(args.file).expanduser() if args.file else default_file()
    hwnd = int(args.hwnd)
    poll_seconds = max(args.poll_ms, 200) / 1000.0

    base_title = strip_prefix(get_window_text(hwnd)) or "CLI"
    last_written = ""
    session_id = str(args.session_id or "").strip()
    session_file = Path(args.session_file).expanduser() if args.session_file else None
    last_session_probe = 0.0
    watch_started_at = utc_now_iso()
    session_offset = 0

    while process_exists(args.owner_pid):
        current_title = get_window_text(hwnd)
        current_base = strip_prefix(current_title)
        if current_base and current_title != last_written:
            base_title = current_base

        now = time.time()
        if not session_id and now - last_session_probe >= 3.0:
            session_id = resolve_session_id(args.owner_pid)
            if session_id and session_file is None:
                session_file = resolve_session_file(session_id)
            last_session_probe = now
        elif session_id and session_file is None and now - last_session_probe >= 3.0:
            session_file = resolve_session_file(session_id)
            last_session_probe = now

        session_offset, saw_user_message = scan_user_message_since(session_file, session_offset, watch_started_at)
        if saw_user_message and session_id:
            ack_thread(inbox, session_id)

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
