from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark models through independent CLI processes.")
    parser.add_argument("--provider", default=None)
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--timeout-sec", type=float, default=60.0)
    parser.add_argument("--prompt", default="只输出 OK，不要解释。")
    parser.add_argument("--expected", default="OK")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workdir", type=Path, default=Path.cwd())
    return parser.parse_args()


def resolve_command() -> list[str]:
    executable = shutil.which("codex")
    if not executable:
        raise SystemExit("codex command was not found")
    if os.name == "nt" and executable.lower().endswith((".cmd", ".bat")):
        node = shutil.which("node")
        cli_script = Path(executable).parent / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
        if node and cli_script.is_file():
            return [node, str(cli_script)]
    if os.name == "nt" and executable.lower().endswith(".ps1"):
        powershell = shutil.which("powershell.exe")
        if not powershell:
            raise SystemExit("powershell.exe was not found")
        return [powershell, "-NoProfile", "-NonInteractive", "-File", executable]
    return [executable]


def terminate_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        process.kill()


def extract_final_message(stdout_text: str) -> str:
    final_message = ""
    for line in stdout_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        event = json.loads(stripped)
        item = event.get("item") or {}
        if event.get("type") == "item.completed" and item.get("type") == "agent_message":
            final_message = str(item.get("text", ""))
    return final_message


def percentile_nearest_rank(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, int((percentile * len(ordered) + 0.999999)))
    return ordered[min(rank - 1, len(ordered) - 1)]


def main() -> int:
    args = parse_args()
    if args.runs < 1:
        raise SystemExit("--runs must be positive")
    if args.timeout_sec <= 0:
        raise SystemExit("--timeout-sec must be positive")

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    runs_dir = output_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    command_prefix = resolve_command()
    results: list[dict[str, object]] = []

    for run_number in range(1, args.runs + 1):
        for model in args.models:
            model_dir = runs_dir / model.replace("/", "_")
            model_dir.mkdir(parents=True, exist_ok=True)
            stdout_path = model_dir / f"{run_number:02d}.stdout.jsonl"
            stderr_path = model_dir / f"{run_number:02d}.stderr.txt"
            command = command_prefix + [
                "exec",
                "--skip-git-repo-check",
                "--ephemeral",
                "--json",
                "-m",
                model,
            ]
            if args.provider:
                command.extend(["-c", f"model_provider={args.provider}"])
            command.append(args.prompt)
            started_at = time.perf_counter()
            process = subprocess.Popen(
                command,
                cwd=args.workdir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            timeout_state = {"timed_out": False}

            def timeout_process() -> None:
                if process.poll() is None:
                    timeout_state["timed_out"] = True
                    terminate_process_tree(process)

            timer = threading.Timer(args.timeout_sec, timeout_process)
            timer.start()
            stdout_text, stderr_text = process.communicate()
            timer.cancel()
            elapsed_sec = time.perf_counter() - started_at
            stdout_path.write_text(stdout_text, encoding="utf-8")
            stderr_path.write_text(stderr_text, encoding="utf-8")
            final_message = extract_final_message(stdout_text)
            exit_code = process.returncode
            result = {
                "provider": args.provider or "current-default",
                "model": model,
                "run": run_number,
                "elapsed_sec": round(elapsed_sec, 3),
                "exit_code": exit_code,
                "timed_out": timeout_state["timed_out"],
                "request_success": exit_code == 0 and not timeout_state["timed_out"],
                "strict_match": final_message.strip() == args.expected,
                "final_message": final_message,
                "stdout_path": str(stdout_path),
                "stderr_path": str(stderr_path),
            }
            results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)

    (output_dir / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with (output_dir / "results.csv").open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)

    summary: list[dict[str, object]] = []
    for model in args.models:
        model_results = [result for result in results if result["model"] == model]
        successful_times = [
            float(result["elapsed_sec"])
            for result in model_results
            if result["request_success"]
        ]
        summary.append(
            {
                "provider": args.provider or "current-default",
                "model": model,
                "runs": len(model_results),
                "successes": sum(bool(result["request_success"]) for result in model_results),
                "timeouts": sum(bool(result["timed_out"]) for result in model_results),
                "strict_matches": sum(bool(result["strict_match"]) for result in model_results),
                "mean_sec": round(statistics.mean(successful_times), 3) if successful_times else None,
                "p50_sec": round(statistics.median(successful_times), 3) if successful_times else None,
                "p95_sec": percentile_nearest_rank(successful_times, 0.95),
            }
        )
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"summary": summary}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
