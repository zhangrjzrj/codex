# Verified Messiah Public Develop iOS Flow

## 1. Fixed verified values

- SSH alias: `mac-h74`
- Mac user: `game-netease`
- Bundle identifier: `com.netease.technicalcenter`
- Team: `S3NPTV6S84`
- Provisioning profile: `profile5test`
- Development identity fingerprint: `FEBBFCEF2905FD673C85B667231DFC180961F1F5`
- CoreDevice identifier: `11E6D8F3-8AF5-5A99-BFC3-B5AE7759A13B`
- Device UDID: `00008110-001A5C1226B8401E`
- Telnet mapping: `127.0.0.1:19113 → device:9113`
- iproxy binary: `/opt/homebrew/Cellar/libusbmuxd/2.1.1/bin/iproxy`

Discover current identifiers again before using these values on another Mac or device.

## 2. Locate the public integrated commit

Fetch public develop and locate the merge/integration commit by title, issue, version, or changed library path. Record:

- exact commit;
- parent commit for A/B;
- changed files;
- current `origin/develop` head.

Create an isolated worktree instead of mutating an existing sample workspace:

```bash
git worktree add -b j-ios-<version> \
  /Users/game-netease/Desktop/messiah_develop_ios_<version> \
  <integrated-commit>
```

## 3. Materialize LFS inputs

Ensure Homebrew Git LFS is visible from SSH:

```bash
export PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
git lfs version
```

Pull at least the iOS NBS archive and every other iOS framework/library referenced by the generated project. Verify large inputs are not pointer text:

```bash
file Engine/Sources/External/miniGif/lib/ios/arm64/release/libNewBasisDecoder.a
```

Expected: a real `ar archive`, not a Git LFS pointer.

When build errors expose another LFS pointer, materialize the responsible input rather than patching the build command.

## 4. Prepare packaged resources

The verified develop worktree required:

```text
MpkCooked/Resources.mpk
MpkCooked/Resources.mpkinfo
```

Copy them from the known-good sample only when source generation does not produce them. Record SHA-256 for source and destination so the copied package remains auditable.

## 5. Generate the iOS project

Generate with the verified bundle identifier:

```bash
python3 BuildMessiah.py ios \
  monolithic=0 build_core=1 armv7=0 armv7s=0 \
  override_pymalloc=0 clip_pre_pass=1 NaviRecast=1 Loader=0 \
  TestCase=0 Presenter=0 Shaderman=0 FbxRemoteImport=0 \
  occlus=True enable_stat=1 \
  bundleIdentifier=com.netease.technicalcenter \
  tracy_profile_memory=1 enable_profile=1 MagicSniffer=1 \
  use_fixmath=1 ImGui=1 AR=1 Customization=1 \
  open_record=1 NativeMedia=1
```

Save generation output to `.j-evidence/generate_ios.log`. Confirm the generated project contains `PRODUCT_BUNDLE_IDENTIFIER = com.netease.technicalcenter`.

## 6. Provision an SSH-capable signing keychain

Use a dedicated keychain rather than the GUI login keychain. The one-time setup requires a p12 exported with its private key. Keep all passwords on the Mac.

Verified paths:

```text
/Users/game-netease/Desktop/ios_signing/build_reimport.keychain-db
/Users/game-netease/.ios_ci_keychain_pass
/Users/game-netease/Desktop/ios_signing/run_hybrid_gui.sh
```

Protect the password file with mode `600`. Never print it. The keychain must contain the target identity and have the `apple-tool:,apple:,codesign:` partition list.

The verified minimal stable route keeps the external flow unchanged and moves keychain preparation into the build script itself. `run_hybrid_gui.sh` must:

- read the password from `~/.ios_ci_keychain_pass`;
- `security unlock-keychain` the dedicated build keychain;
- run `security set-keychain-settings -lut 21600`;
- run `security set-key-partition-list -S apple-tool:,apple:,codesign:`.

Before a build, the equivalent preparation is:

