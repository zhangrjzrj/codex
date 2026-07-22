---
name: "windows-graphics-capture"
description: "Capture a complete visible Windows application window with Windows Graphics Capture even when another window occludes it or it is not foreground. Use for occlusion-safe full UI screenshots of Unreal Editor, Win32, Qt, Electron, browsers, or desktop tools; output image evidence and JSON metadata."
---

# Windows Graphics Capture

Use this skill for complete application-window UI evidence when a desktop copy would include an overlapping window. It uses Windows Graphics Capture (WGC), not screen pixels.

## Capture

1. Confirm the target window is visible and not minimized with `windows-uia-operator` or `Get-Process`.
2. Put outputs in the project's ignored evidence directory.
3. Run the bundled script with a unique title substring or a process ID.

```powershell
powershell -ExecutionPolicy Bypass -File "$HOME\.codex\skills\windows-graphics-capture\scripts\capture_window_wgc.ps1" `
  -TitleSubstring "ue_test_demo" `
  -OutputPath "F:\project\Saved\CodexEvidence\ue-ui.png" `
  -Json
```

Use `-ProcessId` when the process identity is more stable than its window title. The script writes PNG and sibling JSON metadata, including the target HWND, title, capture dimensions, and image byte count.

## Evidence Rules

- Inspect the image and metadata before treating it as pass evidence.
- Preserve the original image. For large images, create a visual-only preview with `image-payload-optimizer`.
- If proving occlusion safety matters, also capture a normal desktop screenshot in the same state; it should show the overlapping foreground content while WGC does not.
- WGC captures an application window, not its desktop z-order composition. Use it for full IDE/UI screenshots; use UE internal screenshot APIs for viewport render evidence when that is the actual target.

## Limits

- The target must be visible and non-minimized.
- Do not assume success for DRM/protected content, secure desktop prompts, elevated windows from a lower-integrity process, or exclusive-fullscreen applications.
- A successful file only proves a frame arrived; inspect it for stale, blank, or startup UI before accepting it.
