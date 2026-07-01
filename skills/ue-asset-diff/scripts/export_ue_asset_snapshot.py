import json
import os

import unreal


DEFAULT_MAP_PATH = "/Game/Modern_Gas_Station/Maps/Demo_Day"


def load_config():
    config_path = os.environ.get("UE_ASSET_SNAPSHOT_CONFIG")
    if config_path:
        with open(config_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return (
            data["asset_path"],
            data["output_path"],
            data.get("map_path", DEFAULT_MAP_PATH),
        )
    return (
        os.environ["UE_ASSET_PATH"],
        os.environ["UE_ASSET_SNAPSHOT_OUT"],
        os.environ.get("UE_ASSET_MAP_PATH", DEFAULT_MAP_PATH),
    )


ASSET_PATH, OUTPUT_PATH, MAP_PATH = load_config()


def normalize_value(value):
    if value is None:
        return None
    if isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, unreal.Name):
        return str(value)
    if isinstance(value, unreal.Text):
        return str(value)
    if isinstance(value, unreal.Array):
        return [normalize_value(v) for v in value]
    if isinstance(value, list):
        return [normalize_value(v) for v in value]
    if isinstance(value, tuple):
        return [normalize_value(v) for v in value]
    if hasattr(value, "get_path_name"):
        try:
            return value.get_path_name()
        except Exception:
            pass
    return str(value)


def call_noarg(obj, method_name, default=None):
    method = getattr(obj, method_name, None)
    if not callable(method):
        return default
    try:
        return method()
    except Exception:
        return default


def get_object_class_name(obj):
    if not obj:
        return ""
    try:
        return obj.get_class().get_name()
    except Exception:
        return obj.__class__.__name__


def get_object_name(obj):
    if not obj:
        return ""
    for method_name in ("get_name", "get_fname"):
        value = call_noarg(obj, method_name)
        if value is not None:
            return str(value)
    try:
        return obj.get_path_name().split(".")[-1]
    except Exception:
        return str(obj)


def get_node_title(node):
    for descriptive in (True, False):
        try:
            return str(node.get_node_title(descriptive))
        except Exception:
            pass
    return get_object_name(node)


def get_member_name(member):
    return call_noarg(member, "get_member_name", get_object_name(member))


def get_pin_label(pin):
    for attr in ("label", "Label", "name", "Name"):
        try:
            return str(getattr(pin, attr))
        except Exception:
            pass
    for method_name in ("get_label", "get_name"):
        value = call_noarg(pin, method_name)
        if value is not None:
            return str(value)
    return str(pin)


def get_pin_direction(pin):
    value = None
    for attr in ("direction", "Direction"):
        try:
            value = getattr(pin, attr)
            break
        except Exception:
            pass
    return str(value) if value is not None else ""


def export_pin(pin):
    connected = []
    get_connected = getattr(pin, "get_all_connected_pins", None)
    if callable(get_connected):
        try:
            for connected_pin in get_connected():
                connected_node = call_noarg(connected_pin, "get_owning_node")
                connected.append(
                    {
                        "node": get_object_name(connected_node),
                        "node_class": get_object_class_name(connected_node),
                        "pin": get_pin_label(connected_pin),
                    }
                )
        except Exception:
            connected = []
    connected.sort(key=lambda item: (item["node"], item["pin"]))
    return {
        "label": get_pin_label(pin),
        "direction": get_pin_direction(pin),
        "connected": connected,
    }


def export_node_pins(node, method_name):
    method = getattr(node, method_name, None)
    if not callable(method):
        return []
    try:
        pins = [export_pin(pin) for pin in method()]
    except Exception:
        return []
    pins.sort(key=lambda item: item["label"])
    return pins


def property_should_export(prop_name):
    if not prop_name:
        return False
    if prop_name.startswith("bOverride_"):
        return True
    excluded = {
        "object_flags",
        "outer",
        "class",
    }
    return prop_name not in excluded


