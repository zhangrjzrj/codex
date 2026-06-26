---
name: "ue-asset-diff"
description: "Export Unreal Engine World and LevelSequence assets into normalized JSON snapshots and compare baseline vs current project copies. Use when Codex needs semantic diffs for .umap or .uasset content such as actor add/remove, tag or hidden-state changes, transform drift, sequence binding changes, or MRQ/scene investigations where Git binary diffs are insufficient."
---

# Ue Asset Diff

Use this skill when `.umap` / `.uasset` binary diffs are not enough and you need a stable, semantic comparison.

## Workflow

1. Read [references/workflow.md](references/workflow.md) once if you need the full procedure.
2. Export one snapshot per project copy with `scripts/export_ue_asset_snapshot.py`.
3. Compare the snapshots with `scripts/compare_ue_asset_snapshots.py`.
4. Summarize only meaningful deltas.

## Export

Run the export through `UnrealEditor-Cmd.exe -ExecutePythonScript=...`.

Required environment variables:

- `UE_ASSET_PATH`: Unreal asset path such as `/Game/Modern_Gas_Station/Maps/Demo_Day`
- `UE_ASSET_SNAPSHOT_OUT`: output JSON path

Optional:

- `UE_ASSET_MAP_PATH`: map path to load before world export; defaults to `Demo_Day`

Supported asset types:

- `World`
- `LevelSequence`

Current snapshot contents:

- `World`: actor label, class, path, tags, hidden flag, transform
- `LevelSequence`: bindings, tracks, sections, master tracks, display rate, tick resolution

## Compare

Use `scripts/compare_ue_asset_snapshots.py left.json right.json out.json`.

Interpretation rules:

- `left_only_actors` / `right_only_actors`: actor add-remove drift
- `changed_actors`: same actor label but different tags, hidden flag, or transform
- `left_only_bindings` / `right_only_bindings`: sequence binding drift
- `changed_bindings`: same binding name but different track structure

## Notes

- Prefer ignored local output directories for snapshots and diffs.
- Treat this skill as semantic inspection, not exact binary serialization.
- For scene regressions, export the map and the controlling sequence together.
