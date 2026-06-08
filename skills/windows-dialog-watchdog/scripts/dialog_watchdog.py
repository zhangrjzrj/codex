#!/usr/bin/env python3
import argparse
import ctypes
import json
import os
import signal
import subprocess
import sys
import time
from ctypes import wintypes
from datetime import datetime
from pathlib import Path


user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
EnumChildProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

WM_CLOSE = 0x0010
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_TERMINATE = 0x0001

user32.EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL
user32.EnumChildWindows.argtypes = [wintypes.HWND, EnumChildProc, wintypes.LPARAM]
user32.EnumChildWindows.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.restype = wintypes.BOOL

kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
kernel32.TerminateProcess.restype = wintypes.BOOL
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL


def now_iso():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def get_window_text(hwnd):
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value.strip()


def get_class_name(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value.strip()


def get_pid(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value)


def query_process_path(pid):
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(32768)
        buf = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return buf.value
        return ""
    finally:
        kernel32.CloseHandle(handle)


def process_name_from_path(path, pid):
    if path:
        return Path(path).name
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=2,
        ).strip()
    except Exception:
        return ""
    if not out or out.startswith("INFO:"):
        return ""
    return next(csv_cells(out), [""])[0]


def csv_cells(line):
    import csv

    yield from csv.reader([line])


def enum_child_text(hwnd):
    items = []

    def callback(child_hwnd, _):
        if user32.IsWindowVisible(child_hwnd):
            text = get_window_text(child_hwnd)
            cls = get_class_name(child_hwnd)
            if text:
                items.append({"hwnd": hex(child_hwnd), "class": cls, "text": text})
        return True

    user32.EnumChildWindows(hwnd, EnumChildProc(callback), 0)
    return items


