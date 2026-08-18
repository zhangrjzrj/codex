---
name: "ue-minimal-module-build"
description: "Build a specific Unreal Engine module with UBT using the smallest safe scope, usually for plugin/module-only C++ changes where Live Coding failed or should be avoided. Use when the user wants to compile a UE plugin/module without full-project rebuild, especially after XGE/IncrediBuild nested-job failures, Live Coding failures, or when only one module needs recompilation."
---

# UE Minimal Module Build

Use this skill to compile only the Unreal Engine module that matches the current code change, instead of triggering a full target rebuild.

## When to use

- The user changed C++ under one plugin or module.
- Live Coding failed or is risky.
- Full-project build is too slow or pulls unrelated modules into the build.
- The environment shows XGE/IncrediBuild nested-job failures.

## Core rule

Prefer a closed-editor module build with UBT and `-NoXGE`.

## Workflow

1. Identify the target module from the changed file path.
- `.../Source/<ModuleName>/...` usually means the module is `<ModuleName>`.
- Do not guess if the module name is ambiguous; read the nearest `.Build.cs`.

2. Identify the target.
- For editor plugin work, prefer `<ProjectName>Editor Win64 Development`.
- For runtime-only game builds, honor the user target if specified.

3. Close Unreal Editor before compiling.
- This avoids Live Coding state, file locks, and partial reload ambiguity.

4. Run UBT with the narrowest scope.
- Always prefer `-Module=<ModuleName>`.
- Default to `-NoXGE` to avoid nested distributed-build failures.
- Keep the build to one target/configuration unless the user explicitly asks for more.

5. Verify the result.
- Exit code must be zero.
- Check the newest module DLL timestamp when applicable.
- Summarize only actionable build errors if compilation failed.

## Command template

```powershell
powershell -ExecutionPolicy Bypass -File `
  C:\Users\zhangruojun\.codex\skills\ue-minimal-module-build\scripts\invoke_ue_minimal_module_build.ps1 `
  -ProjectRoot "F:\L46\L46_trunk\FortySix" `
  -Uproject "F:\L46\L46_trunk\FortySix\FortySix.uproject" `
  -Target "FortySixEditor" `
  -Platform "Win64" `
  -Configuration "Development" `
  -Module "NewBasisMediaCompositionEditor"
```

## Guardrails

- Do not switch to full-project build unless the user asks or module build is proven insufficient.
- Do not rely on Live Coding as the only path.
- Do not add `-NoXGE` only sometimes; default to it unless the user explicitly wants distributed build behavior.
- Keep reporting concrete target/module names and output artifacts.

## Why `-NoXGE` matters

In some environments, Live Coding or nested build entry points can trigger XGE/IncrediBuild from inside another distributed job. That causes the classic failure:

- `An Incredibuild distributed job cannot be started from within another distributed job.`

`-NoXGE` forces this build back to local execution and avoids that nested scheduler conflict.

## Resources

- `scripts/invoke_ue_minimal_module_build.ps1`: runs a narrow UBT module build and prints the most relevant output paths.
