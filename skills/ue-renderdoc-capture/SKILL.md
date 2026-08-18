---
name: "ue-renderdoc-capture"
description: "Capture real RenderDoc .rdc frames from Unreal Editor, PIE, standalone, or a scoped UE RenderGraph path. Use when Codex needs GPU evidence, precise NBS/MRG/composition capture, playback ViewFamily capture, or repeated A/B rendering diagnosis without relying on window focus."
---

# UE RenderDoc Capture

## Core Rule

Use this skill for RenderDoc `.rdc` capture, not for ordinary screenshots. The desired evidence is a GPU capture file under the UE project, usually:

```text
<Project>/Saved/RenderDocCaptures/*.rdc
```

For pixels-only evidence, use `ue-window-capture` instead.

## Preferred Workflow

1. Confirm an `UnrealEditor.exe` process is running.
2. Confirm the process command line contains `-AttachRenderDoc`, or the UE log shows `RenderDoc plugin is ready`.
3. Ensure the target viewport/PIE state is already showing the frame to capture.
4. Run `scripts/capture_ue_renderdoc.ps1`.
5. Verify success from both:
   - UE log contains `Cmd: renderdoc.CaptureFrame` and `RenderDocPlugin: Capture frame and launch renderdoc!`
   - A new `.rdc` exists and has nonzero size.

## Scoped RenderGraph Capture

Prefer a code-level scoped capture when a specific UE render path must be isolated repeatedly.

1. Locate the earliest callback that owns the target `FRDGBuilder` before target passes are registered.
2. Create `RenderCaptureInterface::FScopedCapture` with that `FRDGBuilder`.
3. Keep the object alive until the callback that finishes registering the required pass range.
4. Do not call `GraphBuilder.Execute()` from a plugin. The RDG constructor schedules `BeginCapture` and its destructor schedules `EndCapture` in the graph.
5. Gate capture by the real target world/view identity, not window focus. For playback, require `EWorldType::PIE` or `EWorldType::Game` and an active composition proxy.
6. Use separate frame and request controls: frame selects the zero-based eligible render frame; incrementing request id rearms one capture without inventing persistent capture state.
7. Verify the RDC event tree contains the target composition pass and required downstream passes before accepting success.
8. For large full-ViewFamily captures, perform at most one scoped capture per Unreal Editor process. Restart the editor before another large capture; repeated captures can page-fault RenderDoc's D3D12 copy path on constrained GPUs.

For a full playback frame, scope from `PreRenderViewFamily_RenderThread` through `PostRenderViewFamily_RenderThread`. For a narrow pass-only capture, scope around the registration block only when downstream effects are not required.

## Quick Command

```powershell
powershell -ExecutionPolicy Bypass -File "$HOME\.codex\skills\ue-renderdoc-capture\scripts\capture_ue_renderdoc.ps1" -ProcessId <UE_PID>
```

Useful parameters:

```powershell
-ProcessId 50656
-ProjectRoot "F:\ue\ue-test-demo_new_mrg"
-Command "renderdoc.CaptureFrame"
-TriggerMode auto
-TimeoutSeconds 90
```

If `-ProjectRoot` is omitted, the script tries to infer it from the running editor command line.

## Trigger Modes

- `auto`: Prefer ArtClaw MCP in-process capture, fall back to UE Cmd UI input.
- `mcp`: Require ArtClaw MCP in-process capture. This is the stable background path.
- `ui`: Force the legacy UE Cmd input fallback.

The stable path requires ArtClaw embedded MCP to expose:

```text
artclaw_renderdoc_capture_frame
```

That tool calls UE's render capture provider inside the editor process, so it does not need to click the UE window or bring UE to the foreground.

## UI Fallback

Older ArtClaw builds may not expose `artclaw_renderdoc_capture_frame`. In that case `-TriggerMode auto` falls back to the same operation as manual input:

```text
click UE bottom Cmd input -> type renderdoc.CaptureFrame -> Enter
```

Use this fallback only when MCP is unavailable. It requires the UE window to be visible and can briefly steal foreground focus.

## Failure Handling

If no `.rdc` is produced:

- Recheck that UE was started with `-AttachRenderDoc`.
- Recheck that the RenderDoc plugin log says `RenderDoc plugin is ready`.
- Recheck that ArtClaw MCP is listening at `http://127.0.0.1:17881/mcp`.
- Recheck that `tools/list` includes `artclaw_renderdoc_capture_frame`.
- If MCP is unavailable, recheck that the UE window is visible and not minimized for UI fallback.
- If focus automation fails, ask the user to click the UE viewport or Cmd box and press `Alt+F12` or run `renderdoc.CaptureFrame`; then search for `.rdc`.
- If a scoped request produces no RDC, log and verify request arming, eligible world type, target frame count, capture provider availability, and actual scope creation in that order.
- If the RDC exists but misses downstream passes, widen the scope lifetime; do not add sleeps or call RDG execution manually.

## Expected Evidence

Report:

- UE process id.
- UE log lines around `renderdoc.CaptureFrame`.
- `.rdc` absolute path.
- file size.
- trigger mode (`mcp` or `ui`).
- whether the capture was generated after this run's start time.
