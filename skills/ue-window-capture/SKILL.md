---
name: "ue-window-capture"
description: "Capture screenshots of a running Unreal Editor GUI window for UE visual feedback loops. Use when Codex needs evidence screenshots from Unreal Editor or PIE without relying on the current foreground window; supports PID/title selection but requires the UE window to be visible, not minimized, and not occluded for accurate pixels."
---

# UE Window Capture

Use this skill to capture Unreal Editor GUI evidence during UE debugging, PIE playback checks, MRG/NBS visual validation, or other UE feedback loops.

## Capability

- Captures a running `UnrealEditor.exe` window by PID, title regex, or first matching process.
- Does not require Unreal Editor to be the active foreground window.
- Writes a PNG and a JSON metadata file.

## Limits

- The target window must be visible and not minimized.
- Pixels come from the desktop compositor via screen copy; if another window covers UE, the capture can include the covering window.
- This is not a GPU backbuffer readback and not a RenderDoc capture.
- For hidden/minimized/background-correct captures, use a UE-specific viewport/readback path or RenderDoc instead.

## Quick Start

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

## Feedback Loop Pattern

1. Confirm `UnrealEditor` is running and responsive.
2. Trigger the UE action or PIE state needed for the test.
3. Wait for rendering/playback to settle.
4. Run `capture_ue_window.ps1`.
5. Inspect the PNG and metadata before deciding pass/fail.

Metadata fields to check:

- `success`: capture succeeded.
- `processId`, `windowTitle`, `windowHandle`: target identity.
- `rect`, `width`, `height`: captured region.
- `isIconic`: must be false.
- `warning`: non-empty means evidence may be unreliable.

