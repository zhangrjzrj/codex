from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="Login URL (manual captcha/verification).")
    parser.add_argument("--state", default="auth_state.json", help="Output storage_state JSON.")
    parser.add_argument(
        "--save-signal",
        default="",
        help="Optional path to a signal file. When it exists, save storage_state and exit. "
        "Useful when stdin is not interactive (no input prompt).",
    )
    parser.add_argument(
        "--auto-save-on",
        default="",
        help="Optional URL substring. When page.url contains this substring, save storage_state and exit.",
    )
    parser.add_argument(
        "--timeout-sec",
        type=int,
        default=30 * 60,
        help="Max seconds to wait for login completion (default: 1800).",
    )
    args = parser.parse_args()

    state_path = Path(args.state).resolve()
    save_signal = Path(args.save_signal).resolve() if args.save_signal else None
    auto_save_on = str(args.auto_save_on or "").strip()
    timeout_sec = int(args.timeout_sec)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(args.url, wait_until="domcontentloaded")
        initial_netloc = urlparse(page.url or "").netloc

        interactive = False
        try:
            interactive = bool(sys.stdin and sys.stdin.isatty())
        except Exception:
            interactive = False

        need_wait = True

        if interactive and not save_signal and not auto_save_on:
            try:
                input("Finish login / captcha on the browser, then press Enter here to save state...")
                need_wait = False
            except EOFError:
                # Some environments report isatty() but still can't accept input.
                need_wait = True

        if need_wait:
            deadline = time.time() + timeout_sec
            print("Login window opened.")
            if save_signal:
                print(f"Waiting for save signal file: {save_signal}")
            if auto_save_on:
                print(f"Waiting for URL to contain: {auto_save_on!r}")
            if not save_signal and not auto_save_on:
                print(
                    "No stdin prompt available. Falling back to heuristic: wait for site to change from "
                    f"{initial_netloc!r}. (You can provide --save-signal or --auto-save-on for precision.)",
                )

            while time.time() < deadline:
                if save_signal and save_signal.exists():
                    break
                if auto_save_on and (auto_save_on in (page.url or "")):
                    break
                if (not save_signal and not auto_save_on) and (urlparse(page.url or "").netloc != initial_netloc):
                    break
                time.sleep(0.5)

            if time.time() >= deadline:
                browser.close()
                print("timeout waiting for login completion; state not saved")
                return 2

        context.storage_state(path=str(state_path))
        browser.close()

    print(f"saved: {state_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
