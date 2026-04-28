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
from telnet_driver import TelnetDriver, parse_auto_json

LOCKED_LAUNCH_BAT_REL = Path(r"cooked_client/Client/Messiah_Demo_常规启动_RenderDoc抓帧专用.bat")


def str2bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_locked_launch_bat(repo_root: Path) -> Path:
    bat = (repo_root / LOCKED_LAUNCH_BAT_REL).resolve()
    if not bat.exists():
        raise FileNotFoundError(f"locked launch bat missing: {bat}")
    return bat


def resolve_h74_operator_script(repo_root: Path, requested_path: str | Path | None) -> Path | None:
    if requested_path and str(requested_path).strip():
        path = Path(requested_path).resolve()
        if path.exists():
            return path
        return None

    candidates = [
        repo_root
        / "Messiah/Package/Script/Python3/src/utils/debug/gpm/land_scene_builder/scripts/h74_game_operator.py",
        repo_root
        / "Messiah/Package_cooked/Script/Python3/src/utils/debug/gpm/land_scene_builder/scripts/h74_game_operator.py",
        repo_root
        / "cooked_client/Client/Package/Script/Python3/src/utils/debug/gpm/land_scene_builder/scripts/h74_game_operator.py",
    ]
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate.exists():
            return candidate
    return None


def resolve_nbs_demo_path(repo_root: Path, requested_path: str | Path | None) -> Path:
    if requested_path and str(requested_path).strip():
        return Path(requested_path).resolve()
    return (repo_root / "Messiah/NBSDemo.py").resolve()


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


def resolve_log_dir(repo_root: Path, requested_path: str | Path | None) -> Path:
    if requested_path and str(requested_path).strip():
        return Path(requested_path).resolve()
    candidates = [
        repo_root / "Messiah/LocalData/Log",
        repo_root / "cooked_client/Client/LocalData/Log",
    ]
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate.exists():
            return candidate
    return candidates[0].resolve()


def resolve_artifacts_root(repo_root: Path, requested_path: str | Path | None) -> Path:
    if requested_path and str(requested_path).strip():
        return Path(requested_path).resolve()
    return (repo_root / "artifacts/test_runs").resolve()


def run_build(
    repo_root: Path,
    build_script: Path,
    action: str,
    configuration: str,
    platform: str,
    timeout_sec: int,
    out_log_path: Path,
) -> int:
    cmd = [
        "powershell",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(build_script),
        "-RepoRoot",
        str(repo_root),
        "-Action",
        action,
        "-Configuration",
        configuration,
        "-Platform",
        platform,
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        timeout=timeout_sec,
    )
    combined = [
        "[cmd] " + " ".join(cmd),
        "[stdout]",
        proc.stdout,
        "[stderr]",
        proc.stderr,
        f"[exit_code] {proc.returncode}",
    ]
    write_text(out_log_path, "\n".join(combined))
    return proc.returncode


def run_launch_bat(launch_bat: Path, out_log_path: Path) -> int:
    cmd = ["cmd", "/c", str(launch_bat)]
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    proc = subprocess.Popen(
        cmd,
        cwd=str(launch_bat.parent),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )
    time.sleep(2.0)
    exit_code = proc.poll()
    status = "spawned" if exit_code is None else f"exited:{exit_code}"
    combined = [
        "[cmd] " + " ".join(cmd),
        f"[pid] {proc.pid}",
        f"[status] {status}",
    ]
    write_text(out_log_path, "\n".join(combined))
    if exit_code is None:
        return 0
    return exit_code


def run_rdc_analysis(
    repo_root: Path,
    analyzer_script: Path,
    rdc_path: Path,
    output_json: Path,
    pass_keyword: str,
    stage: str,
    timeout_sec: int,
    qrenderdoc_path: str,
    cb_value_mode: str,
    cb_top_n: int,
    cb_neighbor_window: int,
    cb_nonzero_only: bool,
    target_event_id: int,
) -> int:
    cmd = [
        "python",
        str(analyzer_script),
        "--rdc-path",
        str(rdc_path),
        "--output-json",
        str(output_json),
        "--pass-keyword",
        str(pass_keyword),
        "--stage",
        str(stage),
        "--timeout-sec",
        str(timeout_sec),
        "--cb-value-mode",
        str(cb_value_mode),
        "--cb-top-n",
        str(max(1, int(cb_top_n))),
        "--cb-neighbor-window",
        str(max(0, int(cb_neighbor_window))),
        "--cb-nonzero-only",
        str(bool(cb_nonzero_only)).lower(),
    ]
    if int(target_event_id) > 0:
        cmd.extend(["--target-event-id", str(int(target_event_id))])
    if qrenderdoc_path and str(qrenderdoc_path).strip():
        cmd.extend(["--qrenderdoc-path", str(qrenderdoc_path).strip()])
    proc = subprocess.run(
        cmd,
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        timeout=max(60, int(timeout_sec) + 60),
    )
    write_text(
        output_json.with_suffix(".run.log"),
        "\n".join(
            [
                "[cmd] " + " ".join(cmd),
                f"[exit_code] {proc.returncode}",
                "[stdout]",
                proc.stdout or "",
                "[stderr]",
                proc.stderr or "",
            ]
        ),
    )
    return proc.returncode


