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


def main():
    asset = unreal.load_asset(ASSET_PATH)
    if not asset:
        raise RuntimeError(f"Failed to load asset: {ASSET_PATH}")

    if isinstance(asset, unreal.World):
        payload = export_world_snapshot()
    elif isinstance(asset, unreal.LevelSequence):
        payload = export_sequence_snapshot(asset)
    else:
        raise RuntimeError(f"Unsupported asset type: {asset.get_class().get_name()}")

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=2, sort_keys=True)
    print("UE_ASSET_SNAPSHOT_WRITTEN", OUTPUT_PATH)


main()
