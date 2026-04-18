#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

from collect_artifacts import collect, list_dump_files
from run_loop import (
    append_trace,
    any_game_running,
    ensure_dir,
    parse_auto_json,
    require_ok,
    resolve_artifacts_root,
    resolve_h74_operator_script,
    resolve_locked_launch_bat,
    resolve_log_dir,
    run_build,
    send_command,
    str2bool,
    trigger_login_via_ui,
    try_dismiss_trace_notice,
    wait_telnet_connect,
    wait_login_ready,
    write_json,
)
from telnet_driver import TelnetDriver


def run_launch_bat_with_env(launch_bat: Path, out_log_path: Path, extra_env: dict[str, str] | None = None) -> int:
    cmd = ["cmd", "/c", str(launch_bat)]
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    env = os.environ.copy()
    if extra_env:
        env.update({str(k): str(v) for k, v in extra_env.items()})
    proc = subprocess.Popen(
        cmd,
        cwd=str(launch_bat.parent),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
        env=env,
    )
    time.sleep(2.0)
    exit_code = proc.poll()
    status = "spawned" if exit_code is None else f"exited:{exit_code}"
    out_log_path.parent.mkdir(parents=True, exist_ok=True)
    out_log_path.write_text(
        "\n".join(
            [
                "[cmd] " + " ".join(cmd),
                f"[pid] {proc.pid}",
                f"[status] {status}",
                f"[repro_delay_ms] {extra_env.get('MESSIAH_MINIGIF_REPRO_DELAY_MS', '0') if extra_env else '0'}",
            ]
        ),
        encoding="utf-8",
    )
    if exit_code is None:
        return 0
    return exit_code


