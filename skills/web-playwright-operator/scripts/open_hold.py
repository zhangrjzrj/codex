from __future__ import annotations

import argparse
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="URL to open.")
    parser.add_argument("--state", default="", help="Optional storage_state JSON to reuse login.")
    parser.add_argument(
        "--close-signal",
        default="close.signal",
        help="Close when this file exists (default: close.signal in cwd).",
    )
    parser.add_argument(
        "--timeout-sec",
        type=int,
        default=24 * 60 * 60,
        help="Max seconds to keep the browser open (default: 86400).",
    )
    args = parser.parse_args()

    close_signal = Path(args.close_signal).resolve()
    state = Path(args.state).resolve() if args.state else None
    deadline = time.time() + int(args.timeout_sec)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--new-window",
                "--window-position=50,50",
                "--window-size=1400,900",
            ],
        )
        context = browser.new_context(storage_state=str(state) if state else None, no_viewport=True)
        page = context.new_page()
        page.goto(args.url, wait_until="domcontentloaded")
        try:
            page.bring_to_front()
        except Exception:
            pass

        print("opened:", page.url)
        print("close by creating:", close_signal)

        while time.time() < deadline:
            if close_signal.exists():
                break
            time.sleep(0.5)

        browser.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