def export_object_properties(obj):
    properties = {}
    for prop_name in dir(obj):
        if prop_name.startswith("_") or not property_should_export(prop_name):
            continue
        try:
            value = getattr(obj, prop_name)
        except Exception:
            continue
        if callable(value):
            continue
        if prop_name in ("input_pins", "output_pins"):
            continue
        normalized = normalize_value(value)
        if isinstance(normalized, str) and normalized.startswith("<"):
            continue
        if normalized in (None, "", [], {}):
            continue
        properties[prop_name] = normalized
    return properties


def export_actor(actor):
    location = actor.get_actor_location()
    rotation = actor.get_actor_rotation()
    scale = actor.get_actor_scale3d()
    return {
        "label": actor.get_actor_label(),
        "class": actor.get_class().get_name(),
        "path": actor.get_path_name(),
        "tags": sorted(str(tag) for tag in actor.tags),
        "hidden_in_game": bool(actor.hidden),
        "location": [round(location.x, 4), round(location.y, 4), round(location.z, 4)],
        "rotation": [round(rotation.roll, 4), round(rotation.pitch, 4), round(rotation.yaw, 4)],
        "scale": [round(scale.x, 4), round(scale.y, 4), round(scale.z, 4)],
    }


def export_world_snapshot():
    if not unreal.EditorLevelLibrary.load_level(MAP_PATH):
        raise RuntimeError(f"Failed to load map: {MAP_PATH}")

    actors = [export_actor(actor) for actor in unreal.EditorLevelLibrary.get_all_level_actors()]
    actors.sort(key=lambda item: item["label"])
    return {
        "asset_path": ASSET_PATH,
        "asset_type": "World",
        "map_path": MAP_PATH,
        "actor_count": len(actors),
        "actors": actors,
    }


def export_track(track):
    sections = []
    try:
        for section in track.get_sections():
            entry = {
                "class": section.get_class().get_name(),
                "range": str(section.get_range()),
            }
            if hasattr(section, "get_shot_display_name"):
                try:
                    entry["shot_display_name"] = str(section.get_shot_display_name())
                except Exception:
                    pass
            sections.append(entry)
    except Exception:
        pass
    return {
        "class": track.get_class().get_name(),
        "display_name": str(track.get_display_name()) if hasattr(track, "get_display_name") else "",
        "sections": sections,
    }


def export_binding(binding):
    tracks = []
    try:
        tracks = [export_track(track) for track in binding.get_tracks()]
    except Exception:
        pass
    tracks.sort(key=lambda item: (item["class"], item["display_name"]))
    return {
        "name": str(binding.get_display_name()),
        "id": str(binding.get_id()),
        "tracks": tracks,
    }


def export_sequence_snapshot(sequence):
    movie_scene = sequence.get_movie_scene()
    bindings = [export_binding(binding) for binding in sequence.get_bindings()]
    bindings.sort(key=lambda item: item["name"])
    get_master_tracks = getattr(movie_scene, "get_master_tracks", None)
    if callable(get_master_tracks):
        raw_master_tracks = get_master_tracks()
    else:
        raw_master_tracks = []
    master_tracks = [export_track(track) for track in raw_master_tracks]
    master_tracks.sort(key=lambda item: (item["class"], item["display_name"]))
    get_display_rate = getattr(movie_scene, "get_display_rate", None)
    get_tick_resolution = getattr(movie_scene, "get_tick_resolution", None)
    get_playback_range = getattr(movie_scene, "get_playback_range", None)
    return {
        "asset_path": ASSET_PATH,
        "asset_type": "LevelSequence",
        "display_rate": str(get_display_rate()) if callable(get_display_rate) else "",
        "tick_resolution": str(get_tick_resolution()) if callable(get_tick_resolution) else "",
        "playback_range": str(get_playback_range()) if callable(get_playback_range) else "",
        "binding_count": len(bindings),
        "bindings": bindings,
        "master_tracks": master_tracks,
    }


