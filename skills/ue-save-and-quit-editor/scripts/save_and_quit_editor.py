import json

import unreal


def package_paths(packages):
    paths = []
    for package in packages:
        try:
            paths.append(package.get_path_name())
        except Exception:
            paths.append(str(package))
    return paths


def main():
    dirty_map_packages = list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    dirty_content_packages = list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    packages_to_save = dirty_map_packages + dirty_content_packages

    before = {
        "dirty_map_count": len(dirty_map_packages),
        "dirty_content_count": len(dirty_content_packages),
        "dirty_map_packages": package_paths(dirty_map_packages),
        "dirty_content_packages": package_paths(dirty_content_packages),
    }

    save_success = True
    if packages_to_save:
        save_success = unreal.EditorLoadingAndSavingUtils.save_packages(packages_to_save, False)

    remaining_map_packages = list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    remaining_content_packages = list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())

    after = {
        "remaining_dirty_map_count": len(remaining_map_packages),
        "remaining_dirty_content_count": len(remaining_content_packages),
        "remaining_dirty_map_packages": package_paths(remaining_map_packages),
        "remaining_dirty_content_packages": package_paths(remaining_content_packages),
    }

    result = {
        "save_success": bool(save_success),
        "before": before,
        "after": after,
        "will_quit": bool(
            save_success
            and not remaining_map_packages
            and not remaining_content_packages
        ),
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result["will_quit"]:
        unreal.SystemLibrary.quit_editor()
        return

    raise RuntimeError("Editor still has dirty packages or save failed; abort quit")


if __name__ == "__main__":
    main()
