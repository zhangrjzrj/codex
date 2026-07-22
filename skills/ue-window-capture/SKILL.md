---
name: "ue-window-capture"
description: "Capture occlusion-safe Unreal Editor viewport or PIE render evidence through ArtClaw MCP and UE internal screenshot APIs, with JSON metadata for MRG, NBS, composition, and render validation. Use for scene/viewport pixels, not complete editor UI."
---

# UE Viewport Capture

Use this skill for UE viewport or PIE render evidence. It captures pixels inside the editor process, does not click the UE window, and does not require the editor to be foreground or unoccluded.

For complete Unreal Editor UI such as menus, MRG graph layout, Details, Outliner, Content Browser, or dialogs, use `windows-graphics-capture` instead.

## Capture

1. Confirm `UnrealEditor.exe` is running and responsive.
2. Put output in the project's ignored evidence directory.
3. Run the bundled script.

```powershell
powershell -ExecutionPolicy Bypass -File "$HOME\.codex\skills\ue-window-capture\scripts\capture_ue_viewport.ps1" `
  -ProjectRoot "F:\ue\ue-test-demo_new_mrg" `
  -OutputPath "F:\ue\ue-test-demo_new_mrg\Saved\CodexEvidence\viewport.png" `
  -Width 1280 -Height 720 -Json
```

Useful options:

```powershell
# Bind metadata to a specific UE process.
-ProcessId 31372

# Use game view where supported.
-ForceGameView

# Override the ArtClaw endpoint.
-McpUrl "http://127.0.0.1:17881/mcp"
```

## Validate

Inspect both the PNG and JSON metadata:

- `success` is true.
- `captureMode` is `viewport_internal`.
- `processId` and `projectRoot` identify the intended editor.
- `outputExists` is true and `outputSizeBytes` is nonzero.
- `artclawRunId` and `artclawReportPath` provide in-editor execution evidence.

The image alone does not prove whether the source was PIE or editor scene view; use the metadata and ArtClaw report for that distinction.

## Escalation

- For complete editor UI: use `windows-graphics-capture`.
- For GPU pass or shader evidence: use `ue-renderdoc-capture`.
