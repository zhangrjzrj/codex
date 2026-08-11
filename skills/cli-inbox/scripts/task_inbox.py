from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def default_file() -> Path:
    env = os.environ.get("INBOX_FILE") or os.environ.get("CODEX_INBOX_FILE")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".task-inbox.txt"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def new_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}_{secrets.token_hex(3)}"


def ensure_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("", encoding="utf-8")


def set_console_title(text: str) -> bool:
    ok = False
    try:
        import ctypes
        ok = bool(ctypes.windll.kernel32.SetConsoleTitleW(text))
    except Exception:
        ok = False
    try:
        sys.stdout.write(f"\x1b]0;{text}\x07")
        sys.stdout.flush()
        ok = True
    except Exception:
        pass
    return ok


def refresh_title(path: Path) -> int:
    count = len(load_rows(path))
    title = f"● {count}" if count > 0 else "Inbox"
    set_console_title(title)
    return count


def load_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def write_rows(path: Path, rows: list[dict]) -> None:
    ensure_file(path)
    text = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    if text:
        text += "\n"
    path.write_text(text, encoding="utf-8")


def resolve_index(rows: list[dict], item_id: str) -> int:
    exact = [i for i, row in enumerate(rows) if row.get("id") == item_id]
    if exact:
        return exact[0]
    matches = [i for i, row in enumerate(rows) if str(row.get("id", "")).startswith(item_id)]
    if not matches:
        raise SystemExit(f"item not found: {item_id}")
    if len(matches) > 1:
        raise SystemExit(f"item id is ambiguous: {item_id}")
    return matches[0]


def cmd_add(args: argparse.Namespace) -> int:
    inbox = Path(args.file).expanduser() if args.file else default_file()
    rows = load_rows(inbox)
    item_id = args.id or new_id()
    if any(row.get("id") == item_id for row in rows):
        raise SystemExit(f"item already exists: {item_id}")
    rows.append(
        {
            "id": item_id,
            "title": args.title,
            "cli_title": args.cli_title,
            "session_id": args.session_id,
            "workdir": args.workdir,
            "created_at": args.created_at or utc_now(),
            "message": args.message,
        }
    )
    write_rows(inbox, rows)
    refresh_title(inbox)
    print(inbox)
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    inbox = Path(args.file).expanduser() if args.file else default_file()
    rows = load_rows(inbox)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        refresh_title(inbox)
        return 0
    if not rows:
        print("no unread items")
        refresh_title(inbox)
        return 0
    for row in rows:
        print(f"{row['id']} | {row.get('title', '')} | {row.get('cli_title', '')} | {row.get('session_id', '')}")
    refresh_title(inbox)
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    inbox = Path(args.file).expanduser() if args.file else default_file()
    rows = load_rows(inbox)
    index = resolve_index(rows, args.item_id)
    print(json.dumps(rows[index], ensure_ascii=False, indent=2))
    refresh_title(inbox)
    return 0


def cmd_ack(args: argparse.Namespace) -> int:
    inbox = Path(args.file).expanduser() if args.file else default_file()
    rows = load_rows(inbox)
    index = resolve_index(rows, args.item_id)
    item = rows.pop(index)
    write_rows(inbox, rows)
    refresh_title(inbox)
    print(f"acked {item['id']}")
    return 0


def cmd_ack_thread(args: argparse.Namespace) -> int:
    inbox = Path(args.file).expanduser() if args.file else default_file()
    rows = load_rows(inbox)
    kept = []
    removed = []
    for row in rows:
        if row.get("session_id") == args.thread_id:
            removed.append(row["id"])
        else:
            kept.append(row)
    if not removed:
        print("no unread items for thread")
        refresh_title(inbox)
        return 0
    write_rows(inbox, kept)
    refresh_title(inbox)
    for item_id in removed:
        print(f"acked {item_id}")
    return 0


