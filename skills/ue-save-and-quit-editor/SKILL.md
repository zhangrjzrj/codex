---
name: "ue-save-and-quit-editor"
description: "Save all dirty Unreal Editor map and content packages, verify the editor is clean, and then quit Unreal Editor cleanly. Use when Codex needs to close UE Editor without getting blocked by the save-confirmation dialog."
---

# UE Save And Quit Editor

## Overview

Use this skill to close Unreal Editor through the normal editor path:

```text
save all dirty packages
-> verify no dirty packages remain
-> quit editor
```

This skill is for the common automation blocker where `unreal.SystemLibrary.quit_editor()` gets intercepted by the unsaved-changes dialog.

Do not use this skill when the user explicitly wants to discard unsaved changes. This skill saves first.

## Workflow

1. Run the bundled Python script inside Unreal Editor.
2. Collect dirty map packages and dirty content packages.
3. Save all dirty packages without prompting per package.
4. Re-check whether any dirty packages remain.
5. Quit Unreal Editor only if the editor is clean.

If saving fails, or dirty packages remain after save, stop and report the remaining package list instead of trying to force-close the editor.

## Script

The bundled script is:

```text
scripts/save_and_quit_editor.py
```

It is intended to run through the same Unreal Python execution path already used by the project.

## Expected Result

- all dirty packages are saved
- the script prints a machine-readable JSON summary
- `unreal.SystemLibrary.quit_editor()` is only called when no dirty packages remain

## Guardrails

- Do not replace this workflow with a hard kill.
- Do not silently ignore failed saves.
- Do not use this skill for discard-and-quit scenarios.
