---
name: "ue-window-capture"
description: "Capture Unreal Editor evidence screenshots for UE visual feedback loops. Use when Codex needs either full IDE/window screenshots of Unreal Editor, or occlusion-safe lightweight viewport/PIE screenshots through ArtClaw MCP and UE internal screenshot APIs, with JSON metadata for MRG/NBS/render validation."
---

# UE Window Capture

Use this skill to capture Unreal Editor evidence during UE debugging, PIE playback checks, MRG/NBS visual validation, or other UE feedback loops.

## Capture Modes

### IDE Window

Use `scripts/capture_ue_window.ps1` when Codex must see the whole Unreal Editor IDE:

- MRG graph layout
- Details panel
- Outliner
- Content Browser
- modal dialogs or editor chrome

- Captures a running `UnrealEditor.exe` window by PID, title regex, or first matching process.
- Does not require Unreal Editor to be the active foreground window.
- Writes a PNG and a JSON metadata file.

Limits:

- The target window must be visible and not minimized.
- Pixels come from the desktop compositor via screen copy; if another window covers UE, the capture can include the covering window.
- This is not a GPU backbuffer readback and not a RenderDoc capture.

### Viewport Internal

Use `scripts/capture_ue_viewport.ps1` when Codex needs occlusion-safe render evidence:

- PIE or editor viewport result
- NBS playback visual checks
- rain/character/depth composition checks
- color/scale/camera validation

This mode calls ArtClaw MCP, which executes UE Python inside the editor process and uses `unreal.AutomationLibrary.take_high_res_screenshot`. It does not use RenderDoc, does not click the UE window, and does not require the editor window to be foreground or unoccluded.

Limits:

- Captures the active UE viewport, not the full IDE.
- The PNG alone does not prove whether the source was PIE or editor scene view; always inspect the JSON metadata and ArtClaw report.
- Requires ArtClaw MCP at `http://127.0.0.1:17881/mcp` and a running `UnrealEditor.exe`.

## Quick Start: IDE Window

Run the bundled script:

```powershell
powershell -ExecutionPolicy Bypass -File "$env:CODEX_HOME\skills\ue-window-capture\scripts\capture_ue_window.ps1" -OutputPath "F:\path\shot.png"
```

If `CODEX_HOME` is unset, use:

```powershell
powershell -ExecutionPolicy Bypass -File "$HOME\.codex\skills\ue-window-capture\scripts\capture_ue_window.ps1" -OutputPath "F:\path\shot.png"
```

Useful options:

```powershell
# Exact UE process id.
-ProcessId 38400

# Window title regex.
-TitleRegex "ue_test_demo|LVL_H74"

# Also print JSON metadata to stdout.
-Json
```

## Quick Start: Viewport Internal

```powershell
powershell -ExecutionPolicy Bypass -File "$HOME\.codex\skills\ue-window-capture\scripts\capture_ue_viewport.ps1" `
  -ProjectRoot "F:\ue\ue-test-demo_new_mrg" `
  -OutputPath "F:\ue\ue-test-demo_new_mrg\Saved\CodexEvidence\shot.png" `
  -Width 1280 -Height 720 -Json
```

Useful options:

```powershell
# Exact UE process id used for metadata and project inference.
-ProcessId 31372

# Capture at a custom size.
-Width 1920 -Height 1080

# Ask UE to use game view where supported.
-ForceGameView

# ArtClaw endpoint override.
-McpUrl "http://127.0.0.1:17881/mcp"
```

## Feedback Loop Pattern

1. Confirm `UnrealEditor` is running and responsive.
2. Choose capture mode:
   - IDE state or editor UI: use `capture_ue_window.ps1`.
   - render/playback result: use `capture_ue_viewport.ps1`.
3. Wait for rendering/playback to settle.
4. Run the selected capture script.
5. Inspect the PNG and metadata before deciding pass/fail.

IDE metadata fields to check:

- `success`: capture succeeded.
- `processId`, `windowTitle`, `windowHandle`: target identity.
- `rect`, `width`, `height`: captured region.
- `isIconic`: must be false.
- `warning`: non-empty means evidence may be unreliable.

Viewport metadata fields to check:

- `success`: capture succeeded.
- `captureMode`: `viewport_internal`.
- `processId`, `projectRoot`: target identity.
- `width`, `height`: requested screenshot size.
- `artclawRunId`, `artclawReportPath`: in-editor execution evidence.
- `outputExists`, `outputSizeBytes`: file sanity.
- `warning`: non-empty means evidence may need manual interpretation.

## Escalation

- If viewport PNG is insufficient and GPU pass evidence is needed, use `ue-renderdoc-capture`.
- If full IDE screenshot must be occlusion-safe, this skill cannot guarantee it; prefer exporting asset/graph metadata as JSON plus viewport screenshot.
