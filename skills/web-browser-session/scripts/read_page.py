from __future__ import annotations

import argparse

from browser_session_common import DEFAULT_PORT, connect_page, emit, wait_soft


def main() -> int:
    ap = argparse.ArgumentParser(description="Read current page text and optionally HTML.")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--tab-index", type=int, default=None)
    ap.add_argument("--url-contains", default="")
    ap.add_argument("--title-contains", default="")
    ap.add_argument("--include-html", default="false")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    p, browser, page, _pages = connect_page(args.port, args.tab_index, args.url_contains, args.title_contains)
    try:
        wait_soft(page)
        body_text = page.evaluate("() => document.body ? document.body.innerText : ''")
        data = {
            "ok": True,
            "page": {"url": page.url, "title": page.title()},
            "body_text": body_text,
        }
        if args.include_html.lower() == "true":
            data["html"] = page.content()
        return emit(data, args.out)
    finally:
        browser.close()
        p.stop()


if __name__ == "__main__":
    raise SystemExit(main())
