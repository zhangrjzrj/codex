#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import string
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


SKILL_DIR = Path(__file__).resolve().parents[1]
TMP_ROOT = Path.home() / ".codex" / "tmp" / "messiah-tracy-analyzer"
TOOL_VERSIONS = ["0.13.0", "0.12.2", "0.11.1"]
WINDOWS_ZIP_URL = "https://github.com/wolfpld/tracy/releases/download/v{version}/windows-{version}.zip"
LEGACY_CSVEXPORT_CANDIDATES = [
    Path(r"C:\Users\zhangruojun\.codex\tmp\Tracy-0.8.2\csvexport.exe"),
    Path(r"F:\messiah_h74\Messiah\Engine\Tools\tracy\csvexport.exe"),
]
LOCAL_PROFILER_CANDIDATES = [
    Path(r"C:\Users\zhangruojun\Documents\我的POPO\Tracy.exe"),
]


@dataclass
class ExportAttempt:
    version: str
    exit_code: int | None
    stdout_path: Path
    stderr_path: Path
    stats_path: Path
    events_path: Path | None
    status: str
    message: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze a Tracy .tracy capture and summarize likely stalls.")
    parser.add_argument("--trace-path", required=True, help="Path to the input .tracy file")
    parser.add_argument("--output-dir", default="", help="Directory for generated artifacts")
    return parser.parse_args()


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def is_ascii_path(path: Path) -> bool:
    return all(ord(ch) < 128 for ch in str(path))


def sanitize_name(name: str) -> str:
    allowed = string.ascii_letters + string.digits + "._-"
    result = "".join(ch if ch in allowed else "_" for ch in name)
    result = re.sub(r"_+", "_", result).strip("._")
    return result or "trace"


def prepare_trace_path(trace_path: Path, workspace: Path) -> Path:
    if is_ascii_path(trace_path):
        return trace_path
    trace_copy = workspace / f"{sanitize_name(trace_path.stem)}.tracy"
    shutil.copy2(trace_path, trace_copy)
    return trace_copy


def run(cmd: list[str], stdout_path: Path, stderr_path: Path, timeout: int) -> int | None:
    with stdout_path.open("w", encoding="utf-8", newline="") as stdout_f, stderr_path.open("w", encoding="utf-8", newline="") as stderr_f:
        try:
            proc = subprocess.run(cmd, stdout=stdout_f, stderr=stderr_f, timeout=timeout, check=False)
            return proc.returncode
        except subprocess.TimeoutExpired:
            stderr_f.write(f"TIMEOUT after {timeout}s\n")
            return None


