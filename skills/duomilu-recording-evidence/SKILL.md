---
name: "duomilu-recording-evidence"
description: "Record and verify Duomilu Android emulator test evidence with scrcpy-first workflows, including background video capture, nonempty/black-screen sanity checks, optional audio-presence checks, frame extraction, and evidence path reporting. Use when Codex needs to record Duomilu app2/app emulator feedback-loop tests, lip-sync checks, screenshot consistency checks, or full task runs without relying on the emulator window staying in front."
---

# Duomilu Recording Evidence

Use this skill to collect repeatable video evidence for Duomilu emulator tests. The skill is only for recording, verification, and evidence reporting; it does not decide whether the business task itself passed.

## Workflow

1. Identify the target Android device with `adb devices`. If several devices are present, choose the app-specific emulator requested by the user or the one already used in the current test context.
2. Store recordings under a project-local ignored evidence directory such as `D:\hanhan\app2\.local-artifacts\runtime-evidence\`.
3. Prefer scrcpy recording because it can capture the device stream without keeping the emulator window in front:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_scrcpy_record.ps1 -Serial <adb-serial> -Output <path-to-mp4>
```

4. Run the Duomilu test while recording.
5. Stop the recorder:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stop_scrcpy_record.ps1 -PidFile <path-to-pid-json>
```

6. Verify the output:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\check_recording.ps1 -Path <path-to-mp4> -ExtractFrame
```

7. Report the mp4 path, duration if available, extracted frame path if available, task/session identifiers, and any limitation such as missing audio metadata.

If scrcpy is unavailable and cannot be installed during the current run, use ADB `screenrecord` as a video-only fallback:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\record_adb_screen.ps1 -Serial <adb-serial> -Output <path-to-mp4> -TimeLimitSeconds 10
```

## Evidence Rules

- Start recording before the user-visible action begins when the user asks for a full-process recording.
- Keep generated mp4/png/log files out of source changes by using ignored local artifact folders.
- Treat a missing, tiny, unreadable, or black recording as a failed evidence collection and fix recording before claiming the test passed.
- For lip-sync checks, include both video evidence and timing/log evidence when available. A recording is for human replay; logs provide timestamp alignment.
- ADB `screenrecord` fallback is video-only evidence. Do not use it as proof of audio playback or lip-sync by itself.
- For screenshot consistency checks, extract at least one frame near the reported screenshot moment and compare it with the app-returned image when available.

## Troubleshooting

- `scrcpy` missing: locate or install scrcpy before falling back to OBS.
- Black video: retry with another capture path, confirm the target serial is correct, and verify the emulator is rendering visible content.
- No sound: confirm Windows audio is unmuted and confirm the chosen recorder can capture audio. scrcpy video recording may not prove host speaker output on all setups; note this limitation explicitly.
- Empty or very short mp4: confirm the recorder process stayed alive for the whole run and that it was stopped cleanly.
- Wrong device: rerun `adb devices` and use an explicit `-Serial`.

## Scripts

- `scripts/start_scrcpy_record.ps1`: Start scrcpy recording in the background and write a pid metadata file.
- `scripts/stop_scrcpy_record.ps1`: Stop the scrcpy recorder by pid metadata.
- `scripts/check_recording.ps1`: Check file size, optional ffprobe duration, optional audio streams, and extract one frame with ffmpeg when requested.
- `scripts/record_adb_screen.ps1`: Record a bounded video-only clip through ADB `screenrecord`, pull it locally, and remove the remote temp file.
