from __future__ import annotations

import argparse
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from browser_session_common import DEFAULT_PORT, DEFAULT_PROFILE, emit, find_free_port


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
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile),
            headless=False,
            no_viewport=True,
            args=[
                "--new-window",
                "--window-position=80,80",
                "--window-size=1400,900",
                f"--remote-debugging-port={port}",
            ],
        )
        page = context.pages[0] if context.pages else context.new_page()
        if args.url:
            page.goto(args.url, wait_until="domcontentloaded")
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
        context.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
