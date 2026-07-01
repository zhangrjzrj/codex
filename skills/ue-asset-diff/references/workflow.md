# Workflow

1. Use `scripts/export_ue_asset_snapshot.py` through `UnrealEditor-Cmd.exe -ExecutePythonScript=...`.
2. Set `UE_ASSET_PATH` to a `World`, `LevelSequence`, or `MovieGraphConfig` / MRG asset path.
3. Set `UE_ASSET_SNAPSHOT_OUT` to an ignored local JSON output path.
4. For worlds, optionally set `UE_ASSET_MAP_PATH` to the same map path to ensure the level is loaded before actor enumeration.
5. Run the export once per project copy.
6. Compare the two JSON snapshots with `scripts/compare_ue_asset_snapshots.py`.
7. Summarize only meaningful semantic differences:
   - world: actor add/remove, tags, hidden state, transform
   - level sequence: binding add/remove, track structure, master tracks
   - movie graph: graph inputs/outputs/variables, branches, nodes, pin connections, exported node properties

Use this workflow when binary `.umap` / `.uasset` files need stable diffs that Git cannot show directly.
