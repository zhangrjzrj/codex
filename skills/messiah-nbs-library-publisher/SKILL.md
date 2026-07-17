---
name: "messiah-nbs-library-publisher"
description: "Publish a downloaded Messiah NBS library ZIP into a local messiah_develop engine tree by extracting libNewBasisDecoder, nbs_extend, and shared headers into their expected platform paths. Use when Codex needs to install a delivered NBS package into Messiah, verify destination mapping, or automate repeated NBS library publication."
---

# Messiah NBS Library Publisher

Use this skill to publish a downloaded NBS library ZIP into a local `messiah_develop` engine tree.

## What It Publishes

The bundled script publishes these artifacts from the ZIP:

- `libNewBasisDecoder`
- `nbs_extend`
- shared headers under `include/nbs/*.h`

Current destination coverage matches the verified local engine layout:

- Android
- iOS
- mac arm64
- Windows
- PS5

## Command

```powershell
python C:\Users\zhangruojun\.codex\skills\messiah-nbs-library-publisher\scripts\PublishNbsLibrary.py <zip_path> <engine_root> --ps5-variant 12
```

Example:

```powershell
python C:\Users\zhangruojun\.codex\skills\messiah-nbs-library-publisher\scripts\PublishNbsLibrary.py 'C:\Users\zhangruojun\Downloads\messiah-libNewBasisDecoder-1.0.3.3_15_2026-07-16_10-03-18.zip' 'F:\messiah_official\messiah_develop' --ps5-variant 13
```

Dry run:

```powershell
python C:\Users\zhangruojun\.codex\skills\messiah-nbs-library-publisher\scripts\PublishNbsLibrary.py <zip_path> <engine_root> --ps5-variant 13 --dry-run
```

## Parameters

- `zip_path`: downloaded NBS ZIP package
- `engine_root`: Messiah engine root such as `F:\messiah_official\messiah_develop`
- `--ps5-variant 12|13`: required because PS5-12 and PS5-13 publish into the same target paths
- `--dry-run`: print copy plan without writing files

## Important Notes

- The ZIP may contain hash-suffixed package directories; the script matches by stable directory prefix, not by full fixed folder name.
- `mac` x86 payload may exist in the ZIP, but the verified current engine consumer path is `mac/arm64`; the script does not publish an unused `mac` x86 target.
- PS5-12 and PS5-13 overwrite the same destination files, so only one variant can be active in the engine tree at a time.
- The script expects the engine tree to contain:
  - `Engine/Sources/External/miniGif`
  - `Engine/Sources/External/nbsextend`
