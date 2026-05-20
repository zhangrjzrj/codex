#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from telnet_driver import TelnetDriver


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Set Messiah client window size over Telnet.")
    parser.add_argument("width", type=int, help="Window width in pixels, for example 2580.")
    parser.add_argument("height", type=int, help="Window height in pixels, for example 1080.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9113)
    parser.add_argument("--log-dir", type=Path, default=Path(r"F:\messiah_h74\Messiah\LocalData\Log"))
    parser.add_argument("--timeout-sec", type=float, default=15.0)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.width <= 0 or args.height <= 0:
        raise SystemExit("width and height must be positive integers")

    command = f"import MUI;MUI.SetWindowPos({args.width},{args.height})"
    script = (
        "import json\n"
        "import MUI\n"
        f"MUI.SetWindowPos({args.width},{args.height})\n"
        "print('AUTO_JSON::' + json.dumps({"
        "'ok': True, "
        "'action': 'set_window_pos', "
        f"'width': {args.width}, "
        f"'height': {args.height}"
        "}, ensure_ascii=False))\n"
        "print('AUTO_END')"
    )
    wrapped_command = "exec(" + repr(script) + ")"
    driver = TelnetDriver(host=args.host, port=args.port, log_dir=args.log_dir)
    try:
        used_port = driver.connect()
        print(json.dumps({"connected": True, "port": used_port}, ensure_ascii=False))
        out = driver.command(wrapped_command, timeout=args.timeout_sec, accept_auto_json=True)
        print(
            json.dumps(
                {
                    "ok": True,
                    "action": "set_window_pos",
                    "width": args.width,
                    "height": args.height,
                    "command": command,
                    "output_tail": out[-600:],
                },
                ensure_ascii=False,
            )
        )
        return 0
    finally:
        driver.close()


if __name__ == "__main__":
    raise SystemExit(main())
