---
name: "temporal-visual-evidence"
description: "Record a visible Windows application window through Windows Graphics Capture and analyze dynamic visual artifacts over time. Use when automated evidence is needed for flicker, waves, shimmer, temporal instability, animation regressions, intermittent rendering defects, or A/B visual gates in Unreal Engine, desktop applications, browsers, emulators, or other Windows windows where single screenshots are insufficient."
---

# Temporal Visual Evidence

Capture a target window without desktop occlusion, then analyze a fixed region across consecutive frames. Treat this as a temporal evidence workflow, not a general video editor.

## Workflow

1. Confirm the target process has a visible, non-minimized top-level window.
2. Put output under the target project's ignored evidence directory.
3. Record 8-15 seconds at 10-15 FPS with `scripts/record_window_wgc.ps1`.
   For startup-only defects, use `scripts/record_window_triggered.ps1` so capture becomes ready before the application trigger runs.
4. Keep the camera and application timeline deterministic between A/B runs.
5. Analyze the smallest region containing the defect with `scripts/analyze_temporal_frames.py`.
6. Establish a known-good baseline before applying a ratio gate.
7. Inspect the heatmap and contact sheet before accepting the numeric verdict.

## Record

```powershell
powershell -ExecutionPolicy Bypass -File scripts/record_window_wgc.ps1 `
  -ProcessId 12345 `
  -OutputDirectory "F:\project\Saved\JEvidence\temporal\baseline" `
  -DurationSeconds 10 `
  -FramesPerSecond 12 `
  -CreateVideo `
  -Json
```

Use `-WindowTitleSubstring` for a PIE/Standalone child window when the process has multiple top-level windows. Use `-TitleSubstring` only for a process main window. WGC requires the target window to remain visible and non-minimized, but other windows may cover it.

## Triggered startup capture

Provide a deterministic trigger script that starts playback, reloads a scene, or begins a test only after WGC writes its ready signal:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/record_window_triggered.ps1 `
  -WindowTitleSubstring "Target Window" `
  -OutputDirectory "F:\project\Saved\JEvidence\temporal\startup" `
  -TriggerScript "F:\project\Saved\JEvidence\triggers\start_playback.ps1" `
  -PostTriggerSeconds 3 `
  -FramesPerSecond 30 `
  -CreateVideo `
  -Json
```

Treat `trigger.json` as the requested start marker. Prefer an application-native trigger and record an application-confirmed BeginPlay or sequence-start marker when available. Use UI Automation or synthetic input only when the application exposes no control API.

## Analyze

Pixel ROI:

```powershell
python scripts/analyze_temporal_frames.py `
  --frames-dir "F:\project\Saved\JEvidence\temporal\baseline\frames" `
  --output-dir "F:\project\Saved\JEvidence\temporal\baseline\analysis" `
  --roi "120,360,900,300"
```

Fractional ROI uses `left,top,right,bottom` in the range 0-1:

```powershell
python scripts/analyze_temporal_frames.py `
  --frames-dir "...\frames" `
  --output-dir "...\analysis" `
  --roi-fraction "0.1,0.55,0.9,0.98" `
  --baseline-report "...\baseline\analysis\report.json" `
  --max-baseline-ratio 1.25
```

## Evidence

Require all of these before a verdict:

- `recording.json` reports success, expected frame count, target PID/HWND, and capture dimensions.
- `report.json` reports at least 20 analyzed frames.
- `temporal_heatmap.png` localizes motion to the expected defect region.
- `contact_sheet.png` shows consistent framing and no camera cut.
- A baseline comparison uses the same duration, FPS, resolution, ROI, camera, and timeline.

Do not treat high temporal energy alone as a defect when the ROI contains intentional rain, particles, character motion, camera motion, or UI animation. Reduce the ROI or create a more controlled baseline.

## Escalation

- Use app-native capture when WGC cannot access a protected/elevated window.
- Use RenderDoc after temporal evidence identifies the responsible time interval or renderer.
- Use a human-defined ROI once when semantic separation cannot be inferred from pixels alone; subsequent A/B runs can remain automated.
