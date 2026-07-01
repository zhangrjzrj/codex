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


def compare_lists(left, right, key):
    left_items = index_by(left, key)
    right_items = index_by(right, key)
    left_keys = set(left_items)
    right_keys = set(right_items)
    changed = []

    for item_key in sorted(left_keys & right_keys):
        if left_items[item_key] != right_items[item_key]:
            changed.append(
                {
                    key: item_key,
                    "left": left_items[item_key],
                    "right": right_items[item_key],
                }
            )

    return {
        "left_only": sorted(left_keys - right_keys),
        "right_only": sorted(right_keys - left_keys),
        "changed": changed,
    }


def compare_node_fields(left_node, right_node):
    changed_fields = {}
    for field in ("class", "title", "properties", "input_pins", "output_pins"):
        if left_node.get(field) != right_node.get(field):
            changed_fields[field] = {
                "left": left_node.get(field),
                "right": right_node.get(field),
            }
    return changed_fields


def compare_movie_graph(left, right):
    left_nodes = index_by(left["nodes"], "name")
    right_nodes = index_by(right["nodes"], "name")
    left_node_names = set(left_nodes)
    right_node_names = set(right_nodes)
    changed_nodes = []

    for name in sorted(left_node_names & right_node_names):
        changed_fields = compare_node_fields(left_nodes[name], right_nodes[name])
        if changed_fields:
            changed_nodes.append({"name": name, "fields": changed_fields})

    return {
        "inputs": compare_lists(left.get("inputs", []), right.get("inputs", []), "name"),
        "outputs": compare_lists(left.get("outputs", []), right.get("outputs", []), "name"),
        "variables": compare_lists(left.get("variables", []), right.get("variables", []), "name"),
        "branches_changed": left.get("branches", []) != right.get("branches", []),
        "branch_nodes_changed": left.get("branch_nodes", {}) != right.get("branch_nodes", {}),
        "left_only_nodes": sorted(left_node_names - right_node_names),
        "right_only_nodes": sorted(right_node_names - left_node_names),
        "changed_nodes": changed_nodes,
        "edges_changed": left.get("edges", []) != right.get("edges", []),
        "left_edges": left.get("edges", []),
        "right_edges": right.get("edges", []),
    }


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
    elif left["asset_type"] == "MovieGraphConfig":
        report = compare_movie_graph(left, right)
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
