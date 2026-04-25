---
name: apk-pack
description: Use this skill when the user needs Android APK cloud packaging for a uni-app/HBuilderX project only. This skill focuses strictly on packaging and returning package artifacts and logs, and does not perform install, run, or debugging steps.
---

# APK Pack

## Overview

Use this skill to produce Android APK builds from a uni-app project through `HBuilderX cli.exe pack`.
This skill only handles packaging and packaging outputs.

## When To Use

- User asks to "打包 APK" / "自动打包" / "云打包"
- Project is a uni-app project with `manifest.json`
- You need a reproducible package command and build log output

## Do Not Use For

- Device install / adb launch / runtime debugging
- Code fix loops
- Logcat analysis

## Inputs

- `project_path` (required): absolute path to project root
- `package_name` (required): Android package name
- `hbuilderx_cli` (optional): defaults to `D:\hanhan\HBuilderX\cli.exe`
- `pack_type` (optional): `cloud` (default) or `custom`
  - `cloud` maps to `--android.androidpacktype 3`
  - `custom` maps to `--android.androidpacktype 0` and needs cert args

## Workflow

1. Validate `cli.exe` and `manifest.json` exist
2. Validate user is logged in (`cli user info`)
3. Run pack command
4. Return:
- raw build log
- parsed download URL if present
- local download path if downloaded

## Command Template

```powershell
& "$hbuilderx_cli" pack --project "$project_path" --platform android --android.packagename "$package_name" --android.androidpacktype 3
```

## Script

Run:

```powershell
pwsh -File scripts/build_apk.ps1 -ProjectPath "D:\hanhan\app" -PackageName "com.chaoweisuanli.duomilu"
```

## Output Contract

- `status`: success|failed
- `pack_log_path`
- `download_url` (if available)
- `downloaded_apk_path` (if available)