def _focus_window_by_keywords(keywords: list[str]) -> bool:
    if not any(keywords):
        return False
    try:
        import ctypes

        user32 = ctypes.windll.user32
        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        titles: list[tuple[int, str]] = []

        @EnumWindowsProc
        def enum_proc(hwnd, lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value
            if title:
                titles.append((hwnd, title))
            return True

        user32.EnumWindows(enum_proc, 0)
        lowered = [k.lower() for k in keywords if k]
        for hwnd, title in titles:
            low = title.lower()
            if any(k in low for k in lowered):
                user32.ShowWindow(hwnd, 9)
                user32.SetForegroundWindow(hwnd)
                return True
    except Exception:
        return False
    return False


def _pick_index_gui(rows: list[dict]) -> Optional[int]:
    try:
        import tkinter as tk
        from tkinter import ttk
    except Exception:
        return None

    chosen: list[Optional[int]] = [None]
    root = tk.Tk()
    root.title("Inbox")
    root.geometry("1100x520")
    frm = ttk.Frame(root, padding=12)
    frm.pack(fill="both", expand=True)
    ttk.Label(frm, text="双击或按回车打开并已读").pack(anchor="w")
    lb = tk.Listbox(frm, activestyle="dotbox")
    lb.pack(fill="both", expand=True, pady=(8, 8))
    for idx, row in enumerate(rows):
        lb.insert(tk.END, f"{idx + 1}. {row['id']} | {row.get('title', '')} | {row.get('cli_title', '')} | {row.get('session_id', '')}")

    def choose(event=None):
        sel = lb.curselection()
        if not sel:
            return
        chosen[0] = int(sel[0])
        root.destroy()

    lb.bind("<Double-Button-1>", choose)
    lb.bind("<Return>", choose)
    btns = ttk.Frame(frm)
    btns.pack(fill="x")
    ttk.Button(btns, text="打开", command=choose).pack(side="left")
    ttk.Button(btns, text="取消", command=root.destroy).pack(side="right")
    lb.selection_set(0)
    lb.focus_set()
    root.mainloop()
    return chosen[0]


def _pick_index_console(rows: list[dict]) -> Optional[int]:
    for i, row in enumerate(rows, 1):
        print(f"{i}. {row['id']} | {row.get('title', '')} | {row.get('cli_title', '')} | {row.get('session_id', '')}")
    choice = input("选择编号，回车取消: ").strip()
    if not choice:
        return None
    try:
        index = int(choice) - 1
    except ValueError:
        return None
    if index < 0 or index >= len(rows):
        return None
    return index


def cmd_pick(args: argparse.Namespace) -> int:
    inbox = Path(args.file).expanduser() if args.file else default_file()
    rows = load_rows(inbox)
    if not rows:
        print("no unread items")
        return 0
    use_gui = os.environ.get("INBOX_FORCE_CONSOLE", "").strip().lower() not in {"1", "true", "yes"} and sys.stdin.isatty()
    index = _pick_index_gui(rows) if use_gui else None
    if index is None:
        index = _pick_index_console(rows)
    if index is None:
        print("cancelled")
        refresh_title(inbox)
        return 0
    row = rows.pop(index)
    if not args.no_focus:
        _focus_window_by_keywords([row.get("session_id", ""), row.get("cli_title", ""), row.get("workdir", ""), row.get("title", "")])
    write_rows(inbox, rows)
    refresh_title(inbox)
    print(json.dumps(row, ensure_ascii=False, indent=2))
    print(f"acked {row['id']}")
    return 0


def cmd_refresh_title(args: argparse.Namespace) -> int:
    inbox = Path(args.file).expanduser() if args.file else default_file()
    count = refresh_title(inbox)
    print(f"unread={count}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage a file-backed unread inbox.")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--file", help="Inbox file. Defaults to INBOX_FILE or ~/.task-inbox.txt.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    add = sub.add_parser("add", help="Add a pending item.", parents=[common])
    add.add_argument("--id")
    add.add_argument("--title", required=True)
    add.add_argument("--cli-title", default="")
    add.add_argument("--session-id", default="")
    add.add_argument("--workdir", default="")
    add.add_argument("--created-at", default="")
    add.add_argument("--message", required=True)
    add.set_defaults(func=cmd_add)

    listing = sub.add_parser("list", help="List unread items.", parents=[common])
    listing.add_argument("--json", action="store_true")
    listing.set_defaults(func=cmd_list)

    show = sub.add_parser("show", help="Show one unread item.", parents=[common])
    show.add_argument("item_id")
    show.set_defaults(func=cmd_show)

    ack = sub.add_parser("ack", help="Remove one unread item.", parents=[common])
    ack.add_argument("item_id")
    ack.set_defaults(func=cmd_ack)

    ack_thread = sub.add_parser("ack-thread", help="Remove all unread items for one thread.", parents=[common])
    ack_thread.add_argument("--thread-id", required=True)
    ack_thread.set_defaults(func=cmd_ack_thread)

    pick = sub.add_parser("pick", help="Pick one unread item and ack it.", parents=[common])
    pick.add_argument("--no-focus", action="store_true")
    pick.set_defaults(func=cmd_pick)

    refresh = sub.add_parser("refresh-title", help="Refresh the current console title from unread count.", parents=[common])
    refresh.set_defaults(func=cmd_refresh_title)

    return parser


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