```bash
CI_KEYCHAIN=/Users/game-netease/Desktop/ios_signing/build_reimport.keychain-db
security unlock-keychain -p "$(cat "$HOME/.ios_ci_keychain_pass")" "$CI_KEYCHAIN"
security set-keychain-settings -lut 21600 "$CI_KEYCHAIN"
security set-key-partition-list \
  -S apple-tool:,apple:,codesign: \
  -s \
  -k "$(cat "$HOME/.ios_ci_keychain_pass")" \
  "$CI_KEYCHAIN"
```

Run a disposable framework probe first:

```bash
codesign --force --verbose=4 \
  --sign FEBBFCEF2905FD673C85B667231DFC180961F1F5 \
  --keychain "$CI_KEYCHAIN" \
  --timestamp=none \
  /tmp/j_sign_probe.framework

codesign --verify --deep --strict --verbose=4 \
  /tmp/j_sign_probe.framework
```

Do not run the full build until this probe passes.

## 7. Build and sign Hybrid

Run the long build remotely in the background and save PID/log. For the verified minimal route, prefer the wrapper script so the caller does not need extra signing steps:

```bash
/bin/bash /Users/game-netease/Desktop/ios_signing/run_hybrid_gui.sh
```

The wrapper currently expands to:

```bash
CI_KEYCHAIN=/Users/game-netease/Desktop/ios_signing/build_reimport.keychain-db
xcodebuild \
  -project Engine/Intermediate/Messiah-iOS.xcodeproj \
  -scheme Game \
  -configuration Hybrid \
  -destination 'generic/platform=iOS' \
  CODE_SIGN_STYLE=Manual \
  DEVELOPMENT_TEAM=S3NPTV6S84 \
  PROVISIONING_PROFILE_SPECIFIER=profile5test \
  CODE_SIGN_IDENTITY=FEBBFCEF2905FD673C85B667231DFC180961F1F5 \
  OTHER_CODE_SIGN_FLAGS="--keychain $CI_KEYCHAIN" \
  build
```

Pass requires `** BUILD SUCCEEDED **` in the saved log.

## 8. Verify Game.app

The verified product path was:

```text
Engine/Binaries/IOS/Hybrid-iphoneos/Game.app
```

Confirm it from the build log before use. Gate with:

```bash
codesign --verify --deep --strict --verbose=2 Game.app
codesign -dvv Game.app
codesign -d --entitlements :- Game.app
```

Expected:

```text
Identifier=com.netease.technicalcenter
TeamIdentifier=S3NPTV6S84
application-identifier=S3NPTV6S84.com.netease.technicalcenter
```

Verify every embedded framework as well.

## 9. Install and prove registration

```bash
xcrun devicectl device install app \
  --device 11E6D8F3-8AF5-5A99-BFC3-B5AE7759A13B \
  Engine/Binaries/IOS/Hybrid-iphoneos/Game.app
```

Immediately query:

```bash
xcrun devicectl device info apps \
  --device 11E6D8F3-8AF5-5A99-BFC3-B5AE7759A13B \
  --bundle-id com.netease.technicalcenter
```

Do not launch until `Game` appears in the app list.

## 10. Stage the NBS asset

Do not assume the app bundle or `Resources.mpk` contains the test NBS. Stage the exact file into the app data container after installation:

```bash
NBS_SOURCE=/absolute/path/to/horror.nbs
STAGE=/tmp/j_ios_nbs_payload
rm -rf "$STAGE"
mkdir -p "$STAGE/Videos"
cp "$NBS_SOURCE" "$STAGE/Videos/horror.nbs"

xcrun devicectl device copy to \
  --device 11E6D8F3-8AF5-5A99-BFC3-B5AE7759A13B \
  --domain-type appDataContainer \
  --domain-identifier com.netease.technicalcenter \
  --source "$STAGE/Videos" \
  --destination Documents/LocalData/Videos
```

This must produce:

```text
Documents/LocalData/Videos/horror.nbs
```

Pull the file or its parent directory back with `devicectl device copy from`. Compare byte size and SHA-256 with `NBS_SOURCE`; the playback gate remains closed until they match.

For the historical direct-create route, stage the same file under `Documents/Videos/horror.nbs` instead.

## 11. Launch and forward Telnet

The device must be unlocked:

