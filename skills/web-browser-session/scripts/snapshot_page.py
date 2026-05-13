from __future__ import annotations

import argparse

from browser_session_common import DEFAULT_PORT, connect_page, emit, list_tabs, snapshot, wait_soft


def main() -> int:
    ap = argparse.ArgumentParser(description="Extract a runtime DOM semantic snapshot from a browser tab.")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--tab-index", type=int, default=None)
    ap.add_argument("--url-contains", default="")
    ap.add_argument("--title-contains", default="")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    p, browser, page, _pages = connect_page(args.port, args.tab_index, args.url_contains, args.title_contains)
    try:
        wait_soft(page)
        data = snapshot(page)
        data["ok"] = True
        data["port"] = args.port
        data["tabs"] = list_tabs(args.port)
        return emit(data, args.out)
    finally:
        browser.close()
        p.stop()


if __name__ == "__main__":
    raise SystemExit(main())