def enum_top_windows():
    windows = []

    def callback(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            title = get_window_text(hwnd)
            cls = get_class_name(hwnd)
            if title or cls == "#32770":
                windows.append({"hwnd": int(hwnd), "title": title, "class": cls, "pid": get_pid(hwnd)})
        return True

    user32.EnumWindows(EnumWindowsProc(callback), 0)
    return windows


def contains_any(value, needles):
    if not needles:
        return True
    lower = value.lower()
    return any(n.lower() in lower for n in needles)


def match_event(window, args):
    pid = window["pid"]
    if args.pid and pid not in args.pid:
        return None

    path = query_process_path(pid)
    name = process_name_from_path(path, pid)
    if args.process_name and not contains_any(name, args.process_name):
        return None
    if args.process_path_contains and not contains_any(path, args.process_path_contains):
        return None

    child_items = enum_child_text(window["hwnd"])
    texts = [window["title"]] + [item["text"] for item in child_items]
    combined_text = "\n".join(t for t in texts if t)
    matched_keywords = [k for k in args.keyword if k.lower() in combined_text.lower()]
    if args.keyword and not matched_keywords:
        return None

    if not args.include_all_classes:
        has_dialog_signals = window["class"] == "#32770" or child_items
        if not has_dialog_signals:
            return None

    return {
        "timestamp": now_iso(),
        "window_hwnd": hex(window["hwnd"]),
        "window_class": window["class"],
        "window_title": window["title"],
        "dialog_text": combined_text,
        "child_controls": child_items,
        "matched_keywords": matched_keywords,
        "pid": pid,
        "process_name": name,
        "process_path": path,
    }


def default_evidence_dir():
    cwd = Path.cwd()
    if (cwd / ".codex-memory").exists():
        return cwd / ".codex-memory" / "tasks" / "dialog-watchdog"
    return cwd / "dialog-watchdog-evidence"


def write_event(evidence_dir, event):
    evidence_dir.mkdir(parents=True, exist_ok=True)
    with (evidence_dir / "events.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def take_screenshot(evidence_dir, seq):
    try:
        import PIL.ImageGrab
    except Exception:
        return ""
    path = evidence_dir / f"screenshot-{seq:04d}.png"
    try:
        PIL.ImageGrab.grab().save(path)
        return str(path)
    except Exception:
        return ""


def close_window(hwnd):
    return bool(user32.PostMessageW(hwnd, WM_CLOSE, 0, 0))


def kill_process(pid):
    handle = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
    if not handle:
        return False
    try:
        return bool(kernel32.TerminateProcess(handle, 57005))
    finally:
        kernel32.CloseHandle(handle)


def repeat_key_for(event, mode):
    if mode == "exact":
        return f"{event['pid']}|{event['window_title']}|{event['dialog_text'][:200]}"
    if event["matched_keywords"]:
        signature = ",".join(sorted(event["matched_keywords"]))
    else:
        signature = event["window_title"] or event["window_class"]
    return f"{event['pid']}|{event['process_name']}|{signature}"


def scan(args, evidence_dir, repeats, seq):
    events = []
    for window in enum_top_windows():
        if args.max_events and seq + len(events) >= args.max_events:
            break
        event = match_event(window, args)
        if not event:
            continue
        key = repeat_key_for(event, args.repeat_key_mode)
        repeats[key] = repeats.get(key, 0) + 1
        event["repeat_key"] = key
        event["repeat_key_mode"] = args.repeat_key_mode
        event["repeat_count"] = repeats[key]
        event["action"] = "record"
        event["reason"] = "matched_dialog"
        if args.screenshot:
            event["screenshot"] = take_screenshot(evidence_dir, seq + len(events) + 1)
        if args.auto_close:
            event["close_posted"] = close_window(window["hwnd"])
            event["action"] = "close_window"
        if args.auto_kill and repeats[key] >= args.kill_threshold:
            event["kill_posted"] = kill_process(event["pid"])
            event["action"] = "kill_process"
            event["reason"] = "repeat_threshold_reached"
        write_event(evidence_dir, event)
        print(json.dumps(event, ensure_ascii=False), flush=True)
        events.append(event)
    return events


def parse_args():
    parser = argparse.ArgumentParser(description="Detect Windows modal dialogs, save evidence, and optionally close or kill repeated offenders.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--watch", action="store_true", help="scan repeatedly until stopped")
    mode.add_argument("--once", action="store_true", help="scan once and exit")
    parser.add_argument("--interval", type=float, default=1.0, help="watch interval in seconds")
    parser.add_argument("--pid", type=int, action="append", default=[], help="PID to match; repeatable")
    parser.add_argument("--process-name", action="append", default=[], help="process name substring to match; repeatable")
    parser.add_argument("--process-path-contains", action="append", default=[], help="process path substring to match; repeatable")
    parser.add_argument("--keyword", action="append", default=[], help="dialog title/text substring to match; repeatable")
    parser.add_argument("--evidence-dir", default="", help="directory for events.jsonl and screenshots")
    parser.add_argument("--auto-close", action="store_true", help="send WM_CLOSE to matched dialog windows")
    parser.add_argument("--auto-kill", action="store_true", help="kill owning process when repeat threshold is reached")
    parser.add_argument("--kill-threshold", type=int, default=3, help="repeat count before killing a process")
    parser.add_argument("--repeat-key-mode", choices=["signature", "exact"], default="signature", help="signature groups dialogs by PID and matched keywords; exact groups by PID, title, and text prefix")
    parser.add_argument("--max-events", type=int, default=0, help="stop after this many matched events")
    parser.add_argument("--screenshot", action="store_true", help="try to save a desktop screenshot per event")
    parser.add_argument("--include-all-classes", action="store_true", help="allow non-dialog top-level windows that match filters")
    args = parser.parse_args()
    if not args.watch and not args.once:
        args.once = True
    if args.auto_kill and not (args.pid or args.process_name or args.process_path_contains):
        parser.error("--auto-kill requires --pid, --process-name, or --process-path-contains")
    if args.kill_threshold < 1:
        parser.error("--kill-threshold must be >= 1")
    return args


def main():
    args = parse_args()
    evidence_dir = Path(args.evidence_dir) if args.evidence_dir else default_evidence_dir()
    repeats = {}
    total = 0
    stop = False

    def handle_stop(signum, frame):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, handle_stop)
    signal.signal(signal.SIGTERM, handle_stop)

    print(f"dialog_watchdog evidence_dir={evidence_dir}", flush=True)
    while True:
        events = scan(args, evidence_dir, repeats, total)
        total += len(events)
        if args.max_events and total >= args.max_events:
            return 2 if total else 0
        if args.once or stop:
            return 2 if total else 0
        time.sleep(args.interval)


if __name__ == "__main__":
    if os.name != "nt":
        print("dialog_watchdog only supports Windows.", file=sys.stderr)
        sys.exit(1)
    sys.exit(main())
