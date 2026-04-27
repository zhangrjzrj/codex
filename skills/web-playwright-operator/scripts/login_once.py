from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="Login URL (manual captcha/verification).")
    parser.add_argument("--state", default="auth_state.json", help="Output storage_state JSON.")
    args = parser.parse_args()

    state_path = Path(args.state).resolve()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(args.url, wait_until="domcontentloaded")
        input("Finish login / captcha on the browser, then press Enter here to save state...")
        context.storage_state(path=str(state_path))
        browser.close()

    print(f"saved: {state_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

