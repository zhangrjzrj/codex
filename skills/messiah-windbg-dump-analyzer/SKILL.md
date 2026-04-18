---
name: messiah-windbg-dump-analyzer
description: Analyze Windows crash dump files (`.dmp`) for Messiah or similar native crashes by silently invoking `cdb` or WinDbg command-line tooling, extracting exception details, registers, crashing-thread stacks, and all-thread stacks, then summarizing likely root cause. Use when Codex needs to inspect a dump, compare whether a newly reproduced crash matches an older signature, or generate a structured crash report without opening a debugger UI.
---

# Messiah WinDbg Dump Analyzer

## Overview

Use this skill to inspect Windows `.dmp` files in a quiet, automatable way.
Prefer the bundled script over ad hoc debugger commands so output stays stable and easy to diff across crashes.

## Quick Start

- Run `scripts/analyze_dump.py --dump-path <path-to-dmp>`.
- Pass `--symbol-path` when symbols are available; this improves stack readability a lot.
- Read `references/commands.md` only when you need to tweak the debugger command set or interpret raw output.

## Workflow

1. Locate the dump file.
- Prefer the newest `.dmp` under a local crash output directory when reproducing locally.

2. Run the bundled script.
- Default behavior:
  - prefer `cdb.exe`
  - fall back to `windbg.exe`
  - avoid interactive UI
  - write stable text and JSON outputs

3. Inspect the generated outputs.
- Primary outputs:
  - `summary.json`
  - `debugger_stdout.txt`
- Check these first:
  - exception code
  - exception address
  - crashing thread
  - top stack frames

4. Compare with known signatures.
- When checking whether two dumps are the same class of crash, focus on:
  - exception type
  - top stack frames
  - whether the path is `read` / `seek` callback related
  - whether registers suggest null, freed, or stale object access

## Script

- `scripts/analyze_dump.py`
  - Silent dump-analysis entry point
  - Finds `cdb.exe` automatically when possible
  - Runs a fixed debugger command set
  - Writes raw text plus a compact JSON summary

## Notes

- If `cdb` or WinDbg is not installed, the script exits clearly instead of fabricating results.
- If symbols are missing, the script still captures raw debugger output, but stack quality may be limited.
- For debugger command details, see `references/commands.md`.
