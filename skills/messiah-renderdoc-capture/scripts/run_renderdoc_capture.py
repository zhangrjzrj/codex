#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


def str2bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def detect_test_loop_script() -> Path:
    skill_dir = Path(__file__).resolve().parents[1]
    script = skill_dir.parent / "messiah-test-loop" / "scripts" / "run_loop.py"
    if not script.exists():
        raise FileNotFoundError(f"test loop script missing: {script}")
    return script.resolve()


def detect_candidate_rdc_dirs(repo_root: Path) -> list[Path]:
    candidates = [
        repo_root / "artifacts",
        repo_root / "Messiah",
        repo_root / "Messiah" / "LocalData",
        repo_root / "Messiah" / "Engine" / "Binaries" / "Win64",
        Path.home() / "Documents" / "RenderDoc",
        Path.home() / "AppData" / "Local" / "Temp",
    ]
    out: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        try:
            resolved = path.resolve()
        except Exception:
            resolved = path
        key = str(resolved).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(resolved)
    return out


def list_recent_rdc_files(search_roots: list[Path], since_ts: float) -> list[Path]:
    hits: list[Path] = []
    for root in search_roots:
        if not root.exists():
            continue
        try:
            for path in root.rglob("*.rdc"):
                try:
                    if path.stat().st_mtime >= since_ts:
                        hits.append(path.resolve())
                except OSError:
                    continue
        except OSError:
            continue
    unique = sorted({str(p): p for p in hits}.values(), key=lambda p: p.stat().st_mtime, reverse=True)
    return unique


def parse_result_path(stdout: str) -> Path | None:
    for line in reversed((stdout or "").splitlines()):
        line = line.strip()
        if line.startswith("result_path="):
            value = line.split("=", 1)[1].strip()
            if value:
                return Path(value).resolve()
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Messiah RenderDoc auto-capture wrapper")
    parser.add_argument("--repo-root", type=Path, default=Path("F:/messiah_h74"))
    parser.add_argument("--demo-path", required=True)
    parser.add_argument("--delay-frames", type=int, default=20)
    parser.add_argument("--target-frame", type=int, default=0)
    parser.add_argument("--target-mode", choices=["target_window", "target_frame_single"], default="target_window")
    parser.add_argument("--frame-mode", choices=["nbs", "actual"], default="nbs")
    parser.add_argument("--window-size", type=int, default=5)
    parser.add_argument("--pre-roll", type=int, default=2)
    parser.add_argument("--reuse-running-client", type=str2bool, default=False)
    parser.add_argument("--request-exit-on-finish", type=str2bool, default=False)
    parser.add_argument("--do-build", type=str2bool, default=False)
    parser.add_argument("--require-approval", type=str2bool, default=False)
    parser.add_argument("--stop-point", choices=["after_connect", "after_operator_load", "after_click_start", "after_login", "after_scenario"], default="after_scenario")
    parser.add_argument("--timeout-scenario", type=int, default=1800)
    parser.add_argument("--analyze-rdc", type=str2bool, default=False)
    parser.add_argument("--analyze-rdc-path", default="")
    parser.add_argument("--analyze-rdc-pass-keyword", default="WaterPass")
    parser.add_argument("--analyze-rdc-stage", choices=["pixel", "vertex", "compute"], default="pixel")
    parser.add_argument("--analyze-rdc-timeout", type=int, default=180)
    parser.add_argument("--analyze-rdc-qrenderdoc-path", default="")
    parser.add_argument("--print-json", type=str2bool, default=True)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    demo_path = Path(args.demo_path).resolve()
    run_loop_script = detect_test_loop_script()
    started_at = time.time() - 3.0

    cmd = [
        sys.executable,
        str(run_loop_script),
        "--repo-root",
        str(repo_root),
        "--scenario",
        "nbs_playback",
        "--max-rounds",
        "1",
        "--do-build",
        str(bool(args.do_build)).lower(),
        "--require-approval",
        str(bool(args.require_approval)).lower(),
        "--stop-point",
        str(args.stop_point),
        "--nbs-demo-path",
        str(demo_path),
        "--capture-on-playback-start",
        "true",
        "--reuse-running-client",
        str(bool(args.reuse_running_client)).lower(),
        "--request-exit-on-finish",
        str(bool(args.request_exit_on_finish)).lower(),
        "--timeout-scenario",
        str(max(1, int(args.timeout_scenario))),
        "--print-json",
        "false",
    ]

    if int(args.target_frame) > 0:
        cmd.extend(
            [
                "--capture-target-frame",
                str(max(0, int(args.target_frame))),
                "--capture-target-mode",
                str(args.target_mode),
                "--capture-frame-mode",
                str(args.frame_mode),
                "--capture-window-size",
                str(max(1, int(args.window_size))),
                "--capture-pre-roll",
                str(max(0, int(args.pre_roll))),
            ]
        )
    else:
        cmd.extend(["--capture-delay-frames", str(max(0, int(args.delay_frames)))])

    if args.analyze_rdc:
        cmd.extend(
            [
                "--analyze-rdc",
                "true",
                "--analyze-rdc-pass-keyword",
                str(args.analyze_rdc_pass_keyword),
                "--analyze-rdc-stage",
                str(args.analyze_rdc_stage),
                "--analyze-rdc-timeout",
                str(max(1, int(args.analyze_rdc_timeout))),
            ]
        )
        if str(args.analyze_rdc_path).strip():
            cmd.extend(["--analyze-rdc-path", str(Path(args.analyze_rdc_path).resolve())])
        if str(args.analyze_rdc_qrenderdoc_path).strip():
            cmd.extend(["--analyze-rdc-qrenderdoc-path", str(Path(args.analyze_rdc_qrenderdoc_path).resolve())])

    proc = subprocess.run(
        cmd,
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )

    if proc.stdout:
        print(proc.stdout, end="" if proc.stdout.endswith("\n") else "\n")
    if proc.stderr:
        print(proc.stderr, file=sys.stderr, end="" if proc.stderr.endswith("\n") else "\n")

    result_path = parse_result_path(proc.stdout or "")
    result_payload: dict = {}
    if result_path and result_path.exists():
        result_payload = json.loads(result_path.read_text(encoding="utf-8"))

    recent_rdc = list_recent_rdc_files(detect_candidate_rdc_dirs(repo_root), started_at)
    summary = {
        "ok": proc.returncode == 0 and bool(result_payload),
        "repo_root": str(repo_root),
        "demo_path": str(demo_path),
        "mode": "target_frame" if int(args.target_frame) > 0 else "playing_delay_frames",
        "result_path": str(result_path) if result_path else "",
        "outcome": result_payload.get("outcome", ""),
        "renderdoc_capture_requested": bool(result_payload.get("renderdoc_capture_requested", False)),
        "renderdoc_capture_mode": str(result_payload.get("renderdoc_capture_mode", "")),
        "renderdoc_capture_trigger_frame": int(result_payload.get("renderdoc_capture_trigger_frame", 0) or 0),
        "renderdoc_capture_triggered_at_frame": int(result_payload.get("renderdoc_capture_triggered_at_frame", 0) or 0),
        "renderdoc_capture_api": str(result_payload.get("renderdoc_capture_api", "")),
        "renderdoc_capture_error": str(result_payload.get("renderdoc_capture_error", "")),
        "rdc_candidates": [str(p) for p in recent_rdc[:10]],
    }
    if args.print_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
