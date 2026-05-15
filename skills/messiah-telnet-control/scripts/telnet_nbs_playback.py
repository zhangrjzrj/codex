#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from telnet_driver import TelnetDriver, parse_auto_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start Messiah NBS playback over Telnet.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9113)
    parser.add_argument("--log-dir", type=Path, default=Path(r"F:\messiah_h74\Messiah\LocalData\Log"))
    parser.add_argument(
        "--operator-script",
        type=Path,
        default=Path(r"C:\Users\zhangruojun\.codex\skills\messiah-test-loop\scripts\in_game\auto_loop_operator.py"),
    )
    parser.add_argument("--demo-path", type=Path, required=True)
    parser.add_argument("--montid", default="")
    parser.add_argument("--nbs", default="")
    parser.add_argument("--aspect-width", type=float, default=0.0)
    parser.add_argument("--aspect-height", type=float, default=0.0)
    parser.add_argument("--poll-interval-sec", type=float, default=2.0)
    parser.add_argument("--max-polls", type=int, default=40)
    return parser


def send(driver: TelnetDriver, command: str, timeout: float = 20.0) -> dict:
    out = driver.command(command, timeout=timeout, accept_auto_json=True)
    payload = parse_auto_json(out)
    print(json.dumps({"command": command, "payload": payload}, ensure_ascii=False))
    return payload


def main() -> int:
    args = build_parser().parse_args()
    driver = TelnetDriver(host=args.host, port=args.port, log_dir=args.log_dir)
    try:
        used_port = driver.connect()
        print(json.dumps({"connected": True, "port": used_port}, ensure_ascii=False))
        driver.load_script(args.operator_script, "Load Auto Loop Operator Success", timeout=30.0)
        login_state = send(driver, "_auto_loop_operator.check_login_ready()", timeout=15.0)
        if not (login_state.get("ok") and login_state.get("ready")):
            ready_ui = send(driver, "_auto_loop_operator.wait_login_ui_ready(10.0)", timeout=15.0)
            if ready_ui.get("ok") and ready_ui.get("ready"):
                click_result = send(driver, "_auto_loop_operator.click_start_game_with_retry(5, 0.5, 1.0)", timeout=20.0)
                if not click_result.get("success"):
                    send(driver, "_auto_loop_operator.fallback_do_gm_login()", timeout=20.0)
            deadline = time.time() + 60.0
            while time.time() < deadline:
                login_state = send(driver, "_auto_loop_operator.check_login_ready()", timeout=15.0)
                if login_state.get("ok") and login_state.get("ready"):
                    break
                time.sleep(2.0)
        send(driver, f"_auto_loop_operator.set_nbs_demo_path(r'{args.demo_path.resolve().as_posix()}')", timeout=8.0)
        send(
            driver,
            "_auto_loop_operator.set_nbs_run_args("
            f"montid={json.dumps(args.montid)},"
            f"nbs={json.dumps(args.nbs)},"
            f"aspect_width={float(args.aspect_width)},"
            f"aspect_height={float(args.aspect_height)})",
            timeout=8.0,
        )
        start_payload = send(driver, "_auto_loop_operator.start_scenario('nbs_playback')", timeout=20.0)
        final_payload = start_payload
        success_seen = False
        for _ in range(max(1, args.max_polls)):
            time.sleep(max(0.2, args.poll_interval_sec))
            try:
                final_payload = send(driver, "_auto_loop_operator.poll_scenario()", timeout=20.0)
            except Exception as exc:
                print(json.dumps({"poll_error": repr(exc), "success_seen": success_seen}, ensure_ascii=False))
                break
            status = str(final_payload.get("status", ""))
            if status == "success":
                success_seen = True
                break
            if final_payload.get("done") is True or status in {"failed", "timeout", "finished", "idle"}:
                break
        print(json.dumps({"success_seen": success_seen, "final": final_payload}, ensure_ascii=False))
        return 0 if success_seen else 1
    finally:
        driver.close()


if __name__ == "__main__":
    raise SystemExit(main())
