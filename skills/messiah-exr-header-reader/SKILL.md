---
name: "messiah-exr-header-reader"
description: "Read key OpenEXR header attributes in the Messiah workflow, especially `depth_flag`, `MinDepth`, `MaxDepth`, `z_near`, and `z_far`, by compiling and running a tiny local OpenEXR probe against Messiah's bundled OpenEXR libraries. Use when a user wants to verify whether a recorded EXR frame was tagged correctly, inspect depth metadata for AOV/NBS debugging, or quickly check header values from files like `CharacterBoundDepth.exr`."
---

# Messiah EXR Header Reader

## When to use

Use this skill when the task is:

- inspect EXR header metadata from Messiah AOV outputs
- verify `depth_flag` on a specific frame
- compare `MinDepth` / `MaxDepth` / `z_near` / `z_far`
- check whether a recorded `CharacterBoundDepth.exr` was tagged correctly

Typical files:

- `*CharacterBoundDepth.exr`
- `*LosslessNonLinearDepth*.exr`

## Workflow

1. Run the probe script with the target `.exr` path.
2. Read the printed key attributes first.
3. If needed, rerun with `--json` for machine-readable output.

## Command

Plain text output:

```powershell
python C:\Users\zhangruojun\.codex\skills\messiah-exr-header-reader\scripts\read_exr_header.py "F:\74AOVOutput820_prez\1200CharacterBoundDepth.exr"
```

JSON output:

```powershell
python C:\Users\zhangruojun\.codex\skills\messiah-exr-header-reader\scripts\read_exr_header.py "F:\74AOVOutput820_prez\1200CharacterBoundDepth.exr" --json
```

## Notes

- The script uses Messiah's bundled OpenEXR headers and libs.
- It compiles a tiny helper once and reuses it on later runs.
- It builds inside the skill `.cache` directory and uses a lock file so parallel calls do not race on `probe.obj`.
- It decodes compiler output with UTF-8 and replacement fallback to avoid Windows codepage failures.
- If OpenEXR is not found in the default Messiah locations, pass `--openexr-root`.
