---
name: "messiah-nbs-playback-smoke"
description: "Run Messiah NBS playback smoke tests by platform/configuration, starting with Windows Hybrid and Windows Release on messiah_develop. Use when Codex needs to generate, build, launch, inject an NBS playback probe, and judge pass/fail from marker and runtime logs."
---

# Messiah NBS Playback Smoke

Use this skill to run NBS playback smoke tests against a local Messiah engine tree.

## Supported Branches

Current supported branches:

- `windows hybrid`
- `windows release`

Each branch follows the same high-level loop:

```text
generate project
-> compile
-> launch client
-> inject NBS playback probe
-> read marker/log
-> decide pass/fail
```

## Required Inputs

- engine root, for example `F:\messiah_official\messiah_develop`
- branch:
  - `windows hybrid`
  - `windows release`
- NBS resource root that contains `Videos\H74.nbs`

Recommended Windows resource root used in current verification:

```text
F:\messiah_official\testSDK\Package_ui
```

## Generate Step

Windows Hybrid:

```powershell
cmd /c F:\messiah_official\messiah_develop\DevScript\GenerateWin64Editor.bat
```

Windows Release:

```powershell
cmd /c F:\messiah_official\messiah_develop\DevScript\GenerateWin64Release.bat --no-pause
```

## Release Config Cook Prerequisite

Windows Release depends on cooked config `bin` files, not only source `xml`.

Before first `windows release` launch, verify these files exist:

```text
<engine_root>\Engine\Config\Platform.bin
<engine_root>\Patch\Config\Platform.bin
```

If they are missing, cook config first:

```powershell
cmd /c F:\messiah_official\messiah_develop\DevScript\ChefConfig.bat
```

Expected result after cook:

- `Engine\Config\*.bin` exists
- `Patch\Config\*.bin` exists
- at minimum, `Platform.bin` exists in both locations

Reason:

- the original `windows release` crash before NBS playback was caused by missing cooked config bins
- after running `ChefConfig.bat`, `Platform` config loads successfully and the old `PlatformSettings::Apply()` null crash disappears

## Compile Step

Use the existing Messiah IncrediBuild path and switch config explicitly.

Windows Hybrid:

```powershell
python F:\messiah_official\messiah_develop\DevScript\IncrediBuild.py --projects Messiah --config Hybrid --live
```

Windows Release:

```powershell
python F:\messiah_official\messiah_develop\DevScript\IncrediBuild.py --projects Messiah --config Release --live
```

## Launch And Probe

The bundled probe script injects a `cc.MiniGifNode` that loads:

```text
Videos/H74.nbs
```

The probe writes marker lines under:

```text
<engine_root>\.codex-build\nbs_attach_running_scene.marker.txt
```

Pass condition for current Windows branches:

- marker contains `start-cb time=... frames=...`

## Important Notes

- `GenerateWin64Editor.bat` is the verified Windows Hybrid generate path.
- `GenerateWin64Release.bat` is the verified Windows Release generate path.
- Do not reuse Hybrid generate output when validating Release.
- Current probe assumes the runtime path root contains `Videos\H74.nbs`; for the verified path, launch with:
  - `--python-args=nopatch;console=1;path=..\..\..\testSDK\Package_ui`
- Telnet control uses port `9113` and falls back to the latest `ClientLog` if needed.
