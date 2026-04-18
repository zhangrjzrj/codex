---
name: messiah-crashhunter-analyzer
description: Pull and analyze Messiah Android CrashHunter artifacts (NATIVE_DUMP_*/JAVA_DUMP_*), extract assert/signal/script context, and optionally run minidump stackwalk symbolization to produce a readable native stack.
metadata:
  short-description: Analyze CrashHunter dumps
---

# Messiah CrashHunter Analyzer

## When to use

用于 Messiah **Android** 崩溃后的快速闭环：

- 从手机拉取 CrashHunter 产物（`adb run-as`）
- 解析断言上下文：`game_assert.other`
- 解析脚本上下文：`game_stack.other`
- 抽取关键 `logcat.log` 线索
- 可选：对 `*.dmp` 自动跑 `minidump_stackwalk` 还原 C++ 调用栈（需要 symbols）

## Quick start

1) 只拉产物 + 输出摘要（不做 native 栈）：

`python C:/Users/zhangruojun/.codex/skills/messiah-crashhunter-analyzer/scripts/analyze_crashhunter.py --device <adb-serial>`

2) 拉产物 + 自动 stackwalk（提供 symbols 目录或 `Sym.zip`）：

`python C:/Users/zhangruojun/.codex/skills/messiah-crashhunter-analyzer/scripts/analyze_crashhunter.py --device <adb-serial> --symbols <symbols-dir-or-Sym.zip>`

> `minidump_stackwalk` 会自动尝试从 PATH 和默认 MSYS2 目录查找；也可以用 `--stackwalk <path>` 显式指定。
>
> 如果你没有 `Sym.zip`：脚本会在检测到本机 NDK 的 `llvm-addr2line` 且找到本地 `libGame.so`（未 strip）时，自动生成 `native_addr2line.txt`，把 `libGame.so + 0x...` 翻译成函数/文件/行号（作为 stackwalk 的回退方案）。

## Outputs

脚本会创建输出目录并打印路径：

- `summary.md`：结论先行的可读报告
- `summary.json`：结构化字段（assert/file/line、signal、脚本上下文、产物路径）
- 原始产物：`logcat.log` / `game_assert.other` / `game_stack.other` / `*.dmp`
- 如果跑了 stackwalk：`native_stackwalk.txt`
- 如果触发了 addr2line 回退：`native_addr2line.txt`

## Notes / gotchas

- `adb run-as` 需要可用（通常是 debug 或 shell 允许的包），否则拉取会失败。
- CrashHunter 可能生成多个 `NATIVE_DUMP_*`；脚本按目录名排序取“最新”。
- 没有 stackwalk/symbols 也没关系：断言点 + logcat 通常就足够指导“资源/包匹配”修复。

## Install stackwalk (Windows)

如果你电脑上没有 `minidump_stackwalk.exe`，推荐用 MSYS2 安装 breakpad 工具：

- 安装 MSYS2：`winget install -e --id MSYS2.MSYS2 --accept-package-agreements --accept-source-agreements`
- 安装 breakpad（含 `minidump_stackwalk.exe` / `dump_syms.exe`）：
  - `C:\\msys64\\usr\\bin\\bash.exe -lc "pacman -Sy --noconfirm && pacman -S --noconfirm --needed mingw-w64-x86_64-breakpad"`

默认路径一般是：

- `C:\\msys64\\mingw64\\bin\\minidump_stackwalk.exe`
- `C:\\msys64\\mingw64\\bin\\dump_syms.exe`
