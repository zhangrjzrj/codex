from __future__ import annotations

import argparse

from browser_session_common import DEFAULT_PORT, connect_page, emit, get_action_element, wait_soft


def main() -> int:
    ap = argparse.ArgumentParser(description="Perform a browser action against a CDP session.")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--tab-index", type=int, default=None)
    ap.add_argument("--url-contains", default="")
    ap.add_argument("--title-contains", default="")
    ap.add_argument("--action", required=True, choices=["goto", "activate_tab", "click", "fill", "press"])
    ap.add_argument("--id", type=int, default=None, help="Snapshot element id for click/fill.")
    ap.add_argument("--text", default="", help="Text for fill, key for press, or URL for goto.")
    ap.add_argument("--force", default="false")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    p, browser, page, pages = connect_page(args.port, args.tab_index, args.url_contains, args.title_contains)
    try:
        if args.action == "activate_tab":
            page.bring_to_front()
        elif args.action == "goto":
            if not args.text:
                raise RuntimeError("--text must be URL for goto")
            page.goto(args.text, wait_until="domcontentloaded", timeout=30000)
        elif args.action == "press":
            if not args.text:
                raise RuntimeError("--text must be key for press")
            page.keyboard.press(args.text)
        elif args.action == "click":
            if args.id is None:
                raise RuntimeError("--id required for click")
            locator, item = get_action_element(page, "clickable", args.id)
            locator.click(timeout=10000, force=args.force.lower() == "true")
        elif args.action == "fill":
            if args.id is None:
                raise RuntimeError("--id required for fill")
            locator, item = get_action_element(page, "input", args.id)
            locator.fill(args.text, timeout=10000, force=args.force.lower() == "true")
        wait_soft(page)
        return emit({"ok": True, "action": args.action, "url": page.url, "title": page.title()}, args.out)
    finally:
        browser.close()
        p.stop()


if __name__ == "__main__":
    raise SystemExit(main())
