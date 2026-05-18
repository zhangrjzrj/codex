---
name: messiah-nbs-encoder-runner
description: Build and run the local Messiah/NBS NBSEncoder from Codex. Use when the user asks to compile NBSEncoder, run NewBasisEncoder with the same Visual Studio debug parameters, encode a config.txt from F:\【GUI】NBSEncoder, batch-run config variants such as new_depth_dither_edge_dilate_px comparisons, or summarize NBS output sizes and encoder logs.
---

# Messiah NBS Encoder Runner

## Defaults

Use these paths unless the user gives different ones:

```text
Source repo:   E:\messiah_h74\Encoder\NBSEncoder
CMake build:   E:\messiah_h74\Encoder\build
Release exe:   E:\messiah_h74\Encoder\build\Release\NewBasisEncoder.exe
GUI workdir:   F:\【GUI】NBSEncoder
Main config:   F:\【GUI】NBSEncoder\config.txt
Output folder: F:\messiah_h74
```

The Visual Studio equivalent run settings are:

```text
Command:           $(TargetPath)
Command Arguments: config.txt
Working Directory: F:\【GUI】NBSEncoder
Configuration:     Release
Platform:          x64
```

## Workflow

1. Check whether `NewBasisEncoder` is already running. Stop it only when the user asks to restart/replace the run or when a build would overwrite the running exe.
2. Check repo status before code-changing operations:

```powershell
git -C 'E:\messiah_h74\Encoder\NBSEncoder' status --short --branch
```

3. Build Release:

```powershell
cmake --build 'E:\messiah_h74\Encoder\build' --config Release --target NewBasisEncoder
```

4. Run encoding from the GUI workdir:

```powershell
Start-Process -FilePath 'E:\messiah_h74\Encoder\build\Release\NewBasisEncoder.exe' `
  -ArgumentList 'config.txt' `
  -WorkingDirectory 'F:\【GUI】NBSEncoder' `
  -WindowStyle Hidden `
  -PassThru
```

For blocking runs where Codex should wait and collect logs, redirect console output to a per-run log:

```powershell
cd 'F:\【GUI】NBSEncoder'
& 'E:\messiah_h74\Encoder\build\Release\NewBasisEncoder.exe' 'config.txt' *> 'run_encoder.console.log'
```

## Batch Config Variants

Use the bundled script for repeated encode comparisons:

```powershell
& 'C:\Users\zhangruojun\.codex\skills\messiah-nbs-encoder-runner\scripts\run-nbs-encoder.ps1' `
  -Build `
  -BaseConfig 'F:\【GUI】NBSEncoder\config.txt' `
  -DilateValues 0,3,16,64,128,256 `
  -OutputPrefix 'F:/messiah_h74/820_test_dither_edge'
```

The script preserves the base config encoding by using Windows default ANSI, creates copied configs in the GUI workdir, runs each encode, writes `run_dither_dilate*.console.log`, and prints output sizes.

## Config Notes

For current depth dither comparisons, verify these keys:

```text
use_new_depth = 1
new_depth_fog_mode = 1
new_depth_dither = 1
new_depth_dither_edge_dilate_px = <radius>
```

`new_depth_dither_edge_dilate_px` is the edge-mask dilation radius in pixels:

```text
-1  = full allowed area, not limited to edge seeds
0   = seed/edge line only
3   = current default
16+ = wider edge band
256 = effectively saturated on the 100-200 test range seen so far
```

When editing `F:\【GUI】NBSEncoder\config.txt`, keep ANSI encoding. Prefer the bundled script or PowerShell `[System.Text.Encoding]::Default`; avoid converting the file to UTF-8.

## Reporting

After a run, summarize:

- Encoder version from console/log.
- Config path, start frame, frame count, output path.
- Exit code.
- NBS file size in bytes and MiB.
- Useful log lines such as `new_depth_dither_edge_dilate_px` and `Z10M: depth dither edge mask`.

Useful commands:

```powershell
Get-Item 'F:\messiah_h74\*.nbs' | Sort-Object LastWriteTime | Select Name,Length,LastWriteTime
Select-String -Path 'F:\【GUI】NBSEncoder\run*.console.log' -Pattern 'nbs encoder version|new_depth_dither_edge_dilate_px|Z10M: depth dither edge mask|nbs_file_path'
```

## Safety

Do not run `git add`, `git reset`, or `git restore --staged` unless the user explicitly asks. If a stash apply leaves `UU` but the file compiles, report that the content is resolved but the index was not marked resolved.
