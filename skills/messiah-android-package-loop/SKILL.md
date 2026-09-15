---
name: "messiah-android-package-loop"
description: "Build and verify a self-contained Messiah native Android APK from a clean worktree, including Package assembly, stale OBB cleanup, NativeActivity launch, Telnet control, and NBS playback acceptance."
---

# Messiah Android Package Loop

Use this for native Messiah Android. Do not route it through the uni-app APK skill.

## Acceptance target

A clean `nbs_dev` worktree must produce an APK which, after uninstall and fresh install, needs no manual resource repair and passes:

1. App stays alive and foreground.
2. Patch UI is visible without zlib resource errors, required Python module failures, shader asserts, or native crash errors.
3. Device binds `9113`; ADB forwarding yields the Messiah welcome prompt and Python echo.
4. The requested NBS exists at `Package/Videos/<name>.nbs`; `MiniGifNode` reaches `decoder >= 0` and `visible=True`.
5. Runtime logs and device-visible evidence are saved. On foldable/multi-display devices, do not reject user-visible playback solely because default `adb screencap` captured another display.

## Clean source

- Record branch, commit, commit time, dirty state, APK hash, and device serial.
- Create a new worktree at the requested commit; never copy the dirty source tree.
- Keep the Android build path short. On Windows, either create the worktree under a short root or map it with `subst` before Gradle/NDK build; the generated `jni/src/.../../..` PhysX paths can hit the 260-character boundary and surface as a false `No rule to make target` for an existing source file.
- Carry only proven generation/package changes. Exclude diagnostic logging and experimental ZZZ4 parsing.
- For Python Hybrid use arm64 and `use_game_activity=False`, retaining `MessiahNativeActivity`.
- Use the NDK version declared by generated Gradle. If absent, fail with that exact version rather than silently substituting another.

## Package assembly

Use one resource truth source: generated `assets/Package`.

1. Start with `assets/Package` extracted from the official Android APK for Android-compatible shaders/resources.
2. Overlay complete `Script`, `UIScript`, and `Videos` from the full application Package. These are application resources: Python gameplay/test-shell logic, Cocos UI resources, and media/NBS assets.
3. After overlay, restore official Android `UIScript/textureinfo.info`, `UIScript/plists`, and every plist referenced by that list.
4. Write `assets/assets.lst` with `Engine`, `netease_data`, and `Package`.
5. Run `scripts/prepare_package.ps1`; missing `Script/Python/main.py`, UI mapping files, or requested NBS is a hard failure.

Do not require MPK filtering or sharding for this loose Package route. Sharding belongs to a separate optional MPK mode.

## Build

1. Generate the arm64 Hybrid Android Studio project with NativeActivity.
2. If the worktree path is long, map the worktree to a short drive with `subst` and run Gradle from that drive.
3. Run `gradlew.bat clean :app:assembleDebug`. Clean is mandatory because stale multi-GB intermediates previously caused packaging `integer overflow`.
4. If `No rule to make target` names a file that exists, check the raw jni path length first; shorten the path before changing source or package contents.
5. Record APK existence, size, SHA-256, package/activity, ABI, min SDK, and target SDK.

## Device hygiene

1. Select an explicit device serial.
2. Uninstall `com.netease.messiah`, then verify its external data and OBB paths are gone.
3. If package OBB remains, record exact path/size and remove or isolate only that package-scoped file before install.
4. Install only the new APK and launch `com.netease.game.MessiahNativeActivity`.
5. Treat the Android old-target warning as a known first-launch notice caused by low target SDK, not NDK/ABI.
6. During final acceptance, never push missing Script/UI/video resources after install. Missing resources fail the package gate.

## Telnet and NBS

1. Confirm `Telnet Server Binded on Port 0.0.0.0:9113`.
2. Forward `tcp:9113` and require `Welcome to messiah server` plus `1+1 -> 2`.
3. Use packaged `Package/Videos/<name>.nbs`; record the resolved device path.
4. Android cannot open a Windows path passed to `telnet_exec.py --load-script`. Encode the local probe text as Base64 and send `exec(base64.b64decode(...))`; do not copy the probe or resources onto the device.
5. Create a `cc.MiniGifNode`, retain the node and callback state on `__main__`, attach it to the running scene, center it, and set content size. Query retained values through `__main__` in later Telnet connections.
6. Poll after async initialization; require `decoder >= 0`, `visible=True`, and an open-file log for the NBS.
7. Capture two separated frames or a short recording. If Vulkan/multi-display capture is black, record verified direct user observation as supplemental evidence.

## Failure routing

- `incorrect header check`: inspect stale OBB/resource precedence before changing Python.
- `ModuleNotFoundError` for required gameplay modules: complete Script is absent. If `MLauncher.aftercheck` reports missing optional `launcher` but then logs `essential filelist is okay -> enter main`, treat it as a known optional launcher probe and continue validating Patch UI plus Telnet/NBS.
- shader assert/missing `.binx`: Android Package baseline is wrong.
- packaging `integer overflow`: remove generated Gradle outputs and build clean.
- first-launch Surface crash around the old-target dialog: dismiss once and rerun with Surface logs; keep it separate from NBS compatibility.
- `telnet_exec.py` timeout while waiting for `AUTO_END`: if the captured console output already contains the requested marker and returns to `>>>`, verify state with a fresh Telnet query before classifying the command as failed.
