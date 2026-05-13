from __future__ import annotations

import argparse

from browser_session_common import DEFAULT_PORT, emit, list_tabs


def main() -> int:
    ap = argparse.ArgumentParser(description="List tabs from a CDP browser session.")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    return emit({"ok": True, "port": args.port, "tabs": list_tabs(args.port)}, args.out)


if __name__ == "__main__":
    raise SystemExit(main())
