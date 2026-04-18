#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from telnet_driver import TelnetDriver, parse_auto_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Connect to Messiah Telnet and send commands.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9113)
    parser.add_argument("--log-dir", type=Path, default=Path(r"F:\messiah_h74\Messiah\LocalData\Log"))
    parser.add_argument("--load-script", type=Path, default=None)
    parser.add_argument("--load-success-text", default="Load Auto Loop Operator Success")
    parser.add_argument("--command", action="append", default=[])
    parser.add_argument("--timeout-sec", type=float, default=20.0)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    driver = TelnetDriver(host=args.host, port=args.port, log_dir=args.log_dir)
    try:
        used_port = driver.connect()
        print(json.dumps({"connected": True, "port": used_port}, ensure_ascii=False))
        if args.load_script:
            out = driver.load_script(args.load_script, args.load_success_text, timeout=max(10.0, args.timeout_sec))
            print(json.dumps({"loaded_script": str(args.load_script), "output_tail": out[-400:]}, ensure_ascii=False))
        for command in args.command:
            out = driver.command(command, timeout=args.timeout_sec, accept_auto_json=True)
            payload = parse_auto_json(out)
            print(json.dumps({"command": command, "payload": payload, "output_tail": out[-600:]}, ensure_ascii=False))
        return 0
    finally:
        driver.close()


if __name__ == "__main__":
    raise SystemExit(main())