def kill_game_processes(process_names: list[str]) -> list[str]:
    killed = []
    for process_name in process_names:
        if not process_name:
            continue
        proc = subprocess.run(
            ["taskkill", "/IM", process_name, "/F"],
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0:
            killed.append(process_name)
    return killed


def resolve_minigif_path(repo_root: Path, requested_path: str | Path | None) -> Path:
    if requested_path and str(requested_path).strip():
        return Path(requested_path).resolve()
    candidates = [
        repo_root / "820_complete.nbs",
        repo_root / "Package/CGs/a050.nbs",
        repo_root / "Messiah/cliptest.nbs",
    ]
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate.exists():
            return candidate
    return candidates[0].resolve()


def resolve_switch_minigif_path(repo_root: Path, requested_path: str | Path | None, default_path: Path) -> Path:
    if requested_path and str(requested_path).strip():
        return Path(requested_path).resolve()
    candidates = [
        repo_root / "Package/CGs/a050.nbs",
        repo_root / "Messiah/cliptest.nbs",
        repo_root / "820_complete.nbs",
    ]
    default_resolved = default_path.resolve()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate.exists() and candidate != default_resolved:
            return candidate
    return default_resolved


def run_round(args, round_index: int) -> dict:
    run_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-minigif-r{round_index}"
    run_dir = ensure_dir(args.artifacts_root / run_id)
    trace_path = run_dir / "commands.trace"
    start_ts = time.time()
    known_dumps = {str(p) for p in list_dump_files(args.repo_root)}
    driver = TelnetDriver(host=args.telnet_host, port=args.telnet_port)

    result = {
        "run_id": run_id,
        "scenario": "minigif_replace_stress",
        "started_at": datetime.now().isoformat(),
        "phase_status": {"build": "pending", "launch": "pending", "login": "pending", "test": "pending", "analyze": "pending"},
        "outcome": "unknown",
        "key_logs": [],
        "next_action": "",
        "minigif_path": str(args.minigif_path),
    }

    try:
        if args.do_build:
            result["phase_status"]["build"] = "running"
            exit_code = run_build(
                repo_root=args.repo_root,
                build_script=args.build_script,
                action=args.build_action,
                configuration=args.build_configuration,
                platform=args.build_platform,
                timeout_sec=args.timeout_build,
                out_log_path=run_dir / "build.log",
            )
            if exit_code != 0:
                raise RuntimeError(f"build_failed:{exit_code}")
            result["phase_status"]["build"] = "success"
        else:
            result["phase_status"]["build"] = "skipped"

        result["phase_status"]["launch"] = "running"
        if not args.reuse_running_client or not any_game_running(args.game_process_names):
            if args.kill_existing_before_launch:
                killed = kill_game_processes(args.game_process_names)
                if killed:
                    result["killed_before_launch"] = killed
                    time.sleep(3.0)
            extra_env = {}
            if int(args.repro_delay_ms) > 0:
                extra_env["MESSIAH_MINIGIF_REPRO_DELAY_MS"] = str(int(args.repro_delay_ms))
            launch_exit = run_launch_bat_with_env(args.launch_bat, run_dir / "launch.log", extra_env=extra_env)
            if launch_exit != 0:
                raise RuntimeError(f"launch_failed:{launch_exit}")
            time.sleep(args.launch_settle_sec)
        result["phase_status"]["launch"] = "success"

        port, attempts, elapsed_sec = wait_telnet_connect(driver, args.timeout_connect, args.connect_progress_sec)
        result["connected_telnet_port"] = port
        result["telnet_attempts"] = attempts
        result["telnet_elapsed_sec"] = elapsed_sec

        if args.h74_operator_script:
            append_trace(trace_path, f"load script: {args.h74_operator_script}")
            driver.load_script(args.h74_operator_script, "Load Operator Success", timeout=60.0)
            result["project_operator_script_status"] = "loaded"
            result["project_operator_script_path"] = str(args.h74_operator_script)
        else:
            result["project_operator_script_status"] = "missing_skipped"
            result["project_operator_script_path"] = ""

        if args.login_before_repro:
            auto_loop_operator_script = args.auto_loop_operator_script.resolve()
            append_trace(trace_path, f"load script: {auto_loop_operator_script}")
            driver.load_script(auto_loop_operator_script, "Load Auto Loop Operator Success", timeout=30.0)
            result["phase_status"]["login"] = "running"
            trigger_login_via_ui(
                driver=driver,
                trace_path=trace_path,
                timeout_login_ui=args.timeout_login_ui,
                click_max_attempts=args.click_max_attempts,
                click_interval_sec=args.click_interval_sec,
                account=args.account,
                result=result,
            )
            try_dismiss_trace_notice(driver, trace_path, result, "before_wait_login_ready")
            wait_login_ready(driver, trace_path, args.timeout_login, result, False)
            try_dismiss_trace_notice(driver, trace_path, result, "after_login_ready")
            result["phase_status"]["login"] = "success"
        else:
            result["phase_status"]["login"] = "skipped"

        append_trace(trace_path, f"load script: {args.auto_operator_script}")
        driver.load_script(args.auto_operator_script, "Load MiniGif Repro Operator Success", timeout=30.0)

        payload = send_command(
            driver,
            trace_path,
            f"_minigif_repro_operator.set_minigif_path(r'{args.minigif_path.as_posix()}')",
            timeout=8.0,
        )
        require_ok(payload, "set_minigif_path")

        payload = send_command(
            driver,
            trace_path,
            f"_minigif_repro_operator.set_switch_minigif_path(r'{args.switch_minigif_path.as_posix()}')",
            timeout=8.0,
        )
        require_ok(payload, "set_switch_minigif_path")

        result["phase_status"]["test"] = "running"

        payload = send_command(
            driver,
            trace_path,
            (
                "_minigif_repro_operator.start_replace_stress("
                f"file_path=r'{args.minigif_path.as_posix()}',"
                f"total_rounds={int(args.rounds)},"
                f"seek_before_remove={'True' if bool(args.seek_before_remove) else 'False'},"
                f"pause_ms={int(args.pause_ms)},"
                f"keep_only_latest={'True' if bool(args.keep_only_latest) else 'False'},"
                f"clear_external_resources={'True' if bool(args.clear_external_resources) else 'False'},"
                f"remove_name={json.dumps(args.remove_name, ensure_ascii=False)},"
                f"cleanup_after_finish={'True' if bool(args.cleanup_after_finish) else 'False'},"
                f"wait_decoder_ready={'True' if bool(args.wait_decoder_ready) else 'False'},"
                f"wait_decoder_timeout_ms={int(args.wait_decoder_timeout_ms)},"
                f"post_ready_pause_ms={int(args.post_ready_pause_ms)},"
                f"overlap_nodes={int(args.overlap_nodes)},"
                f"steps_per_poll={int(args.steps_per_poll)},"
                f"play_before_seek_ms={int(args.play_before_seek_ms)},"
                f"mode={json.dumps(args.mode, ensure_ascii=False)},"
                f"switch_file_path=r'{args.switch_minigif_path.as_posix()}')"
            ),
            timeout=max(60.0, float(args.start_timeout_sec)),
        )
        require_ok(payload, "start_replace_stress")

        deadline = time.time() + float(args.timeout_scenario)
        poll_payload = {}
        while time.time() < deadline:
            poll_payload = send_command(driver, trace_path, "_minigif_repro_operator.poll()", timeout=30.0)
            require_ok(poll_payload, "poll")
            if poll_payload.get("status") == "success":
                break
            time.sleep(max(0.05, float(args.poll_interval_sec)))
        if poll_payload.get("status") != "success":
            raise TimeoutError(f"minigif poll timeout after {args.timeout_scenario}s, last={poll_payload}")
        result["minigif_repro_result"] = poll_payload
        result["phase_status"]["test"] = "success"
        result["outcome"] = "pass"
        result["next_action"] = "none"
    except TimeoutError as exc:
        result["outcome"] = "timeout"
        result["key_logs"].append(str(exc))
        result["next_action"] = "review_timeout"
    except Exception as exc:
        result["outcome"] = "fail"
        result["key_logs"].append(repr(exc))
        result["next_action"] = "review_failure"
    finally:
        if args.request_exit_on_finish and result.get("outcome") != "crash":
            try:
                send_command(driver, trace_path, "_minigif_repro_operator.request_exit()", timeout=5.0)
            except Exception:
                pass
        driver.close()
        if args.kill_existing_after_finish:
            time.sleep(2.0)
            killed_after = kill_game_processes(args.game_process_names)
            if killed_after:
                result["killed_after_finish"] = killed_after
        collected = collect(
            repo_root=args.repo_root,
            log_dir=args.log_dir,
            out_dir=run_dir,
            since_ts=start_ts,
            known_dumps=known_dumps,
        )
        result["copied_logs"] = collected.copied_logs
        result["copied_dumps"] = collected.copied_dumps
        if collected.dump_count > 0 and result.get("outcome") != "pass":
            result["outcome"] = "crash"
            result["crash_summary"] = {"dump_count": collected.dump_count, "dump_files": collected.copied_dumps}
            result["next_action"] = "analyze_crash_dump"
        result["phase_status"]["analyze"] = "done"
        write_json(run_dir / "result.json", result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Standalone MiniGif lifecycle repro")
    parser.add_argument("--repo-root", type=Path, default=Path(os.environ.get("MESSIAH_REPO_ROOT", "F:/messiah_h74")))
    parser.add_argument("--do-build", type=str2bool, default=False)
    parser.add_argument("--build-script", type=Path, default=Path(r"C:/Users/zhangruojun/.codex/skills/messiah-ib-build-fix/scripts/invoke_ib_build.ps1"))
    parser.add_argument("--build-action", default="build")
    parser.add_argument("--build-configuration", default="Hybrid")
    parser.add_argument("--build-platform", default="x64")
    parser.add_argument("--launch-bat", default="")
    parser.add_argument("--launch-settle-sec", type=int, default=12)
    parser.add_argument("--reuse-running-client", type=str2bool, default=False)
    parser.add_argument("--game-process-names", default="Game_x64h.exe,Game_x64r.exe")
    parser.add_argument("--kill-existing-before-launch", type=str2bool, default=True)
    parser.add_argument("--kill-existing-after-finish", type=str2bool, default=True)
    parser.add_argument("--telnet-host", default="127.0.0.1")
    parser.add_argument("--telnet-port", type=int, default=9113)
    parser.add_argument("--timeout-build", type=int, default=7200)
    parser.add_argument("--timeout-connect", type=int, default=60)
    parser.add_argument("--connect-progress-sec", type=int, default=10)
    parser.add_argument("--login-before-repro", type=str2bool, default=True)
    parser.add_argument("--timeout-login", type=int, default=300)
    parser.add_argument("--timeout-login-ui", type=int, default=10)
    parser.add_argument("--click-max-attempts", type=int, default=5)
    parser.add_argument("--click-interval-sec", type=float, default=0.5)
    parser.add_argument("--account", default="")
    parser.add_argument("--timeout-scenario", type=int, default=60)
    parser.add_argument("--start-timeout-sec", type=int, default=300)
    parser.add_argument("--poll-interval-sec", type=float, default=0.2)
    parser.add_argument("--rounds", type=int, default=300)
    parser.add_argument("--pause-ms", type=int, default=250)
    parser.add_argument("--seek-before-remove", type=str2bool, default=True)
    parser.add_argument("--keep-only-latest", type=str2bool, default=True)
    parser.add_argument("--clear-external-resources", type=str2bool, default=True)
    parser.add_argument("--remove-name", default="gifNode")
    parser.add_argument("--cleanup-after-finish", type=str2bool, default=True)
    parser.add_argument("--wait-decoder-ready", type=str2bool, default=True)
    parser.add_argument("--wait-decoder-timeout-ms", type=int, default=1500)
    parser.add_argument("--play-before-seek-ms", type=int, default=1000)
    parser.add_argument("--post-ready-pause-ms", type=int, default=250)
    parser.add_argument("--overlap-nodes", type=int, default=2)
    parser.add_argument("--steps-per-poll", type=int, default=1)
    parser.add_argument("--mode", default="seek_guard")
    parser.add_argument("--minigif-path", default="")
    parser.add_argument("--switch-minigif-path", default="")
    parser.add_argument("--repro-delay-ms", type=int, default=0)
    parser.add_argument("--request-exit-on-finish", type=str2bool, default=True)
    parser.add_argument("--artifacts-root", default="")
    parser.add_argument("--log-dir", default="")
    parser.add_argument("--h74-operator-script", default="")
    parser.add_argument(
        "--auto-operator-script",
        type=Path,
        default=(Path(__file__).resolve().parent / "in_game" / "minigif_repro_operator.py"),
    )
    parser.add_argument(
        "--auto-loop-operator-script",
        type=Path,
        default=(Path(__file__).resolve().parent / "in_game" / "auto_loop_operator.py"),
    )
    parser.add_argument("--max-rounds", type=int, default=1)
    parser.add_argument("--print-json", type=str2bool, default=False)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    args.repo_root = args.repo_root.resolve()
    args.artifacts_root = resolve_artifacts_root(args.repo_root, args.artifacts_root)
    args.log_dir = resolve_log_dir(args.repo_root, args.log_dir)
    args.h74_operator_script = resolve_h74_operator_script(args.repo_root, args.h74_operator_script)
    args.minigif_path = resolve_minigif_path(args.repo_root, args.minigif_path)
    args.switch_minigif_path = resolve_switch_minigif_path(args.repo_root, args.switch_minigif_path, args.minigif_path)
    args.auto_operator_script = args.auto_operator_script.resolve()
    args.auto_loop_operator_script = args.auto_loop_operator_script.resolve()
    args.game_process_names = [x.strip() for x in args.game_process_names.split(",") if x.strip()]
    args.rounds = max(1, int(args.rounds))
    args.pause_ms = max(0, int(args.pause_ms))

    locked_bat = resolve_locked_launch_bat(args.repo_root)
    if args.launch_bat:
        requested_bat = Path(args.launch_bat).resolve()
        if requested_bat != locked_bat:
            raise ValueError(f"launch-bat is locked to {locked_bat}, got {requested_bat}")
    args.launch_bat = locked_bat

    ensure_dir(args.artifacts_root)

    results = []
    for round_index in range(1, args.max_rounds + 1):
        result = run_round(args, round_index)
        results.append(result)
        if result.get("outcome") != "pass":
            break

    summary = {"created_at": datetime.now().isoformat(), "round_count": len(results), "results": results}
    summary_path = args.artifacts_root / "latest_minigif_summary.json"
    write_json(summary_path, summary)
    print(f"summary_path={summary_path}", flush=True)
    if args.print_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
