from __future__ import annotations

import argparse
import socket
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from browser_session_common import DEFAULT_PORT, DEFAULT_PROFILE, emit, find_free_port


LOCK_FILES = ("SingletonLock", "SingletonCookie", "SingletonSocket")


def port_is_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def profile_is_locked(profile: Path) -> bool:
    return any((profile / name).exists() for name in LOCK_FILES)


def wait_for_port(port: int, timeout_sec: int = 20) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if port_is_open(port):
            return True
        time.sleep(0.2)
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="Open a persistent Chromium session with CDP enabled.")
    ap.add_argument("--url", default="about:blank")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--profile-dir", default=str(DEFAULT_PROFILE))
    ap.add_argument("--close-signal", default="")
    ap.add_argument("--timeout-sec", type=int, default=24 * 60 * 60)
    ap.add_argument("--strict-port", default="false", help="Use the requested port exactly; otherwise choose the next free port.")
    args = ap.parse_args()

    port = args.port if args.strict_port.lower() == "true" else find_free_port(args.port)
    profile = Path(args.profile_dir).resolve()
    profile.mkdir(parents=True, exist_ok=True)
    close_signal = Path(args.close_signal).resolve() if args.close_signal else profile / "close.signal"
    if close_signal.exists():
        close_signal.unlink()

    deadline = time.time() + args.timeout_sec
    with sync_playwright() as p:
        owns_context = False
        if port_is_open(port):
            browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}", timeout=10000)
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            page = context.new_page() if args.url else (context.pages[0] if context.pages else context.new_page())
            if args.url:
                page.goto(args.url, wait_until="domcontentloaded")
        else:
            active_profile = profile
            if profile_is_locked(profile):
                active_profile = profile.parent / f"{profile.name}.session-{port}"
                active_profile.mkdir(parents=True, exist_ok=True)
            browser_exe = p.chromium.executable_path
            proc = subprocess.Popen(
                [
                    browser_exe,
                    "--new-window",
                    "--window-position=80,80",
                    "--window-size=1400,900",
                    f"--remote-debugging-port={port}",
                    f"--user-data-dir={str(active_profile)}",
                    args.url or "about:blank",
                ]
            )
            if not wait_for_port(port, timeout_sec=20):
                raise RuntimeError(f"browser did not expose CDP on port {port}")
            browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}", timeout=10000)
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            page = context.pages[0] if context.pages else context.new_page()
            if args.url and page.url != args.url:
                page.goto(args.url, wait_until="domcontentloaded")
            owns_context = True
        try:
            page.bring_to_front()
        except Exception:
            pass

        emit({
            "ok": True,
            "port": port,
            "profile_dir": str(profile),
            "close_signal": str(close_signal),
            "url": page.url,
            "title": page.title(),
            "cdp": f"http://127.0.0.1:{port}",
        })

        while time.time() < deadline:
            if close_signal.exists():
                break
            time.sleep(0.5)
        if owns_context:
            context.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
