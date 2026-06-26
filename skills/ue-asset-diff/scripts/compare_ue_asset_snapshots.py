import json
import sys
from pathlib import Path


def load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def index_by(items, key):
    return {item[key]: item for item in items}


def compare_world(left, right):
    left_actors = index_by(left["actors"], "label")
    right_actors = index_by(right["actors"], "label")
    left_keys = set(left_actors)
    right_keys = set(right_actors)

    report = {
        "left_only_actors": sorted(left_keys - right_keys),
        "right_only_actors": sorted(right_keys - left_keys),
        "changed_actors": [],
    }

    for label in sorted(left_keys & right_keys):
        la = left_actors[label]
        ra = right_actors[label]
        changed_fields = {}
        for field in ("class", "tags", "hidden_in_game", "location", "rotation", "scale"):
            if la[field] != ra[field]:
                changed_fields[field] = {"left": la[field], "right": ra[field]}
        if changed_fields:
            report["changed_actors"].append({"label": label, "fields": changed_fields})
    return report


def compare_sequence(left, right):
    left_bindings = index_by(left["bindings"], "name")
    right_bindings = index_by(right["bindings"], "name")
    left_keys = set(left_bindings)
    right_keys = set(right_bindings)

    report = {
        "left_only_bindings": sorted(left_keys - right_keys),
        "right_only_bindings": sorted(right_keys - left_keys),
        "changed_bindings": [],
        "master_tracks_changed": left["master_tracks"] != right["master_tracks"],
    }

    for name in sorted(left_keys & right_keys):
        lb = left_bindings[name]
        rb = right_bindings[name]
        if lb["tracks"] != rb["tracks"]:
            report["changed_bindings"].append(
                {
                    "name": name,
                    "left_tracks": lb["tracks"],
                    "right_tracks": rb["tracks"],
                }
            )
    return report


def main():
    if len(sys.argv) != 4:
        raise SystemExit("Usage: compare_ue_asset_snapshots.py left.json right.json out.json")

    left_path, right_path, out_path = [Path(arg) for arg in sys.argv[1:4]]
    left = load_json(left_path)
    right = load_json(right_path)

    if left["asset_type"] != right["asset_type"]:
        raise SystemExit("Snapshot types do not match")

    if left["asset_type"] == "World":
        report = compare_world(left, right)
    elif left["asset_type"] == "LevelSequence":
        report = compare_sequence(left, right)
    else:
        raise SystemExit(f"Unsupported snapshot type: {left['asset_type']}")

    payload = {
        "left": str(left_path),
        "right": str(right_path),
        "asset_type": left["asset_type"],
        "report": report,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=2, sort_keys=True)
    print(f"UE_ASSET_DIFF_WRITTEN {out_path}")


main()