def ensure_tracy_tools(version: str) -> Path:
    target_dir = TMP_ROOT / f"tracy-windows-{version}"
    csvexport = target_dir / "tracy-csvexport.exe"
    if csvexport.exists():
        return target_dir

    ensure_dir(TMP_ROOT)
    zip_path = TMP_ROOT / f"tracy-windows-{version}.zip"
    tmp_zip_path = TMP_ROOT / f"tracy-windows-{version}.{os.getpid()}.zip"
    url = WINDOWS_ZIP_URL.format(version=version)
    if not zip_path.exists():
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri '{url}' -OutFile '{tmp_zip_path}'; Move-Item -LiteralPath '{tmp_zip_path}' -Destination '{zip_path}' -Force",
            ],
            check=True,
        )
    if target_dir.exists():
        shutil.rmtree(target_dir)
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            f"Expand-Archive -Path '{zip_path}' -DestinationPath '{target_dir}' -Force",
        ],
        check=True,
    )
    return target_dir


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def try_read_csv_text(path: Path) -> str:
    if not path.exists():
        return ""
    for encoding in ("utf-8-sig", "utf-16", "utf-16-le", "utf-16-be"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def run_capture_stdout(cmd: list[str], stdout_path: Path, stderr_path: Path, timeout: int, output_encoding: str = "utf-8") -> int | None:
    with stdout_path.open("w", encoding=output_encoding, newline="") as stdout_f, stderr_path.open("w", encoding="utf-8", newline="") as stderr_f:
        try:
            proc = subprocess.run(cmd, stdout=stdout_f, stderr=stderr_f, timeout=timeout, check=False)
            return proc.returncode
        except subprocess.TimeoutExpired:
            stderr_f.write(f"TIMEOUT after {timeout}s\n")
            return None


def attempt_csv_export(trace_path: Path, workspace: Path) -> list[ExportAttempt]:
    attempts: list[ExportAttempt] = []
    for candidate in LEGACY_CSVEXPORT_CANDIDATES:
        if not candidate.exists():
            continue

        stats_path = workspace / "stats_0.8.2.csv"
        stats_stdout = stats_path
        stats_stderr = workspace / "stats_0.8.2.stderr.txt"
        stats_exit = run_capture_stdout([str(candidate), str(trace_path)], stats_path, stats_stderr, timeout=180, output_encoding="utf-16")
        stats_text = read_text(stats_stderr)
        stats_ok = stats_exit in (0, 1) and stats_path.exists() and stats_path.stat().st_size > 0

        if stats_ok:
            attempts.append(
                ExportAttempt(
                    version="0.8.2",
                    exit_code=stats_exit,
                    stdout_path=stats_stdout,
                    stderr_path=stats_stderr,
                    stats_path=stats_path,
                    events_path=None,
                    status="ok",
                    message=f"csvexport succeeded via {candidate}",
                )
            )
            return attempts

        combined = stats_text.strip()
        attempts.append(
            ExportAttempt(
                version="0.8.2",
                exit_code=stats_exit,
                stdout_path=stats_stdout,
                stderr_path=stats_stderr,
                stats_path=stats_path,
                events_path=None,
                status="failed",
                message=combined.splitlines()[0][:200] if combined else "empty-output",
            )
        )

    for version in TOOL_VERSIONS:
        tools_dir = ensure_tracy_tools(version)
        csvexport = tools_dir / "tracy-csvexport.exe"

        stats_path = workspace / f"stats_{version}.csv"
        events_path = workspace / f"events_{version}.csv"
        stats_stdout = workspace / f"stats_{version}.stdout.txt"
        stats_stderr = workspace / f"stats_{version}.stderr.txt"
        events_stdout = workspace / f"events_{version}.stdout.txt"
        events_stderr = workspace / f"events_{version}.stderr.txt"

        stats_exit = run([str(csvexport), str(trace_path)], stats_path, stats_stderr, timeout=180)
        # Some Tracy tools print diagnostics to stderr only; keep stdout evidence even if empty.
        if stats_stdout.exists():
            stats_stdout.unlink()
        events_exit = run([str(csvexport), "-u", "-e", str(trace_path)], events_path, events_stderr, timeout=180)
        if events_stdout.exists():
            events_stdout.unlink()

        stats_text = read_text(stats_stderr)
        events_text = read_text(events_stderr)
        stats_ok = stats_exit in (0, 1) and stats_path.exists() and stats_path.stat().st_size > 0
        events_ok = events_exit in (0, 1) and events_path.exists() and events_path.stat().st_size > 0

        if stats_ok:
            attempts.append(
                ExportAttempt(
                    version=version,
                    exit_code=stats_exit,
                    stdout_path=stats_stdout,
                    stderr_path=stats_stderr,
                    stats_path=stats_path,
                    events_path=events_path if events_ok else Path(),
                    status="ok",
                    message="csvexport succeeded",
                )
            )
            break

        message_parts = []
        combined = (stats_text + "\n" + events_text).strip()
        if "legacy version" in combined.lower():
            message_parts.append("legacy-version")
        crash_codes = {3221226505, -1073740791}
        if stats_exit is None or events_exit is None:
            message_parts.append("timeout")
        elif any(code in crash_codes for code in [stats_exit, events_exit]):
            message_parts.append("native-crash")
        elif any(code and code < 0 for code in [stats_exit, events_exit]):
            message_parts.append("native-crash")
        elif combined:
            message_parts.append(combined.splitlines()[0][:200])
        else:
            message_parts.append("empty-output")

        attempts.append(
            ExportAttempt(
                version=version,
                exit_code=stats_exit,
                stdout_path=stats_stdout,
                stderr_path=stats_stderr,
                stats_path=stats_path,
                events_path=events_path,
                status="failed",
                message="; ".join(message_parts),
            )
        )
    return attempts


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    text = try_read_csv_text(path)
    if not text.strip():
        return []
    return list(csv.DictReader(text.splitlines()))


def to_int(value: str | None) -> int:
    if value is None or value == "":
        return 0
    try:
        return int(float(value))
    except ValueError:
        return 0


def to_float(value: str | None) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def ns_to_ms(value: int | float) -> float:
    return round(float(value) / 1_000_000.0, 3)


def summarize_hotspots(stats_rows: Iterable[dict[str, str]], events_rows: Iterable[dict[str, str]]) -> dict:
    stats_rows = list(stats_rows)
    events_rows = list(events_rows)
    top_total = sorted(stats_rows, key=lambda row: to_int(row.get("total_ns")), reverse=True)[:10]
    top_self = sorted(stats_rows, key=lambda row: to_int(row.get("mean_ns")) * max(to_int(row.get("counts")), 1), reverse=True)[:10]
    top_spikes = sorted(stats_rows, key=lambda row: to_int(row.get("max_ns")), reverse=True)[:10]
    top_events = sorted(events_rows, key=lambda row: to_int(row.get("exec_time_ns")), reverse=True)[:20]

    bottleneck = "unknown"
    if top_spikes:
        names = " ".join((row.get("name") or "").lower() for row in top_spikes[:5])
        if any(token in names for token in ["wait", "lock", "sync", "semaphore", "mutex"]):
            bottleneck = "blocking-or-lock-contention"
        elif any(token in names for token in ["file", "read", "seek", "io"]):
            bottleneck = "io-or-streaming"
        elif any(token in names for token in ["render", "pass", "cocosui", "script"]):
            bottleneck = "cpu-heavy-work-on-frame-critical-path"

    def shape(row: dict[str, str]) -> dict:
        return {
            "name": row.get("name", ""),
            "src_file": row.get("src_file", ""),
            "src_line": to_int(row.get("src_line")),
            "count": to_int(row.get("counts")),
            "total_ms": ns_to_ms(to_int(row.get("total_ns"))),
            "mean_ms": ns_to_ms(to_int(row.get("mean_ns"))),
            "max_ms": ns_to_ms(to_int(row.get("max_ns"))),
            "std_ms": ns_to_ms(to_float(row.get("std_ns"))),
            "total_percent": round(to_float(row.get("total_perc")) * 100.0, 3),
        }

    def event_shape(row: dict[str, str]) -> dict:
        return {
            "name": row.get("name", ""),
            "thread": row.get("thread", ""),
            "start_ms": ns_to_ms(to_int(row.get("ns_since_start"))),
            "exec_ms": ns_to_ms(to_int(row.get("exec_time_ns"))),
            "src_file": row.get("src_file", ""),
            "src_line": to_int(row.get("src_line")),
        }

    return {
        "likely_bottleneck_type": bottleneck,
        "top_hotspots": [shape(row) for row in top_total[:5]],
        "top_spikes": [shape(row) for row in top_spikes[:5]],
        "top_events": [event_shape(row) for row in top_events[:10]],
        "supporting_totals": [shape(row) for row in top_self[:5]],
    }


def main() -> int:
    args = parse_args()
    trace_path = Path(args.trace_path).expanduser().resolve()
    if not trace_path.exists():
        print(f"Trace file not found: {trace_path}", file=sys.stderr)
        return 2

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else (TMP_ROOT / f"report_{sanitize_name(trace_path.stem)}_{timestamp}")
    workspace = ensure_dir(output_dir)
    run_log: list[str] = []
    run_log.append(f"trace={trace_path}")
    run_log.append(f"output_dir={workspace}")

    prepared_trace = prepare_trace_path(trace_path, workspace)
    if prepared_trace != trace_path:
        run_log.append(f"copied_trace_for_ascii_path={prepared_trace}")

    attempts = attempt_csv_export(prepared_trace, workspace)
    summary: dict = {
        "trace_path": str(trace_path),
        "prepared_trace_path": str(prepared_trace),
        "output_dir": str(workspace),
        "analysis_mode": "",
        "likely_bottleneck_type": "unknown",
        "top_hotspots": [],
        "top_spikes": [],
        "top_events": [],
        "notes": [],
        "attempts": [
            {
                "version": a.version,
                "status": a.status,
                "exit_code": a.exit_code,
                "message": a.message,
                "stats_path": str(a.stats_path) if a.stats_path else "",
                "events_path": str(a.events_path) if a.events_path else "",
            }
            for a in attempts
        ],
    }

    success = next((a for a in attempts if a.status == "ok"), None)
    if success is not None:
        stats_rows = load_csv_rows(success.stats_path)
        events_rows = load_csv_rows(success.events_path) if success.events_path and success.events_path.is_file() else []
        hotspot_summary = summarize_hotspots(stats_rows, events_rows)
        summary.update(hotspot_summary)
        summary["analysis_mode"] = "csvexport"
        summary["notes"].append(f"Hotspot summary generated from official tracy-csvexport {success.version}.")
        shutil.copy2(success.stats_path, workspace / "stats.csv")
        if success.events_path and success.events_path.exists() and success.events_path.stat().st_size > 0:
            shutil.copy2(success.events_path, workspace / "events.csv")
    else:
        summary["analysis_mode"] = "error"
        if any("legacy-version" in a.message for a in attempts):
            summary["notes"].append("CSV export failed because the trace is in a legacy Tracy format.")
        elif any("native-crash" in a.message for a in attempts):
            summary["notes"].append("CSV export crashed on all tested Tracy versions, which usually means the trace is too old or unsupported by current exporters.")
        else:
            summary["notes"].append("CSV export did not produce usable output.")
        summary["notes"].append("Tracy analyzer skill no longer falls back to GUI screenshots. Please fix the skill's direct-export path or add explicit support for this trace format.")

    write_text(workspace / "run.log", "\n".join(run_log) + "\n")
    write_json(workspace / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if success is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
