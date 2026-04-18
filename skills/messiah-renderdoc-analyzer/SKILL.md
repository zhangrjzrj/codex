---
name: messiah-renderdoc-analyzer
description: "Analyze Messiah RenderDoc captures (.rdc), locate target passes and shader stages, export machine-readable summaries, and inspect shader disassembly or constant-buffer values without rerunning gameplay."
---

# Messiah RenderDoc Analyzer

## When to use

Use this skill when the user already has an `.rdc` capture and wants offline analysis rather than a live replay.

Typical asks:
- inspect a Messiah `.rdc`
- find a pass by keyword
- inspect vertex or pixel shader state
- export shader disassembly or cbuffer values
- compare target events without rerunning the game

If the user needs to launch the client, capture on playback start, or run a full scenario loop, use `messiah-test-loop` first.

## Resources

- `scripts/renderdoc_analyze.py`: offline analyzer

## Workflow

1. Confirm inputs.
- Required: `--rdc-path`
- Usually also provide `--pass-keyword` and `--stage`

2. Run the analyzer.
- Output is JSON plus optional text artifacts beside it.

3. Read the result summary first.
- Focus on target event selection, matched pass, shader stage, and exported cbuffer summary.

4. Only drill deeper if needed.
- Use `--target-event-id` when the user already knows the exact draw/event.
- Tune cbuffer extraction with `--cb-value-mode`, `--cb-top-n`, and `--cb-neighbor-window`.

## Command

Basic analysis:
```powershell
python C:\Users\zhangruojun\.codex\skills\messiah-renderdoc-analyzer\scripts\renderdoc_analyze.py --rdc-path "F:\capture.rdc" --pass-keyword WaterPass --stage pixel
```

With exact event and cbuffer tuning:
```powershell
python C:\Users\zhangruojun\.codex\skills\messiah-renderdoc-analyzer\scripts\renderdoc_analyze.py --rdc-path "F:\capture.rdc" --pass-keyword WaterPass --stage pixel --target-event-id 12345 --cb-value-mode layered --cb-top-n 20 --cb-neighbor-window 3 --cb-nonzero-only false
```

## Guardrails

- Treat this as offline analysis only; do not launch the game from this skill.
- Prefer the smallest command that answers the user?s question.
- Report clearly when the analyzer can only produce a partial match.
