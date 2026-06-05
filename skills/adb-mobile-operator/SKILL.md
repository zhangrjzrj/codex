---
name: adb-mobile-operator
description: "Use when Codex needs to operate or verify an Android emulator/device through ADB: tap, swipe, type text, press keys, launch apps, capture screenshots, dump UI state, or drive a mobile WebView feedback loop. This skill is for system-level human-like input and evidence collection, especially when DOM/MCP actions need real input fallback."
---

# ADB Mobile Operator

## Scope

Use ADB as the system input and evidence layer for Android emulator/device feedback loops.

Typical tasks:
- Tap, swipe, press keys, input text, and submit messages.
- Capture screenshots and UI dumps for evidence.
- Check foreground activity, process state, screen size, and input method state.
- Launch or relaunch the app under test.
- Verify whether a WebView or app changed after an operation.

## Principles

- Prefer DOM/semantic target discovery first when available; use ADB for real system input, fallback execution, and evidence.
- Do not sediment fixed coordinates as reusable skills. Coordinates are temporary execution evidence, ideally derived from current DOM rect, screenshot, or UI dump at execution time.
- After every operation, verify state with screenshot, DOM/MCP read, UI dump, URL, text, or logs.
- Login itself is not a blocker when the user has provided usable credentials or the app has known test credentials. Continue through normal account/password login.
- Stop only when the flow requires user-held sensitive actions such as SMS/email verification codes, captcha/human verification, QR-code approval, payment confirmation, or other external account-security steps that Codex cannot complete without the user.
- Keep commands non-destructive. Do not clear app data, uninstall, reset device, or change global settings unless the user explicitly requests it.

## Common Commands

Check device:

```powershell
adb devices
adb shell wm size
adb shell wm density
adb shell dumpsys activity activities | Select-String -Pattern "mResumedActivity|ResumedActivity|topResumedActivity"
```

Tap and swipe:

```powershell
adb shell input tap <x> <y>
adb shell input swipe <x1> <y1> <x2> <y2> <duration_ms>
```

Text and keys:

```powershell
adb shell input text "hello"
adb shell input keyevent ENTER
adb shell input keyevent BACK
```

Screenshot evidence:

```powershell
adb shell screencap -p /sdcard/evidence.png
adb pull /sdcard/evidence.png .codex-memory\evidence.png
```

UI dump evidence:

```powershell
adb shell uiautomator dump /sdcard/window.xml
adb pull /sdcard/window.xml .codex-memory\window.xml
```

Launch app:

```powershell
adb shell monkey -p com.chaoweisuanli.duomilu 1
```

## Feedback Loop

1. Record the current screen and foreground activity.
2. Identify the target from DOM/MCP/UI dump/screenshot.
3. If using coordinates, compute them from current evidence and use them immediately.
4. Execute ADB input.
5. Wait briefly for UI settling.
6. Capture new evidence.
7. Compare before/after and decide the next step.

## Chinese Text Input

`adb shell input text` is unreliable for Chinese in many WebView/input-method combinations. If Chinese input is required:

- Prefer app/MCP text APIs when available.
- If using ADB Keyboard or another IME, first verify that committed text appears in the target field.
- If verification fails, do not assume text was entered.