def is_process_running(process_name: str) -> bool:
    cmd = ["tasklist", "/FI", f"IMAGENAME eq {process_name}", "/FO", "CSV", "/NH"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    out = (proc.stdout or "").strip().lower()
    if not out:
        return False
    if out.startswith("info:"):
        return False
    return process_name.lower() in out


def any_game_running(process_names: list[str]) -> bool:
    return any(is_process_running(name) for name in process_names)


def append_trace(trace_path: Path, text: str) -> None:
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    with trace_path.open("a", encoding="utf-8") as fp:
        fp.write(text)
        fp.write("\n")


def send_command(driver: TelnetDriver, trace_path: Path, command: str, timeout: float = 20.0) -> dict:
    out = driver.command(command, timeout=timeout, accept_auto_json=True)
    append_trace(trace_path, f"[{datetime.now().isoformat()}] CMD: {command}")
    append_trace(trace_path, out)
    payload = parse_auto_json(out)
    return payload


def require_ok(payload: dict, action: str) -> None:
    if not payload:
        raise RuntimeError(f"{action}: empty payload")
    if payload.get("ok") is False:
        raise RuntimeError(f"{action}: {payload}")


def wait_telnet_connect(
    driver: TelnetDriver,
    timeout_sec: int,
    progress_interval_sec: int = 10,
) -> tuple[int, int, int]:
    start_ts = time.time()
    deadline = time.time() + timeout_sec
    last_error = None
    attempt = 0
    next_progress_at = start_ts + max(1, progress_interval_sec)
    while time.time() < deadline:
        attempt += 1
        try:
            port = driver.connect()
            elapsed_sec = int(time.time() - start_ts)
            return port, attempt, elapsed_sec
        except Exception as exc:
            last_error = exc
            now = time.time()
            if now >= next_progress_at:
                elapsed_sec = int(now - start_ts)
                print(
                    f"[progress] telnet retrying: attempts={attempt}, elapsed={elapsed_sec}s/{timeout_sec}s",
                    flush=True,
                )
                next_progress_at = now + max(1, progress_interval_sec)
            time.sleep(2.0)
    raise TimeoutError(f"telnet connect timeout after {timeout_sec}s, last={last_error!r}")


def wait_login_ready(
    driver: TelnetDriver,
    trace_path: Path,
    timeout_sec: int,
    result: dict,
    abort_on_trace_notice: bool,
) -> dict:
    deadline = time.time() + timeout_sec
    last_payload = {}
    while time.time() < deadline:
        if abort_on_trace_notice:
            try_dismiss_trace_notice(driver, trace_path, result, "wait_login_ready")
            if result.get("trace_notice_abort"):
                raise RuntimeError("trace_notice_detected_during_login")
        if result.get("abort_on_process_exit"):
            if not result.get("game_process_names"):
                pass
            else:
                if not any_game_running(result["game_process_names"]):
                    raise RuntimeError("game_process_exited_during_login")
        payload = send_command(driver, trace_path, "_auto_loop_operator.check_login_ready()", timeout=15.0)
        last_payload = payload
        if payload.get("ok") and payload.get("ready"):
            return payload
        time.sleep(2.0)
    raise TimeoutError(f"login timeout after {timeout_sec}s, last={last_payload}")


def wait_login_ui_ready(driver: TelnetDriver, trace_path: Path, timeout_sec: int) -> dict:
    cmd = f"_auto_loop_operator.wait_login_ui_ready({float(timeout_sec)})"
    payload = send_command(driver, trace_path, cmd, timeout=max(8.0, float(timeout_sec) + 5.0))
    require_ok(payload, "wait_login_ui_ready")
    if not payload.get("ready"):
        raise TimeoutError(f"login ui not ready after {timeout_sec}s, last={payload}")
    return payload


def trigger_login_via_ui(
    driver: TelnetDriver,
    trace_path: Path,
    timeout_login_ui: int,
    click_max_attempts: int,
    click_interval_sec: float,
    account: str,
    result: dict,
) -> None:
    print("[step] wait login ui ready", flush=True)
    payload = wait_login_ui_ready(driver, trace_path, timeout_login_ui)
    result["login_ui_ready"] = bool(payload.get("ready"))
    result["login_ui_type"] = payload.get("ui_type", "")
    print(f"[step] login ui ready ui_type={result['login_ui_type']}", flush=True)

    if account:
        print("[step] set login account from cli", flush=True)
        payload = send_command(
            driver,
            trace_path,
            f"_auto_loop_operator.set_login_account({json.dumps(str(account), ensure_ascii=False)})",
            timeout=8.0,
        )
        require_ok(payload, "set_login_account")
        result["login_account"] = payload.get("account", str(account))
        result["login_account_source"] = "cli"
    else:
        result["login_account_source"] = "ui_current"

    print(
        f"[step] click start game retry max_attempts={click_max_attempts} interval={click_interval_sec}s",
        flush=True,
    )
    click_timeout = max(20.0, click_max_attempts * (click_interval_sec + 4.0) + 15.0)
    payload = send_command(
        driver,
        trace_path,
        (
            "_auto_loop_operator.click_start_game_with_retry("
            f"max_attempts={int(click_max_attempts)},"
            f"interval_sec={float(click_interval_sec)})"
        ),
        timeout=click_timeout,
    )
    require_ok(payload, "click_start_game_with_retry")
    result["click_start_triggered"] = bool(payload.get("clicked"))
    result["click_start_success"] = bool(payload.get("success"))
    result["click_start_attempts"] = int(payload.get("attempts_used", 0))
    result["click_start_reason"] = payload.get("reason", "")
    result["click_start_ui_type"] = payload.get("last_ui_type", result.get("login_ui_type", ""))
    result["blockers_dismissed_count"] = int(payload.get("blockers_dismissed_count", 0))
    result["blockers_found_count"] = int(payload.get("blockers_found_count", 0))
    result["used_fallback_do_gm_login"] = False
    result["fallback_success"] = False

    if not result["click_start_success"]:
        print("[step] click retry exhausted, try fallback do_gm_login", flush=True)
        fb_payload = send_command(driver, trace_path, "_auto_loop_operator.fallback_do_gm_login()", timeout=20.0)
        require_ok(fb_payload, "fallback_do_gm_login")
        result["used_fallback_do_gm_login"] = True
        result["fallback_success"] = bool(fb_payload.get("success"))
        result["fallback_reason"] = fb_payload.get("reason", "")
        if not result["fallback_success"]:
            raise RuntimeError(
                "click_exhausted_and_fallback_failed: "
                f"click={payload}, fallback={fb_payload}"
            )
        result["final_login_trigger"] = "do_gm_login_fallback"
    else:
        result["final_login_trigger"] = "button_click"


def try_dismiss_trace_notice(
    driver: TelnetDriver,
    trace_path: Path,
    result: dict,
    stage: str,
) -> None:
    try:
        payload = send_command(driver, trace_path, "_auto_loop_operator.dismiss_trace_notice()", timeout=8.0)
        if payload.get("ok"):
            found = bool(payload.get("found"))
            dismissed = bool(payload.get("dismissed"))
            if found:
                result["trace_notice_found_count"] = int(result.get("trace_notice_found_count", 0)) + 1
            if dismissed:
                result["trace_notice_dismissed_count"] = int(result.get("trace_notice_dismissed_count", 0)) + 1
            reason = str(payload.get("reason", ""))
            if dismissed:
                action = "dismissed"
                print(f"[step] trace notice dismissed stage={stage}", flush=True)
            elif found:
                action = "found_not_dismissed"
                print(f"[step] trace notice found but not dismissed stage={stage}", flush=True)
            else:
                action = "not_found"
            result["trace_notice_last_action"] = f"{stage}:{action}" + (f":{reason}" if reason else "")
            if found and result.get("abort_on_trace_notice"):
                result["trace_notice_abort"] = True
        else:
            result["trace_notice_last_action"] = f"{stage}:error_payload"
            result["key_logs"].append(f"dismiss_trace_notice payload_error at {stage}: {payload}")
    except Exception as exc:
        result["trace_notice_last_action"] = f"{stage}:error_exception"
        result["key_logs"].append(f"dismiss_trace_notice exception at {stage}: {exc!r}")


def wait_scenario_done(
    driver: TelnetDriver,
    trace_path: Path,
    timeout_sec: int,
    process_names: list[str],
    abort_on_process_exit: bool,
) -> dict:
    deadline = time.time() + timeout_sec
    last_payload = {}
    while time.time() < deadline:
        if abort_on_process_exit and process_names:
            if not any_game_running(process_names):
                raise RuntimeError("game_process_exited_during_scenario")
        payload = send_command(driver, trace_path, "_auto_loop_operator.poll_scenario()", timeout=20.0)
        last_payload = payload
        status = payload.get("status")
        if status == "success":
            return payload
        if status == "failed":
            raise RuntimeError(f"scenario failed: {payload}")
        time.sleep(2.0)
    raise TimeoutError(f"scenario timeout after {timeout_sec}s, last={last_payload}")


def create_fix_plan(fix_plan_path: Path, result: dict) -> None:
    text = "\n".join(
        [
            "# Fix Plan",
            "",
            f"- run_id: {result.get('run_id')}",
            f"- scenario: {result.get('scenario')}",
            f"- outcome: {result.get('outcome')}",
            "",
            "## Analysis Inputs",
            "- result.json",
            "- logs in this run directory",
            "- dumps in this run directory (if any)",
            "",
            "## Proposed Next Step",
            "- Analyze top error/crash signature.",
            "- Propose minimal safe patch.",
            "- Wait for user approval before code changes.",
            "",
        ]
    )
    write_text(fix_plan_path, text)


def stop_here(result: dict, stage: str) -> dict:
    if result["phase_status"]["login"] == "pending":
        result["phase_status"]["login"] = "skipped"
    if result["phase_status"]["test"] == "pending":
        result["phase_status"]["test"] = "skipped"
    result["outcome"] = "paused"
    result["paused_at"] = stage
    result["phase_status"]["analyze"] = "done"
    result["next_action"] = "wait_user_instruction"
    return result


def run_round(args, round_index: int) -> dict:
    run_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-r{round_index}"
    run_dir = ensure_dir(args.artifacts_root / run_id)
    trace_path = run_dir / "commands.trace"
    start_ts = time.time()

    result = {
        "run_id": run_id,
        "scenario": args.scenario,
        "stop_point": args.stop_point,
        "started_at": datetime.now().isoformat(),
        "phase_status": {
            "build": "pending",
            "launch": "pending",
            "login": "pending",
            "test": "pending",
            "analyze": "pending",
        },
        "outcome": "unknown",
        "key_logs": [],
        "crash_summary": {},
        "next_action": "",
        "trace_notice_found_count": 0,
        "trace_notice_dismissed_count": 0,
        "trace_notice_last_action": "not_checked",
        "trace_notice_abort": False,
        "abort_on_trace_notice": False,
        "abort_on_process_exit": bool(args.abort_on_process_exit),
        "game_process_names": list(args.game_process_names),
        "renderdoc_capture_requested": False,
        "renderdoc_capture_mode": "",
        "renderdoc_capture_stage": "",
        "renderdoc_capture_error": "",
        "renderdoc_capture_delay_frames": 0,
        "renderdoc_capture_target_frame": 0,
        "renderdoc_capture_target_mode": "",
        "renderdoc_capture_frame_mode": "",
        "renderdoc_capture_window_size": 0,
        "renderdoc_capture_pre_roll": 0,
        "renderdoc_capture_trigger_frame": 0,
        "renderdoc_capture_triggered_at_frame": 0,
        "renderdoc_capture_api": "",
        "rdc_analysis": {
            "enabled": bool(args.analyze_rdc),
            "status": "disabled",
            "reason": "",
            "rdc_path": "",
            "output_json": "",
            "analysis_status": "",
            "disasm_full_path": "",
            "target_event_id": 0,
            "target_event_id_requested": int(args.analyze_rdc_target_event_id),
            "exit_code": None,
            "cb_value_mode": str(args.analyze_rdc_cb_value_mode),
            "cb_top_n": int(args.analyze_rdc_cb_top_n),
            "cb_neighbor_window": int(args.analyze_rdc_cb_neighbor_window),
            "cb_nonzero_only": bool(args.analyze_rdc_cb_nonzero_only),
        },
    }

    known_dumps = {str(p) for p in list_dump_files(args.repo_root)}
    driver = TelnetDriver(host=args.telnet_host, port=args.telnet_port, log_dir=args.log_dir)

    try:
        print(f"[step] run={run_id} scenario={args.scenario} stop_point={args.stop_point}", flush=True)
        effective_launch_bat = args.launch_bat
        if str(getattr(args, "game_args", "")).strip():
            effective_launch_bat = write_custom_launch_bat(run_dir, args.repo_root, args.game_args)
        print(f"[step] launch_bat_locked={args.launch_bat}", flush=True)
        if effective_launch_bat != args.launch_bat:
            print(f"[step] launch_bat_effective={effective_launch_bat}", flush=True)
        if args.do_build:
            result["phase_status"]["build"] = "running"
            print("[step] build started", flush=True)
            code = run_build(
                repo_root=args.repo_root,
                build_script=args.build_script,
                action=args.build_action,
                configuration=args.build_configuration,
                platform=args.build_platform,
                timeout_sec=args.timeout_build,
                out_log_path=run_dir / "build.log",
            )
            if code != 0:
                result["phase_status"]["build"] = "failed"
                result["phase_status"]["analyze"] = "done"
                result["outcome"] = "fail"
                result["key_logs"].append("build failed")
                result["next_action"] = "analyze_build_errors"
                return result
            result["phase_status"]["build"] = "success"
            print("[step] build success", flush=True)
        else:
            result["phase_status"]["build"] = "skipped"

        result["phase_status"]["launch"] = "running"
        print("[step] launch client", flush=True)
        already_running = any_game_running(args.game_process_names)
        if already_running and args.reuse_running_client:
            write_text(run_dir / "launch.log", "[info] detected existing game process, reuse running client")
            result["phase_status"]["launch"] = "reused_running_client"
            print("[step] reuse running client", flush=True)
        else:
            launch_exit = run_launch_bat(effective_launch_bat, run_dir / "launch.log")
            result["phase_status"]["launch"] = "success" if launch_exit == 0 else "success_with_warning"
            if args.launch_settle_sec > 0:
                time.sleep(args.launch_settle_sec)

        print("[step] connect telnet", flush=True)
        connected_port, connect_attempts, connect_elapsed_sec = wait_telnet_connect(
            driver,
            args.timeout_connect,
            args.connect_progress_sec,
        )
        result["connected_telnet_port"] = connected_port
        result["connect_attempts"] = connect_attempts
        result["connect_elapsed_sec"] = connect_elapsed_sec
        append_trace(trace_path, f"connected telnet {args.telnet_host}:{connected_port}")
        print(
            f"[step] telnet connected {args.telnet_host}:{connected_port} attempts={connect_attempts} elapsed={connect_elapsed_sec}s",
            flush=True,
        )
        if args.stop_point == "after_connect":
            return stop_here(result, "after_connect")

        print("[step] load operator scripts", flush=True)
        if args.h74_operator_script and args.h74_operator_script.exists():
            print(f"[step] use project operator script: {args.h74_operator_script}", flush=True)
            append_trace(trace_path, f"load script: {args.h74_operator_script}")
            driver.load_script(args.h74_operator_script, "Load Operator Success", timeout=60.0)
            result["project_operator_script_status"] = "loaded"
            result["project_operator_script_path"] = str(args.h74_operator_script)
        else:
            print("[step] skip project operator script (not found)", flush=True)
            result["project_operator_script_status"] = "missing_skipped"
            result["project_operator_script_path"] = ""
        append_trace(trace_path, f"load script: {args.auto_operator_script}")
        driver.load_script(args.auto_operator_script, "Load Auto Loop Operator Success", timeout=30.0)

        payload = send_command(
            driver,
            trace_path,
            f"_auto_loop_operator.set_nbs_demo_path(r'{args.nbs_demo_path.as_posix()}')",
            timeout=8.0,
        )
        require_ok(payload, "set_nbs_demo_path")
        if args.stop_point == "after_operator_load":
            return stop_here(result, "after_operator_load")

        if args.stop_point == "after_click_start":
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
            try_dismiss_trace_notice(driver, trace_path, result, "after_click_start")
            result["phase_status"]["login"] = "success"
            return stop_here(result, "after_click_start")

        result["phase_status"]["login"] = "running"
        print("[step] login", flush=True)
        if args.server_profile:
            if not args.account:
                raise RuntimeError("account is required when --server-profile is set")
            print(f"[step] login mode=profile profile={args.server_profile}", flush=True)
            login_cmd = (
                f"_auto_loop_operator.login_with_profile({json.dumps(args.server_profile, ensure_ascii=False)},"
                f"{args.space_type},{args.spaceno},{args.ship_config_id},{json.dumps(args.account, ensure_ascii=False)})"
            )
            payload = send_command(driver, trace_path, login_cmd, timeout=20.0)
            require_ok(payload, "login_with_profile")
            result["login_mode"] = "profile"
            result["login_profile"] = args.server_profile
            result["login_account"] = args.account
            result["login_account_source"] = "cli"
            result["final_login_trigger"] = "profile_login"
        else:
            print("[step] login mode=ui_selection", flush=True)
            trigger_login_via_ui(
                driver=driver,
                trace_path=trace_path,
                timeout_login_ui=args.timeout_login_ui,
                click_max_attempts=args.click_max_attempts,
                click_interval_sec=args.click_interval_sec,
                account=args.account,
                result=result,
            )
            result["login_mode"] = "ui_selection"
        try_dismiss_trace_notice(driver, trace_path, result, "before_wait_login_ready")
        wait_login_ready(driver, trace_path, args.timeout_login, result, False)
        try_dismiss_trace_notice(driver, trace_path, result, "after_login_ready")
        result["phase_status"]["login"] = "success"
        if args.stop_point == "after_login":
            return stop_here(result, "after_login")

        result["phase_status"]["test"] = "running"
        try_dismiss_trace_notice(driver, trace_path, result, "before_start_scenario")
        print(f"[step] start scenario {args.scenario}", flush=True)
        if args.scenario == "nbs_playback" and args.capture_on_playback_start:
            if args.capture_target_frame > 0:
                capture_target_mode = str(args.capture_target_mode)
                capture_mode = "target_window" if capture_target_mode == "target_window" else "target_frame"
                capture_window_size = int(args.capture_window_size)
                capture_pre_roll = int(args.capture_pre_roll)
                if capture_mode == "target_frame":
                    capture_window_size = 1
                    capture_pre_roll = 0
                print(
                    (
                        "[step] renderdoc capture on playback target frame "
                        f"mode={capture_mode} target={args.capture_target_frame} frame_mode={args.capture_frame_mode} "
                        f"window={capture_window_size} pre_roll={capture_pre_roll}"
                    ),
                    flush=True,
                )
                payload = send_command(
                    driver,
                    trace_path,
                    (
                        "_auto_loop_operator.start_nbs_playback_with_capture("
                        f"{json.dumps(capture_mode)},0,{int(args.capture_target_frame)},"
                        f"{json.dumps(args.capture_frame_mode)},{capture_window_size},{capture_pre_roll})"
                    ),
                    timeout=20.0,
                )
                result["renderdoc_capture_mode"] = str(payload.get("capture_mode", capture_mode))
                result["renderdoc_capture_target_frame"] = int(args.capture_target_frame)
                result["renderdoc_capture_target_mode"] = capture_target_mode
                result["renderdoc_capture_frame_mode"] = str(args.capture_frame_mode)
                result["renderdoc_capture_window_size"] = int(capture_window_size)
                result["renderdoc_capture_pre_roll"] = int(capture_pre_roll)
            else:
                print(
                    f"[step] renderdoc capture on playback start enabled mode=playing_delay_frames delay={args.capture_delay_frames}",
                    flush=True,
                )
                payload = send_command(
                    driver,
                    trace_path,
                    (
                        "_auto_loop_operator.start_nbs_playback_with_capture("
                        f"'playing_delay_frames',{int(args.capture_delay_frames)})"
                    ),
                    timeout=20.0,
                )
                result["renderdoc_capture_mode"] = str(payload.get("capture_mode", "playing_delay_frames"))
                result["renderdoc_capture_delay_frames"] = int(args.capture_delay_frames)
            result["renderdoc_capture_requested"] = True
            result["renderdoc_capture_stage"] = "on_playback_start"
            if payload.get("ok") is False:
                result["renderdoc_capture_error"] = str(payload.get("error", "unknown"))
            require_ok(payload, "start_nbs_playback_with_capture")
        else:
            if args.capture_on_playback_start and args.scenario != "nbs_playback":
                msg = "capture_on_playback_start ignored: scenario is not nbs_playback"
                result["key_logs"].append(msg)
                print(f"[step] {msg}", flush=True)
            payload = send_command(driver, trace_path, f"_auto_loop_operator.start_scenario('{args.scenario}')", timeout=20.0)
            require_ok(payload, "start_scenario")
        scenario_done_payload = wait_scenario_done(
            driver,
            trace_path,
            args.timeout_scenario,
            args.game_process_names,
            args.abort_on_process_exit,
        )
        if args.scenario == "nbs_playback":
            result["renderdoc_capture_api"] = str(scenario_done_payload.get("capture_api", ""))
            try:
                result["renderdoc_capture_trigger_frame"] = int(scenario_done_payload.get("capture_trigger_frame", 0) or 0)
            except Exception:
                result["renderdoc_capture_trigger_frame"] = 0
            try:
                result["renderdoc_capture_triggered_at_frame"] = int(
                    scenario_done_payload.get("capture_triggered_at_frame", 0) or 0
                )
            except Exception:
                result["renderdoc_capture_triggered_at_frame"] = 0
            capture_error = str(scenario_done_payload.get("capture_error", "") or "")
            if capture_error and not result.get("renderdoc_capture_error"):
                result["renderdoc_capture_error"] = capture_error
        result["phase_status"]["test"] = "success"

        if args.analyze_rdc:
            rdc_info = result["rdc_analysis"]
            rdc_info["status"] = "running"
            analysis_output_json = run_dir / "rdc_analysis.json"
            rdc_info["output_json"] = str(analysis_output_json)
            if not args.analyze_rdc_script.exists():
                rdc_info["status"] = "failed"
                rdc_info["reason"] = f"analyzer_script_missing:{args.analyze_rdc_script}"
                result["key_logs"].append(rdc_info["reason"])
            elif not args.analyze_rdc_path:
                rdc_info["status"] = "skipped"
                rdc_info["reason"] = "analyze_rdc_path_empty"
            elif not args.analyze_rdc_path.exists():
                rdc_info["status"] = "skipped"
                rdc_info["reason"] = f"rdc_missing:{args.analyze_rdc_path}"
            else:
                rdc_info["rdc_path"] = str(args.analyze_rdc_path)
                print(
                    f"[step] analyze rdc path={args.analyze_rdc_path} pass={args.analyze_rdc_pass_keyword} stage={args.analyze_rdc_stage}",
                    flush=True,
                )
                exit_code = run_rdc_analysis(
                    repo_root=args.repo_root,
                    analyzer_script=args.analyze_rdc_script,
                    rdc_path=args.analyze_rdc_path,
                    output_json=analysis_output_json,
                    pass_keyword=args.analyze_rdc_pass_keyword,
                    stage=args.analyze_rdc_stage,
                    timeout_sec=args.analyze_rdc_timeout,
                    qrenderdoc_path=args.analyze_rdc_qrenderdoc_path,
                    cb_value_mode=args.analyze_rdc_cb_value_mode,
                    cb_top_n=args.analyze_rdc_cb_top_n,
                    cb_neighbor_window=args.analyze_rdc_cb_neighbor_window,
                    cb_nonzero_only=args.analyze_rdc_cb_nonzero_only,
                    target_event_id=args.analyze_rdc_target_event_id,
                )
                rdc_info["exit_code"] = int(exit_code)
                analysis_payload = {}
                if analysis_output_json.exists():
                    try:
                        analysis_payload = json.loads(analysis_output_json.read_text(encoding="utf-8"))
                    except Exception as exc:
                        analysis_payload = {}
                        result["key_logs"].append(f"rdc_analysis_parse_failed:{exc!r}")
                status = str(analysis_payload.get("status", "")).strip().lower()
                if status in {"success", "partial", "fail"}:
                    rdc_info["analysis_status"] = status
                if status == "success" and exit_code == 0:
                    rdc_info["status"] = "success"
                elif status in {"partial", "success"} and exit_code == 0:
                    rdc_info["status"] = "partial"
                else:
                    rdc_info["status"] = "failed"
                if analysis_payload.get("target"):
                    try:
                        rdc_info["target_event_id"] = int(analysis_payload["target"].get("event_id", 0))
                    except Exception:
                        rdc_info["target_event_id"] = 0
                    try:
                        rdc_info["target_event_id_requested"] = int(
                            analysis_payload["target"].get("requested_event_id", rdc_info.get("target_event_id_requested", 0))
                        )
                    except Exception:
                        rdc_info["target_event_id_requested"] = int(rdc_info.get("target_event_id_requested", 0) or 0)
                if analysis_payload.get("shader"):
                    rdc_info["disasm_full_path"] = str(analysis_payload["shader"].get("disasm_full_path", ""))
                if rdc_info["status"] == "failed":
                    rdc_info["reason"] = f"rdc_analysis_failed(exit={exit_code},status={status or 'unknown'})"
                    result["key_logs"].append(rdc_info["reason"])

        result["outcome"] = "pass"
        result["phase_status"]["analyze"] = "done"
        result["next_action"] = "none"
        return result

    except TimeoutError as exc:
        result["outcome"] = "timeout"
        result["key_logs"].append(str(exc))
        result["next_action"] = "review_timeout"
    except Exception as exc:
        result["outcome"] = "fail"
        result["key_logs"].append(repr(exc))
        result["next_action"] = "review_failure"
    finally:
        if args.request_exit_on_finish and result.get("outcome") != "paused":
            try:
                send_command(driver, trace_path, "_auto_loop_operator.request_exit()", timeout=5.0)
            except Exception:
                pass
        driver.close()

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
            result["crash_summary"] = {
                "dump_count": collected.dump_count,
                "dump_files": collected.copied_dumps,
            }
            result["next_action"] = "analyze_crash_dump"

        result["phase_status"]["analyze"] = "done"

    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Messiah test loop orchestrator")
    parser.add_argument("--repo-root", type=Path, default=Path(os.environ.get("MESSIAH_REPO_ROOT", "E:/messiah_h74")))
    parser.add_argument("--scenario", choices=["aov_record", "nbs_playback"], required=True)
    parser.add_argument("--max-rounds", type=int, default=1)
    parser.add_argument("--do-build", type=str2bool, default=True)
    parser.add_argument("--build-script", type=Path, default=Path(r"C:/Users/zhangruojun/.codex/skills/messiah-ib-build-fix/scripts/invoke_ib_build.ps1"))
    parser.add_argument("--build-action", default="build")
    parser.add_argument("--build-configuration", default="Hybrid")
    parser.add_argument("--build-platform", default="x64")
    parser.add_argument("--launch-bat", default="")
    parser.add_argument(
        "--game-args",
        default="",
        help=(
            "Override game launch arguments while keeping launch-bat locked. "
            "When set, the runner generates a per-run launch .bat under artifacts and uses it to start the client."
        ),
    )
    parser.add_argument("--launch-settle-sec", type=int, default=12)
    parser.add_argument("--reuse-running-client", type=str2bool, default=False)
    parser.add_argument("--game-process-names", default="Game_x64h.exe,Game_x64r.exe")
    parser.add_argument(
        "--stop-point",
        choices=["after_connect", "after_operator_load", "after_click_start", "after_login", "after_scenario"],
        default="after_click_start",
    )
    parser.add_argument("--request-exit-on-finish", type=str2bool, default=False)
    parser.add_argument("--nbs-demo-path", default="")
    parser.add_argument("--server-profile", default="")
    parser.add_argument("--space-type", type=int, default=2)
    parser.add_argument("--spaceno", type=int, default=98121)
    parser.add_argument("--ship-config-id", type=int, default=9)
    parser.add_argument("--account", default="")
    parser.add_argument("--telnet-host", default="127.0.0.1")
    parser.add_argument("--telnet-port", type=int, default=9113)
    parser.add_argument("--timeout-build", type=int, default=7200)
    parser.add_argument("--timeout-connect", type=int, default=60)
    parser.add_argument("--connect-progress-sec", type=int, default=10)
    parser.add_argument("--timeout-login", type=int, default=300)
    parser.add_argument("--timeout-login-ui", type=int, default=10)
    parser.add_argument("--click-max-attempts", type=int, default=5)
    parser.add_argument("--click-interval-sec", type=float, default=0.5)
    parser.add_argument("--capture-on-playback-start", type=str2bool, default=False)
    parser.add_argument("--capture-delay-frames", type=int, default=20)
    parser.add_argument("--capture-target-frame", type=int, default=0)
    parser.add_argument("--capture-target-mode", choices=["target_window", "target_frame_single"], default="target_window")
    parser.add_argument("--capture-frame-mode", choices=["nbs", "actual"], default="nbs")
    parser.add_argument("--capture-window-size", type=int, default=5)
    parser.add_argument("--capture-pre-roll", type=int, default=2)
    parser.add_argument("--abort-on-trace-notice", type=str2bool, default=False)
    parser.add_argument("--abort-on-process-exit", type=str2bool, default=True)
    parser.add_argument("--timeout-scenario", type=int, default=1800)
    parser.add_argument("--require-approval", type=str2bool, default=True)
    parser.add_argument("--print-json", type=str2bool, default=False)
    parser.add_argument("--artifacts-root", default="")
    parser.add_argument("--log-dir", default="")
    parser.add_argument("--h74-operator-script", default="")
    parser.add_argument("--analyze-rdc", type=str2bool, default=False)
    parser.add_argument("--analyze-rdc-path", default="")
    parser.add_argument("--analyze-rdc-pass-keyword", default="WaterPass")
    parser.add_argument("--analyze-rdc-stage", choices=["pixel", "vertex", "compute"], default="pixel")
    parser.add_argument("--analyze-rdc-timeout", type=int, default=180)
    parser.add_argument("--analyze-rdc-qrenderdoc-path", default="")
    parser.add_argument("--analyze-rdc-target-event-id", type=int, default=0)
    parser.add_argument("--analyze-rdc-cb-value-mode", choices=["layered", "strict", "aggressive"], default="layered")
    parser.add_argument("--analyze-rdc-cb-top-n", type=int, default=20)
    parser.add_argument("--analyze-rdc-cb-neighbor-window", type=int, default=3)
    parser.add_argument("--analyze-rdc-cb-nonzero-only", type=str2bool, default=False)
    parser.add_argument(
        "--analyze-rdc-script",
        type=Path,
        default=(Path(__file__).resolve().parent / "renderdoc_analyze.py"),
    )
    parser.add_argument(
        "--auto-operator-script",
        type=Path,
        default=(Path(__file__).resolve().parent / "in_game" / "auto_loop_operator.py"),
    )
    return parser


def write_custom_launch_bat(run_dir: Path, repo_root: Path, game_args: str) -> Path:
    """
    Generate a per-run launch bat to avoid editing the locked project bat.
    We keep behavior roughly aligned with the project's locked bat (RenderDoc enable best-effort).
    """
    game_args = str(game_args or "").strip()
    if not game_args:
        raise ValueError("game_args must be non-empty")

    repo_root = repo_root.resolve()
    cooked_client_dir = repo_root / "cooked_client" / "Client"
    setup_hook_bat = cooked_client_dir / "shader_cache_hookers" / "setup_svn_hook.bat"
    mod_plugins_py = cooked_client_dir / "mod_engine_plugins.py"
    engine_bin_dir = repo_root / "Messiah" / "Engine" / "Binaries" / "Win64"
    game_exe = engine_bin_dir / "Game_x64h.exe"

    content = "\n".join(
        [
            "@echo off",
            "setlocal EnableExtensions",
            "",
            "REM Enable RenderDoc plugin (best-effort)",
            f'call "{setup_hook_bat}"',
            f'pushd "{repo_root / "Messiah"}"',
            f'python "{mod_plugins_py}" RenderDoc True',
            "popd",
            "",
            f'cd /d "{engine_bin_dir}"',
            "",
            f'start \"\" \"{game_exe}\" {game_args}',
            "",
            "endlocal",
            "",
        ]
    )

    out_path = run_dir / "launch_custom.bat"
    write_text(out_path, content)
    return out_path


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    args.repo_root = args.repo_root.resolve()
    args.artifacts_root = resolve_artifacts_root(args.repo_root, args.artifacts_root)
    args.log_dir = resolve_log_dir(args.repo_root, args.log_dir)
    args.h74_operator_script = resolve_h74_operator_script(args.repo_root, args.h74_operator_script)
    args.auto_operator_script = args.auto_operator_script.resolve()
    args.nbs_demo_path = resolve_nbs_demo_path(args.repo_root, args.nbs_demo_path)
    args.analyze_rdc_script = args.analyze_rdc_script.resolve()
    args.analyze_rdc_path = Path(args.analyze_rdc_path).resolve() if str(args.analyze_rdc_path).strip() else None
    args.analyze_rdc_qrenderdoc_path = (
        str(Path(args.analyze_rdc_qrenderdoc_path).resolve())
        if str(args.analyze_rdc_qrenderdoc_path).strip()
        else ""
    )
    args.analyze_rdc_cb_top_n = max(1, int(args.analyze_rdc_cb_top_n))
    args.analyze_rdc_cb_neighbor_window = max(0, int(args.analyze_rdc_cb_neighbor_window))
    args.analyze_rdc_target_event_id = max(0, int(args.analyze_rdc_target_event_id))
    args.game_process_names = [x.strip() for x in args.game_process_names.split(",") if x.strip()]
    args.click_max_attempts = max(1, int(args.click_max_attempts))
    args.click_interval_sec = max(0.0, float(args.click_interval_sec))
    args.capture_delay_frames = max(0, int(args.capture_delay_frames))
    args.capture_target_frame = max(0, int(args.capture_target_frame))
    args.capture_window_size = max(1, int(args.capture_window_size))
    args.capture_pre_roll = max(0, int(args.capture_pre_roll))
    if not args.game_process_names:
        args.game_process_names = ["Game_x64h.exe", "Game_x64r.exe"]

    locked_bat = resolve_locked_launch_bat(args.repo_root)
    if args.launch_bat:
        requested_bat = Path(args.launch_bat).resolve()
        if requested_bat != locked_bat:
            raise ValueError(f"launch-bat is locked to {locked_bat}, got {requested_bat}")
    args.launch_bat = locked_bat

    ensure_dir(args.artifacts_root)

    all_results: list[dict] = []
    for i in range(1, args.max_rounds + 1):
        result = run_round(args, i)
        run_dir = args.artifacts_root / result["run_id"]
        result_path = run_dir / "result.json"
        write_json(result_path, result)
        all_results.append(result)
        if result.get("outcome") in {"pass", "paused"}:
            print(
                "[ok] "
                f"run_id={result['run_id']} outcome={result['outcome']} stop_point={result.get('paused_at', args.stop_point)} "
                f"telnet={args.telnet_host}:{result.get('connected_telnet_port', 'n/a')}",
                flush=True,
            )
        else:
            brief = result.get("key_logs", [""])[0]
            print(f"[fail] run_id={result['run_id']} outcome={result.get('outcome')} reason={brief}", flush=True)
        print(f"result_path={result_path}", flush=True)

        if result.get("outcome") == "paused":
            break
        if result.get("outcome") != "pass":
            if args.require_approval:
                create_fix_plan(run_dir / "fix_plan.md", result)
                break
            break

    summary = {
        "created_at": datetime.now().isoformat(),
        "round_count": len(all_results),
        "results": all_results,
    }
    summary_path = args.artifacts_root / "latest_summary.json"
    write_json(summary_path, summary)

    print(f"summary_path={summary_path}", flush=True)
    if args.print_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
