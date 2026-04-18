---
name: messiah-tracy-analyzer
description: Analyze Tracy `.tracy` captures on Windows, export machine-readable hotspot data when possible, detect legacy-format failures, and produce a concise stall/root-cause summary with artifacts. Use when the user asks where a Tracy capture is stalling, which zones are hottest, what likely causes the hitch, or wants repeatable offline analysis of `.tracy` files.
---

# Messiah Tracy Analyzer

## Overview

Use this skill when the user already has a `.tracy` file and wants offline analysis.
Prefer the bundled script over ad hoc GUI clicking so output stays stable and reusable.
This skill is direct-export only. If CSV export fails, treat that as a skill/tooling problem to fix instead of falling back to screenshots.

## Quick Start

- Run `scripts/analyze_tracy.py --trace-path <path-to-file.tracy>`.
- Read `summary.json` first.
- If the script reports `analysis_mode=csvexport`, trust the hotspot summary.
- If the script reports `analysis_mode=error`, stop and fix the direct-export path or add explicit compatibility for that trace format.

## Workflow

1. Confirm the input trace path.
- Required: `--trace-path`

2. Run the analyzer.
- The script will:
  - detect or download official Tracy tools
  - try `tracy-csvexport.exe` on multiple official versions
  - parse hotspot statistics when export succeeds
  - detect legacy/unsupported crashes
  - fail fast when direct export is unavailable

3. Read the result summary first.
- Focus on:
  - `analysis_mode`
  - `likely_bottleneck_type`
  - `top_hotspots`
  - `notes`

4. Only drill deeper if needed.
- Use the CSV artifacts for exact zone totals and max spikes.
- If export fails, repair the export chain instead of using GUI screenshots.

## Command

```powershell
python C:\Users\zhangruojun\.codex\skills\messiah-tracy-analyzer\scripts\analyze_tracy.py --trace-path "C:\path\capture.tracy"
```

Optional output directory:

```powershell
python C:\Users\zhangruojun\.codex\skills\messiah-tracy-analyzer\scripts\analyze_tracy.py --trace-path "C:\path\capture.tracy" --output-dir "C:\temp\tracy-report"
```

## Output Contract

The script writes:

- `summary.json`: primary machine-readable result
- `stats.csv`: raw zone statistics when export succeeds
- `events.csv`: raw zone events when export succeeds
- `run.log`: command-level evidence

## Interpretation Rules

- Treat very large `max_ns` zones as hitch suspects.
- Prefer `self`-time hotspots when explaining "what itself is slow".
- Prefer total-time hotspots when explaining "what dominates the frame budget overall".
- If export fails with legacy-format errors or native crashes, say so directly instead of fabricating a cause.
- Do not use screenshot-only evidence from this skill.

## Guardrails

- Offline analysis only. Do not launch the game from this skill.
- Prefer the smallest analysis that answers the question.
- Distinguish clearly between:
  - confirmed evidence from CSV
  - inferred likely cause from hotspot shape
  - exporter/tooling failures that require skill fixes
