---
name: "newbasis-wasm-browser-loop"
description: "Build, stage, serve, and browser-verify the NewBasis libnbs_c H5 WASM package on Windows. Use for NewBasis Web playback development, packaging verification, browser playback regression, SIMD/no-SIMD output checks, or iterative WASM fixes; do not treat the full C++ testcase WASM route as already working."
---

# Newbasis Wasm Browser Loop

## Goal

Close the verified `libnbs_c` H5 loop: Conan/Emscripten build, SIMD/no-SIMD output, stage, HTTP serve, Chromium playback, and evidence-based verdict.

Default workspace: `E:\messiah_h74\newbasis\sharestoreplus`.

## Workflow

1. Record `git log -1 --decorate --oneline`, branch containment, and dirty state.
2. Confirm Python, Conan, CMake, and port 8080.
3. Build and stage:

```powershell
python generate_libnbs_c_wasm.py all --strip=dwarf
```

4. If the default asset is missing, select an existing `.nbs` and rerun `stage --nbs <asset-name> --strip=dwarf`. Do not invent or download an asset without authorization.
5. Start `serve_h5.py` in the background, record its PID, and terminate only that PID after verification.
6. Use `web-browser-session` to open `http://localhost:8080/index.html` in Chromium.
7. Require runtime evidence: FPS greater than zero, advancing playback time, index/WASM HTTP 200, WASM MIME `application/wasm`, COOP `same-origin`, COEP `require-corp`, and nonempty SIMD/no-SIMD files.
8. Classify failures as environment, build, staging/resource, HTTP, WASM load, decode, or rendering; fix root causes only when source modification is authorized, then rebuild and repeat.

## Success Gate

Pass only when a freshly built package plays a real NBS in Chromium and playback time advances. Report commit, commands, asset, WASM sizes, headers, observed FPS/time, and limitations.

## Known Boundary

`generate_emscripten_ninja.py` is the separate full C++ testcase route. On baseline `80a86f35`, it fails in `python_runtime.cpp` because Windows-only conversion code and Tracy Zone macros are not isolated for Emscripten, and its wrapper does not propagate Ninja's nonzero exit code. Do not claim this route passes until fixed and rerun.

The verified H5 route is a playback component, not proof of Three.js/Godot integration or NBS depth-based 3D occlusion.

## Hygiene

Keep evidence in ignored directories; never stage build output. Search newly created business artifacts for prohibited automation identity strings before delivery.