```bash
xcrun devicectl device process launch \
  --device 11E6D8F3-8AF5-5A99-BFC3-B5AE7759A13B \
  com.netease.technicalcenter
```

Keep USB forwarding alive in the background:

```bash
/opt/homebrew/Cellar/libusbmuxd/2.1.1/bin/iproxy \
  19113 9113 \
  -u 00008110-001A5C1226B8401E
```

Telnet must return `Welcome to messiah server` from `127.0.0.1:19113`.

## 12. Replace MPK shaders with the complete source roots

The default iOS runtime can load shaders from `Resources.mpk`. NBS may decode successfully while rendering with an older MPK shader, producing panorama distortion, incorrect projection, purple output, or other false visual failures.

Do not copy only `UI/UIMiniGifImage.fx`. The verified hot-update path requires the union of both source roots because `EngineShaders` depends on includes and supporting shaders from `Engine/Shaders`:

```text
Engine/EngineShaders/*
Engine/Shaders/*
        ↓ merge
Documents/LocalData/Patch/Shaders/*
```

Prepare one staging directory on the Mac:

```bash
SHADER_STAGE=/tmp/j_ios_shader_payload
rm -rf "$SHADER_STAGE"
mkdir -p "$SHADER_STAGE"
cp -R Engine/EngineShaders/. "$SHADER_STAGE/"
cp -R Engine/Shaders/. "$SHADER_STAGE/"
```

For a reused app data container, use Telnet before playback to remove these exact stale paths:

```text
Documents/LocalData/Patch/Shaders
Documents/LocalData/Cache/Shaders
Documents/LocalData/Cache/ShaderBin
Documents/LocalData/Cache/LocalShaders
```

Then copy the complete merged tree:

```bash
xcrun devicectl device copy to \
  --device 11E6D8F3-8AF5-5A99-BFC3-B5AE7759A13B \
  --domain-type appDataContainer \
  --domain-identifier com.netease.technicalcenter \
  --source "$SHADER_STAGE" \
  --destination Documents/LocalData/Patch/Shaders
```

Verify at minimum that the device contains:

```text
Documents/LocalData/Patch/Shaders/UI/UIMiniGifImage.fx
Documents/LocalData/Patch/Shaders/YUVDecode.fx
```

Pull representative files back and compare SHA-256 with the staged sources.

Do not treat file copy alone as shader override success. After copying, you must call `MRender.RefreshShaderSource(callback)` through Telnet and require a successful callback, or terminate and relaunch the app before creating the NBS node. The practical rule is:

```text
copy shader source -> refresh shader source -> replay NBS -> judge pixels
```

If `Patch/Shaders` contains the new file but the app has not completed `RefreshShaderSource`, the runtime can still render with the previously loaded shader state. A successful decoder state without this shader refresh gate does not prove visual correctness.

## 13. Play and verify NBS

Historical direct-create builds used:

```text
Documents/Videos/<file>.nbs
MiniGifNode.create('Videos/<file>.nbs', ...)
```

The newer async switch route opens through Messiah `GFileSystem`; use:

```text
Documents/LocalData/Videos/<file>.nbs
MiniGifNode.createPure(...)
node.switchToFile('LocalData/Videos/<file>.nbs', ...)
```

Before playback, clear the welcome layer from the running scene:

```text
Scene -> PanelRoot -> remove all welcome children
```

Then add the node to the now-empty running scene and poll:

```text
getDecoderId()
isVideoReady()
getClipCount()
isVisible()
```

Pass only when the runtime state meets the success contract.

For panorama acceptance, also capture a screenshot after the shader refresh/relaunch and confirm that the image is not distorted, flattened, purple, or black. Runtime readiness and visual correctness are separate gates.

## 14. Crash evidence and A/B

If Telnet resets after decoder creation:

1. Query whether `Game` is still running.
2. List `systemCrashLogs` with `devicectl`.
3. Pull the newest `Game-*.ips` into `.j-evidence/`.
4. Record exception, faulting thread, NBS frames, app UUID, library version, file path, and playback parameters.
5. Rebuild with only the intended prior library/header files changed.
6. Re-run with the identical shader payload, NBS file, install/launch sequence, and playback command.

Never use a different NBS file or playback path for the comparison.
