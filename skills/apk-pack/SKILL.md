---
name: apk-pack
description: Use this skill when the user needs Android APK packaging for a uni-app/HBuilderX project. Prefer local offline packaging first (no cloud quota), with optional cloud fallback. This skill only handles packaging outputs and logs.
---

# APK Pack

## Overview

Use this skill to produce Android APK builds for uni-app projects.
Default strategy is local offline packaging to avoid cloud daily limits.

## Modes

- `local` (default):
  - `publish app-android --type appResource`
  - inject resources into offline project (`HBuilder-Integrate-AS`)
  - `gradlew :simpleDemo:assembleRelease`
- `cloud`:
  - `cli pack --platform android --android.androidpacktype 3`
- `auto`:
  - try local first, fallback to cloud on failure

## When To Use

- User asks to package/build Android APK for uni-app
- User wants reproducible package outputs/logs
- User needs cloud-limit-free packaging path

## Do Not Use For

- Device install / adb launch / runtime debugging
- Code fixes or test loops

## Inputs

- `project_path` (required)
- `package_name` (required)
- `mode` (optional): `local|cloud|auto`, default `local`
- `project_path/.apk_verify_tag` file (required for strict-verify script): first line is a unique string expected in exported `app-service.js`; local mode fails fast if missing
- `offline_project_path` (optional): existing `HBuilder-Integrate-AS` path
- `offline_sdk_zip_path` (optional): offline SDK zip; script can auto-extract
- `android_sdk_dir` (optional): default `D:\AndroidSDK`
- `hbuilderx_cli` (optional): default `D:\hanhan\HBuilderX\cli.exe`

## Script

```powershell
# Local first
powershell -ExecutionPolicy Bypass -File scripts/build_apk.ps1 -ProjectPath "D:\hanhan\app" -PackageName "com.chaoweisuanli.duomilu" -Mode local

# Local with strict export verification tag (recommended)
Set-Content -Path "D:\hanhan\app\.apk_verify_tag" -Value "SKY_TAG_20260426_01" -Encoding ascii
scripts\build_apk_verified.cmd "D:\hanhan\app" "com.chaoweisuanli.duomilu" "D:\hanhan\offline-pack\android-sdk-4.87\Android-SDK@4.87.82540_20251128\HBuilder-Integrate-AS"

# Auto fallback
powershell -ExecutionPolicy Bypass -File scripts/build_apk.ps1 -ProjectPath "D:\hanhan\app" -PackageName "com.chaoweisuanli.duomilu" -Mode auto
```

## Output Contract

- `status`: success|failed
- `mode_used`: local|cloud
- `pack_log_path`
- `local_apk_path` (if local success)
- `download_url` / `downloaded_apk_path` (if cloud success)