def export_movie_graph_members(graph):
    inputs = []
    outputs = []
    variables = []
    get_inputs = getattr(graph, "get_inputs", None)
    get_outputs = getattr(graph, "get_outputs", None)
    get_variables = getattr(graph, "get_variables", None)

    if callable(get_inputs):
        inputs = [{"name": get_member_name(item), "class": get_object_class_name(item)} for item in get_inputs()]
    if callable(get_outputs):
        outputs = [{"name": get_member_name(item), "class": get_object_class_name(item)} for item in get_outputs()]
    if callable(get_variables):
        try:
            raw_variables = get_variables(True)
        except TypeError:
            raw_variables = get_variables()
        variables = [
            {
                "name": get_member_name(item),
                "class": get_object_class_name(item),
                "properties": export_object_properties(item),
            }
            for item in raw_variables
        ]

    inputs.sort(key=lambda item: item["name"])
    outputs.sort(key=lambda item: item["name"])
    variables.sort(key=lambda item: item["name"])
    return inputs, outputs, variables


def export_movie_graph_node(node):
    return {
        "name": get_object_name(node),
        "class": get_object_class_name(node),
        "title": get_node_title(node),
        "path": normalize_value(node),
        "properties": export_object_properties(node),
        "input_pins": export_node_pins(node, "get_input_pins"),
        "output_pins": export_node_pins(node, "get_output_pins"),
    }


def export_movie_graph_edges(nodes):
    edges = set()
    for node in nodes:
        node_name = get_object_name(node)
        for pin in export_node_pins(node, "get_output_pins"):
            from_pin = pin["label"]
            for connected in pin["connected"]:
                edges.add(
                    (
                        node_name,
                        from_pin,
                        connected["node"],
                        connected["pin"],
                    )
                )
    return [
        {
            "from_node": from_node,
            "from_pin": from_pin,
            "to_node": to_node,
            "to_pin": to_pin,
        }
        for from_node, from_pin, to_node, to_pin in sorted(edges)
    ]


def export_movie_graph_snapshot(graph):
    inputs, outputs, variables = export_movie_graph_members(graph)

    nodes_by_name = {}
    for endpoint_method in ("get_input_node", "get_output_node"):
        endpoint = call_noarg(graph, endpoint_method)
        if endpoint:
            nodes_by_name[get_object_name(endpoint)] = endpoint

    branch_names = []
    get_branch_names = getattr(graph, "get_branch_names", None)
    if callable(get_branch_names):
        try:
            branch_names = [str(name) for name in get_branch_names()]
        except Exception:
            branch_names = []

    branch_nodes = {}
    get_nodes_for_branch = getattr(graph, "get_nodes_for_branch", None)
    if callable(get_nodes_for_branch):
        try:
            node_class = unreal.MovieGraphNode
        except Exception:
            node_class = unreal.Object
        for branch_name in branch_names:
            try:
                raw_nodes = get_nodes_for_branch(node_class, unreal.Name(branch_name), False)
            except Exception:
                raw_nodes = []
            branch_node_names = []
            for node in raw_nodes:
                node_name = get_object_name(node)
                nodes_by_name[node_name] = node
                branch_node_names.append(node_name)
            branch_nodes[branch_name] = sorted(set(branch_node_names))

    nodes = [export_movie_graph_node(node) for _, node in sorted(nodes_by_name.items())]
    return {
        "asset_path": ASSET_PATH,
        "asset_type": "MovieGraphConfig",
        "inputs": inputs,
        "outputs": outputs,
        "variables": variables,
        "branches": sorted(branch_names),
        "branch_nodes": branch_nodes,
        "node_count": len(nodes),
        "nodes": nodes,
        "edges": export_movie_graph_edges(list(nodes_by_name.values())),
    }


def main():
    asset = unreal.load_asset(ASSET_PATH)
    if not asset:
        raise RuntimeError(f"Failed to load asset: {ASSET_PATH}")

    if isinstance(asset, unreal.World):
        payload = export_world_snapshot()
    elif isinstance(asset, unreal.LevelSequence):
        payload = export_sequence_snapshot(asset)
    elif get_object_class_name(asset) == "MovieGraphConfig":
        payload = export_movie_graph_snapshot(asset)
    else:
        raise RuntimeError(f"Unsupported asset type: {asset.get_class().get_name()}")

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=2, sort_keys=True)
    print("UE_ASSET_SNAPSHOT_WRITTEN", OUTPUT_PATH)


main()
