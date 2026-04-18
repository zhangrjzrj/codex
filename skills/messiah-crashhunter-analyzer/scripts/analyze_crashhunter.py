#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional


def run(cmd: list[str], *, capture: bool = True, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=check,
    )


def adb_prefix(device: Optional[str]) -> list[str]:
    return ["adb"] + (["-s", device] if device else [])


def adb_shell(device: Optional[str], shell_cmd: str) -> str:
    cp = run(adb_prefix(device) + ["shell", shell_cmd])
    return cp.stdout


def adb_exec_out(device: Optional[str], shell_cmd: str) -> bytes:
    cp = subprocess.run(
        adb_prefix(device) + ["exec-out"] + shell_cmd.split(" "),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return cp.stdout


def safe_mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def pick_latest_folder(names: list[str]) -> Optional[str]:
    if not names:
        return None
    return sorted(names)[-1]


def parse_ls_lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


@dataclass
class AssertInfo:
    expr: str | None = None
    file: str | None = None
    line: int | None = None


@dataclass
class ScriptContext:
    module: str | None = None
    function: str | None = None
    line: int | None = None


@dataclass
class CrashSummary:
    package: str
    device: str | None
    crash_dir: str | None
    pulled_at: str
    signal: str | None = None
    assert_info: AssertInfo | None = None
    script_context: ScriptContext | None = None
    key_log_lines: list[str] | None = None
    artifacts: dict[str, str] | None = None
    stackwalk_ran: bool = False
    stackwalk_output: str | None = None
    stackwalk_path: str | None = None
    symbols_dir: str | None = None


ASSERT_EXPR_RE = re.compile(r"^\[Expr\]:\s*(.*)$")
ASSERT_FILE_RE = re.compile(r"^\[File\]:\s*(.*)$")
ASSERT_LINE_RE = re.compile(r"^\[Line\]:\s*(\d+)\s*$")


def parse_game_assert(text: str) -> AssertInfo:
    info = AssertInfo()
    for ln in text.splitlines():
        m = ASSERT_EXPR_RE.match(ln.strip())
        if m:
            info.expr = m.group(1).strip()
        m = ASSERT_FILE_RE.match(ln.strip())
        if m:
            info.file = m.group(1).strip()
        m = ASSERT_LINE_RE.match(ln.strip())
        if m:
            info.line = int(m.group(1))
    return info


SCRIPT_CTX_RE = {
    "module": re.compile(r"^Module:\\s*(.*)\\s*$"),
    "function": re.compile(r"^Function:\\s*(.*)\\s*$"),
    "line": re.compile(r"^Line:\\s*(\\d+)\\s*$"),
}


def parse_game_stack(text: str) -> ScriptContext:
    ctx = ScriptContext()
    for ln in text.splitlines():
        for k, rx in SCRIPT_CTX_RE.items():
            m = rx.match(ln.strip())
            if not m:
                continue
            if k == "line":
                ctx.line = int(m.group(1))
            elif k == "module":
                ctx.module = m.group(1).strip()
            elif k == "function":
                ctx.function = m.group(1).strip()
    return ctx


def extract_key_log_lines(logcat_text: str, patterns: Iterable[str], limit: int = 80) -> list[str]:
    rx = re.compile("|".join(f"(?:{p})" for p in patterns), re.IGNORECASE)
    hits: list[str] = []
    for ln in logcat_text.splitlines():
        if rx.search(ln):
            hits.append(ln)
    return hits[-limit:]


def find_stackwalk_explicit(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    p = Path(path)
    if p.exists():
        return str(p)
    return None


def find_stackwalk_default() -> Optional[str]:
    for exe in ("minidump_stackwalk.exe", "minidump_stackwalk"):
        found = shutil.which(exe)
        if found:
            return found

    msys2_candidates = [
        r"C:\\msys64\\mingw64\\bin\\minidump_stackwalk.exe",
        r"C:\\Program Files\\MSYS2\\mingw64\\bin\\minidump_stackwalk.exe",
    ]
    for c in msys2_candidates:
        if Path(c).exists():
            return c

    return None


def ensure_symbols_dir(symbols: Optional[str], out_dir: Path) -> Optional[str]:
    if not symbols:
        return None
    p = Path(symbols)
    if not p.exists():
        return None

    if p.is_dir():
        return str(p)

    if p.is_file() and p.suffix.lower() == ".zip" and zipfile.is_zipfile(p):
        dst = out_dir / "symbols_extracted"
        safe_mkdir(dst)
        with zipfile.ZipFile(p, "r") as zf:
            zf.extractall(dst)
        return str(dst)

    return None


def try_stackwalk(stackwalk: Optional[str], symbols: Optional[str], dmp: Path, out_txt: Path) -> tuple[bool, Optional[str]]:
    if not stackwalk:
        return False, None
    stackwalk_path = Path(stackwalk)
    if not stackwalk_path.exists():
        return False, None

    cmd = [str(stackwalk_path), str(dmp)]
    if symbols:
        symbols_path = Path(symbols)
        if not symbols_path.exists():
            return False, None
        cmd.append(str(symbols_path))
    cp = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out_txt.write_text(cp.stdout, encoding="utf-8", errors="replace")
    return True, str(out_txt)


def find_llvm_addr2line() -> Optional[str]:
    # 1) PATH
    for exe in ("llvm-addr2line.exe", "llvm-addr2line"):
        found = shutil.which(exe)
        if found:
            return found

    # 2) ANDROID_SDK_ROOT/ndk/<ver>/toolchains/llvm/prebuilt/windows-x86_64/bin/llvm-addr2line(.exe)
    sdk_root = os.environ.get("ANDROID_SDK_ROOT") or os.environ.get("ANDROID_HOME")
    if not sdk_root:
        # Default Android Studio path
        sdk_root = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Android", "Sdk")

    ndk_root = Path(sdk_root) / "ndk"
    if ndk_root.exists():
        # Prefer the latest version folder
        candidates = sorted([p for p in ndk_root.iterdir() if p.is_dir()], reverse=True)
        for ndk_ver in candidates[:6]:
            p = ndk_ver / "toolchains" / "llvm" / "prebuilt" / "windows-x86_64" / "bin" / "llvm-addr2line.exe"
            if p.exists():
                return str(p)

    return None


def find_local_unstripped_libgame() -> Optional[str]:
    # Prefer the "obj/local" output from Android Studio/NDK build (more likely to contain debug info)
    candidates = [
        r"F:\messiah_h74_latest_mobile\Messiah\Engine\Intermediate\AndroidStudio\Game\app\src\main\obj\local\arm64-v8a\libGame.so",
        r"F:\messiah_h74_latest_mobile\Messiah\Engine\Intermediate\AndroidStudio\Game\app\src\main\obj\local\armeabi-v7a\libGame.so",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return None


def symbolize_stackwalk_with_addr2line(
    stackwalk_txt: Path, out_txt: Path, *, addr2line: str, elf: str, limit: int = 40
) -> bool:
    text = stackwalk_txt.read_text(encoding="utf-8", errors="replace")
    # Find the first "Thread X (crashed)" block and collect libGame.so offsets.
    m = re.search(r"^Thread\s+\d+\s+\(crashed\)\s*$", text, flags=re.MULTILINE)
    if not m:
        return False

    start = m.start()
    block = text[start : start + 20000]  # enough for top frames
    offsets = re.findall(r"libGame\.so\s+\+\s+(0x[0-9a-fA-F]+)", block)
    offsets = offsets[:limit]
    if not offsets:
        return False

    cp = subprocess.run(
        [addr2line, "-Cfip", "-e", elf] + offsets,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out_txt.write_text(cp.stdout, encoding="utf-8", errors="replace")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="Pull & analyze Messiah Android CrashHunter artifacts")
    ap.add_argument("--device", default=None, help="adb device serial (optional)")
    ap.add_argument("--package", default="com.netease.messiah", help="Android package name")
    ap.add_argument("--out", default=None, help="Output directory (default: ./crashhunter_pull_<timestamp>)")
    ap.add_argument("--stackwalk", default=None, help="Path to minidump_stackwalk executable (optional)")
    ap.add_argument("--symbols", default=None, help="Symbols directory or Sym.zip for stackwalk (optional)")
    ap.add_argument("--elf", default=None, help="Path to unstripped libGame.so (optional, for addr2line fallback)")
    args = ap.parse_args()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out) if args.out else Path.cwd() / f"crashhunter_pull_{ts}"
    safe_mkdir(out_dir)

    crash_root = "files/uniTrace/crashhunter"
    ls_text = adb_shell(args.device, f"run-as {args.package} ls -1 {crash_root} 2>/dev/null")
    names = parse_ls_lines(ls_text)

    native_dirs = [n for n in names if n.startswith("NATIVE_DUMP_")]
    java_dirs = [n for n in names if n.startswith("JAVA_DUMP_")]
    chosen = pick_latest_folder(native_dirs) or pick_latest_folder(java_dirs)

    artifacts: dict[str, str] = {}

    # Pull stable top-level files
    for top in ("game_assert.other", "game_stack.other"):
        try:
            data = adb_exec_out(args.device, f"run-as {args.package} cat {crash_root}/{top}")
            (out_dir / top).write_bytes(data)
            artifacts[top] = str(out_dir / top)
        except Exception:
            continue

    crash_dir = None
    if chosen:
        crash_dir = f"{crash_root}/{chosen}"

        # Some builds store these under the dump folder instead of crash_root.
        for fn in ("game_assert.other", "game_stack.other"):
            if fn in artifacts:
                continue
            try:
                data = adb_exec_out(args.device, f"run-as {args.package} cat {crash_dir}/{fn}")
                (out_dir / fn).write_bytes(data)
                artifacts[fn] = str(out_dir / fn)
            except Exception:
                continue

        for fn in (
            "logcat.log",
            "crashhunter.di",
            "native_crash.mark",
            "process_life_file.txt",
            "request_param.unitrace_param",
        ):
            try:
                data = adb_exec_out(args.device, f"run-as {args.package} cat {crash_dir}/{fn}")
                (out_dir / fn).write_bytes(data)
                artifacts[fn] = str(out_dir / fn)
            except Exception:
                continue

        # Pull minidump(s)
        try:
            ls_dump = adb_shell(args.device, f"run-as {args.package} ls -1 {crash_dir} 2>/dev/null")
            dump_names = [n for n in parse_ls_lines(ls_dump) if n.endswith(".dmp")]
            for dn in dump_names:
                data = adb_exec_out(args.device, f"run-as {args.package} cat {crash_dir}/{dn}")
                out_path = out_dir / dn
                out_path.write_bytes(data)
                artifacts[dn] = str(out_path)
        except Exception:
            pass

    assert_info = None
    if (out_dir / "game_assert.other").exists():
        assert_info = parse_game_assert((out_dir / "game_assert.other").read_text(encoding="utf-8", errors="replace"))

    script_ctx = None
    if (out_dir / "game_stack.other").exists():
        script_ctx = parse_game_stack((out_dir / "game_stack.other").read_text(encoding="utf-8", errors="replace"))

    logcat_txt = ""
    if (out_dir / "logcat.log").exists():
        logcat_txt = (out_dir / "logcat.log").read_text(encoding="utf-8", errors="replace")

    key_lines = extract_key_log_lines(
        logcat_txt,
        patterns=[
            r"AndroidCrashHandler \\[nativeSignalCallback\\].*signal=",
            r"doingCrashSignal",
            r"\\[Fail\\]:",
            r"\\[Expr\\]:",
            r"\\[File\\]:",
            r"\\[Line\\]:",
            r"Fail to open file",
            r"missing Patch\\.mpkinfo",
            r"Init\\.pck not found",
            r"Fatal signal",
            r"SIGSEGV|SIGTRAP|SIGABRT",
        ],
        limit=120,
    )

    signal = None
    for ln in reversed(key_lines):
        m = re.search(r"signal=(\\d+)", ln)
        if m:
            signal = m.group(1)
            break

    stackwalk_ran = False
    stackwalk_out = None
    stackwalk_path = find_stackwalk_explicit(args.stackwalk) or find_stackwalk_default()
    symbols_dir = ensure_symbols_dir(args.symbols, out_dir)

    addr2line_path = find_llvm_addr2line()
    elf_path = args.elf or find_local_unstripped_libgame()
    addr2line_out = None

    dmp_files = [Path(p) for k, p in artifacts.items() if k.endswith(".dmp")]
    if dmp_files:
        dmp = dmp_files[0]
        stackwalk_ran, stackwalk_out = try_stackwalk(stackwalk_path, symbols_dir, dmp, out_dir / "native_stackwalk.txt")
        if stackwalk_out:
            artifacts["native_stackwalk.txt"] = stackwalk_out

            # Fallback: if no breakpad symbols, still try to turn libGame.so offsets into file/line using NDK llvm-addr2line
            if not symbols_dir and addr2line_path and elf_path and Path(elf_path).exists():
                out_path = out_dir / "native_addr2line.txt"
                if symbolize_stackwalk_with_addr2line(Path(stackwalk_out), out_path, addr2line=addr2line_path, elf=elf_path):
                    addr2line_out = str(out_path)
                    artifacts["native_addr2line.txt"] = addr2line_out

    summary = CrashSummary(
        package=args.package,
        device=args.device,
        crash_dir=crash_dir,
        pulled_at=datetime.now().isoformat(timespec="seconds"),
        signal=signal,
        assert_info=assert_info,
        script_context=script_ctx,
        key_log_lines=key_lines,
        artifacts=artifacts,
        stackwalk_ran=stackwalk_ran,
        stackwalk_output=stackwalk_out,
        stackwalk_path=stackwalk_path,
        symbols_dir=symbols_dir,
    )

    (out_dir / "summary.json").write_text(
        json.dumps(asdict(summary), ensure_ascii=False, indent=2),
        encoding="utf-8",
        errors="replace",
    )

    # summary.md (结论先行)
    lines: list[str] = []
    lines.append("# CrashHunter Summary\n\n")

    lines.append("## 结论\n")
    if summary.assert_info and summary.assert_info.file and summary.assert_info.line:
        lines.append(f"- 直接触发点：`{summary.assert_info.file}:{summary.assert_info.line}`\n")
    if summary.assert_info and summary.assert_info.expr:
        lines.append(f"- 断言条件：`{summary.assert_info.expr}`\n")
    if summary.signal:
        lines.append(f"- native signal：`{summary.signal}`\n")
    lines.append(f"- 产物目录：`{out_dir}`\n")

    lines.append("\n## 脚本上下文\n")
    if summary.script_context and (summary.script_context.module or summary.script_context.function):
        lines.append(f"- Module：`{summary.script_context.module}`\n")
        lines.append(f"- Function：`{summary.script_context.function}`\n")
        lines.append(f"- Line：`{summary.script_context.line}`\n")
    else:
        lines.append("- （无或未记录）\n")

    lines.append("\n## 关键日志（截取）\n")
    for ln in summary.key_log_lines or []:
        lines.append(f"- {ln}\n")

    lines.append("\n## Native 栈（stackwalk）\n")
    if summary.stackwalk_ran and summary.stackwalk_output:
        lines.append(f"- stackwalk：`{summary.stackwalk_path}`\n")
        lines.append(f"- symbols：`{summary.symbols_dir}`\n")
        lines.append(f"- 输出：`{summary.stackwalk_output}`\n")
        if addr2line_out:
            lines.append(f"- addr2line（无 symbols 的本地回退）：`{addr2line_out}`\n")
    else:
        dmp_keys = [k for k in (summary.artifacts or {}).keys() if k.endswith(".dmp")]
        if dmp_keys and not summary.stackwalk_path:
            lines.append("- 缺少 `minidump_stackwalk`：可用 MSYS2 安装（见 SKILL.md）。\n")
        elif dmp_keys and summary.stackwalk_path and not summary.symbols_dir:
            lines.append("- 找到 `minidump_stackwalk` 但缺 symbols：请提供 symbols 目录或 `Sym.zip`（breakpad symbols）。\n")
        else:
            lines.append("- 无或未能符号化。\n")

    lines.append("\n## 原始产物\n")
    for k, v in sorted((summary.artifacts or {}).items()):
        lines.append(f"- {k}: `{v}`\n")

    # UTF-8 BOM: friendlier for Windows editors and PowerShell Get-Content.
    (out_dir / "summary.md").write_text("".join(lines), encoding="utf-8-sig", errors="replace")

    print(str(out_dir / "summary.md"))
    print(str(out_dir / "summary.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
