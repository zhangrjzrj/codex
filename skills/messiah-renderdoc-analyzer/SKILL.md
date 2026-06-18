---
name: "messiah-renderdoc-analyzer"
description: "Analyze Messiah RenderDoc captures (.rdc), locate target passes and shader stages, export machine-readable summaries, inspect shader disassembly or constant-buffer values, and apply temporary shader replacement debug HLSL to export annotated screenshots/color statistics without rerunning gameplay."
---

# Messiah RenderDoc Analyzer

## When to use

Use this skill when the user already has an `.rdc` capture and wants offline analysis rather than a live replay.

Typical asks:
- inspect a Messiah `.rdc`
- find a pass by keyword
- inspect vertex or pixel shader state
- export shader disassembly or cbuffer values
- apply a RenderDoc shader replacement from `shader.txt`
- export a debug PNG after replacing a pixel/vertex shader
- summarize debug colors such as alpha/depth classification
- compare target events without rerunning the game

If the user needs to launch the client, capture on playback start, or run a full scenario loop, use `messiah-test-loop` first.

## Resources

- `scripts/renderdoc_analyze.py`: offline analyzer
- `scripts/renderdoc_shader_debug.py`: apply a temporary RenderDoc shader replacement, export the current render target as PNG, and write color statistics JSON
- `scripts/renderdoc_window_capture.py`: capture a non-minimized RenderDoc window by title via Windows `PrintWindow`, useful when Codex needs eyes on the current UI without stealing the mouse/keyboard

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

## Shader Replacement Workflow

Use this when the user has an `.rdc`, an event id, and a replacement HLSL stub such as RenderDoc's exported `shader.txt`.

1. Ensure the replacement shader has the expected entry point.
- Default entry is `EditedShaderPS`.
- Default stage is `pixel`.

2. Run `renderdoc_shader_debug.py`.
- It launches `qrenderdoc.exe --ui-python`.
- It uses RenderDoc replay APIs: `BuildTargetShader`, `ReplaceResource`, `SetFrameEvent`, and `SaveTexture`.
- It does not modify the `.rdc` file; replacement is temporary during replay.

3. Read the output JSON before interpreting the PNG.
- Check `status`, `shader.compile_messages`, and `output.save_result`.
- Use `png_stats.mean_rgba` and `png_stats.dominance_ratio` for quick classification.

## Command

Basic analysis:
```powershell
python C:\Users\zhangruojun\.codex\skills\messiah-renderdoc-analyzer\scripts\renderdoc_analyze.py --rdc-path "F:\capture.rdc" --pass-keyword WaterPass --stage pixel
```

With exact event and cbuffer tuning:
```powershell
python C:\Users\zhangruojun\.codex\skills\messiah-renderdoc-analyzer\scripts\renderdoc_analyze.py --rdc-path "F:\capture.rdc" --pass-keyword WaterPass --stage pixel --target-event-id 12345 --cb-value-mode layered --cb-top-n 20 --cb-neighbor-window 3 --cb-nonzero-only false
```

Shader replacement debug export:
```powershell
python C:\Users\zhangruojun\.codex\skills\messiah-renderdoc-analyzer\scripts\renderdoc_shader_debug.py --rdc-path "F:\capture.rdc" --event-id 1215 --shader-path "F:\shader.txt" --output-png "F:\out\event1215_debug.png" --output-json "F:\out\event1215_debug.json"
```

RenderDoc window capture by title:
```powershell
python C:\Users\zhangruojun\.codex\skills\messiah-renderdoc-analyzer\scripts\renderdoc_window_capture.py --window-title "nbs分支.rdc - RenderDoc" --output-png "F:\out\rd_window.png" --output-json "F:\out\rd_window.json"
```

## Guardrails

- Treat this as offline analysis only; do not launch the game from this skill.
- Window capture works best when the RenderDoc window is not minimized; foreground focus is preferred but not required.
- Do not describe shader replacement as permanently modifying an `.rdc`; it is replay-only.
- Prefer the smallest command that answers the user?s question.
- Report clearly when the analyzer can only produce a partial match.
