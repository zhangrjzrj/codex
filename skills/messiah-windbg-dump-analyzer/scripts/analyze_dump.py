#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


DEFAULT_COMMANDS = [
    "!analyze -v",
    ".ecxr",
    "r",
    "kb",
    "~*kb",
    "lm",
    "q",
]


def _find_from_appx_package() -> Path | None:
    powershell_candidates = [
        ["powershell", "-NoProfile", "-Command", "(Get-AppxPackage Microsoft.WinDbg).InstallLocation"],
        ["pwsh", "-NoProfile", "-Command", "(Get-AppxPackage Microsoft.WinDbg).InstallLocation"],
    ]
    preferred_relative_paths = [
        Path("amd64") / "cdb.exe",
        Path("amd64") / "ntsd.exe",
        Path("amd64") / "kd.exe",
        Path("DbgX.Shell.exe"),
    ]
    for command in powershell_candidates:
        try:
            proc = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            )
        except (FileNotFoundError, subprocess.SubprocessError):
            continue
        install_location = (proc.stdout or "").strip()
        if not install_location:
            continue
        package_dir = Path(install_location)
        for relative_path in preferred_relative_paths:
            candidate = package_dir / relative_path
            if candidate.exists():
                return candidate.resolve()
    return None


def find_debugger(explicit_path: str) -> Path | None:
    if explicit_path:
        path = Path(explicit_path).expanduser().resolve()
        if path.exists():
            return path
        return None

    names = ["cdb.exe", "windbg.exe"]
    path_entries = os.environ.get("PATH", "").split(os.pathsep)
    for entry in path_entries:
        if not entry:
            continue
        for name in names:
            candidate = Path(entry) / name
            if candidate.exists():
                return candidate.resolve()

    kit_root = Path(r"C:\Program Files (x86)\Windows Kits")
    if kit_root.exists():
        for candidate in kit_root.rglob("cdb.exe"):
            return candidate.resolve()

    appx_debugger = _find_from_appx_package()
    if appx_debugger:
        return appx_debugger

    return None


def build_command(debugger: Path, dump_path: Path, symbol_path: str, commands: list[str]) -> list[str]:
    command_text = "; ".join(commands)
    cmd = [str(debugger), "-z", str(dump_path), "-c", command_text]
    if symbol_path.strip():
        cmd.extend(["-y", symbol_path.strip()])
    return cmd


def extract_summary(text: str) -> dict:
    summary: dict[str, object] = {}

    patterns = {
        "exception_code": r"ExceptionCode:\s+([^\s]+)",
        "exception_address": r"ExceptionAddress:\s+([^\s]+)",
        "process_name": r"PROCESS_NAME:\s+([^\r\n]+)",
        "faulting_thread": r"FAULTING_THREAD:\s+([^\r\n]+)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            summary[key] = match.group(1).strip()

    stack_lines = []
    capture = False
    for line in text.splitlines():
        if "STACK_TEXT:" in line:
            capture = True
            continue
        if capture:
            if not line.strip():
                if stack_lines:
                    break
                continue
            stack_lines.append(line.rstrip())
            if len(stack_lines) >= 12:
                break
    summary["stack_preview"] = stack_lines

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Silent WinDbg/cdb dump analyzer")
    parser.add_argument("--dump-path", required=True)
    parser.add_argument("--debugger-path", default="")
    parser.add_argument("--symbol-path", default="")
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--commands", nargs="*", default=DEFAULT_COMMANDS)
    args = parser.parse_args()

    dump_path = Path(args.dump_path).expanduser().resolve()
    if not dump_path.exists():
        print(json.dumps({"ok": False, "error": f"dump_not_found:{dump_path}"}, ensure_ascii=False))
        return 2

    debugger = find_debugger(args.debugger_path)
    if not debugger:
        print(json.dumps({"ok": False, "error": "debugger_not_found", "hint": "install cdb.exe or WinDbg"}, ensure_ascii=False))
        return 3

    out_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else dump_path.with_suffix("")
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = build_command(debugger, dump_path, args.symbol_path, args.commands)
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")

    stdout_path = out_dir / "debugger_stdout.txt"
    stderr_path = out_dir / "debugger_stderr.txt"
    summary_path = out_dir / "summary.json"

    stdout_path.write_text(proc.stdout or "", encoding="utf-8")
    stderr_path.write_text(proc.stderr or "", encoding="utf-8")

    summary = {
        "ok": proc.returncode == 0,
        "return_code": proc.returncode,
        "dump_path": str(dump_path),
        "debugger_path": str(debugger),
        "symbol_path": str(args.symbol_path),
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
    }
    summary.update(extract_summary(proc.stdout or ""))
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
