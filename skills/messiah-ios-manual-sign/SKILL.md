---
name: "messiah-ios-manual-sign"
description: "Use when Codex needs to generate, sign, and build a Messiah iOS project on macOS with a known manual-signing workflow: override bundleIdentifier, regenerate Messiah-iOS.xcodeproj, run xcodebuild with explicit CODE_SIGN_STYLE/DEVELOPMENT_TEAM/PROVISIONING_PROFILE_SPECIFIER/CODE_SIGN_IDENTITY, and diagnose signing failures from logs."
---

# Messiah iOS Manual Sign

## When to use

Use this skill when a Messiah iOS build is blocked by signing and you need a repeatable command-line closure instead of Xcode UI clicking.

Typical triggers:

- `Signing for "Game" requires a development team`
- `No profiles for ... were found`
- need to rebuild a clean iOS project with the correct bundle id
- need to reuse the previously verified `technicalcenter + profile5test` signing chain

## Verified environment for this workflow

- SSH host alias: `mac-h74`
- Remote Messiah root: `/Users/game-netease/Desktop/messiah_official_nbs_dev/messiah`
- iOS target: `Game`
- Known good bundle id: `com.netease.technicalcenter`
- Known good manual signing parameters:
  - `CODE_SIGN_STYLE=Manual`
  - `DEVELOPMENT_TEAM=S3NPTV6S84`
  - `PROVISIONING_PROFILE_SPECIFIER=profile5test`
  - `CODE_SIGN_IDENTITY=Apple Development: Qinlin Li (XUKN5ANLY9)`

## Closed-loop procedure

### 1. Ensure remote tracked code is clean

```powershell
ssh mac-h74 "cd /Users/game-netease/Desktop/messiah_official_nbs_dev/messiah && git status --short"
```

If tracked source files are dirty, restore them before signing verification. Keep `.codex-build/` if it only contains local evidence/scripts.

### 2. Regenerate iOS project with the correct bundle id

Do not rely on the default `GenerateIOSHybrid.sh` bundle id if it still points to `com.netease.tx`.
Prefer a direct command override:

```powershell
ssh mac-h74 "cd /Users/game-netease/Desktop/messiah_official_nbs_dev/messiah && python3 BuildMessiah.py ios monolithic=0 build_core=1 armv7=0 armv7s=0 override_pymalloc=0 clip_pre_pass=1 NaviRecast=1 Loader=0 TestCase=0 Presenter=0 Shaderman=0 FbxRemoteImport=0 occlus=True enable_stat=1 bundleIdentifier=com.netease.technicalcenter tracy_profile_memory=1 enable_profile=1 MagicSniffer=1 use_fixmath=1 ImGui=1 AR=1 Customization=1 open_record=1 NativeMedia=1"
```

### 3. Confirm generated project values

```powershell
ssh mac-h74 "cd /Users/game-netease/Desktop/messiah_official_nbs_dev/messiah && grep -RIn 'PRODUCT_BUNDLE_IDENTIFIER\\|DEVELOPMENT_TEAM\\|PROVISIONING_PROFILE_SPECIFIER\\|CODE_SIGN_STYLE' Engine/Intermediate/Messiah-iOS.xcodeproj/project.pbxproj | head -n 80"
```

Expected baseline after generate:

- `PRODUCT_BUNDLE_IDENTIFIER = com.netease.technicalcenter;`
- generated file may still leave:
  - `CODE_SIGN_STYLE = Manual;`
  - `DEVELOPMENT_TEAM = "";`
  - `PROVISIONING_PROFILE_SPECIFIER = "";`

That is acceptable because the real signing inputs are injected through `xcodebuild`.

### 4. Run the verified manual-signing build

```powershell
ssh mac-h74 "cd /Users/game-netease/Desktop/messiah_official_nbs_dev/messiah && xcodebuild -project Engine/Intermediate/Messiah-iOS.xcodeproj -scheme Game -configuration Hybrid -destination 'generic/platform=iOS' CODE_SIGN_STYLE=Manual DEVELOPMENT_TEAM=S3NPTV6S84 PROVISIONING_PROFILE_SPECIFIER=profile5test \"CODE_SIGN_IDENTITY=Apple Development: Qinlin Li (XUKN5ANLY9)\" build | tee .codex-build/xcodebuild_hybrid_manual_profile_current.log"
```

### 5. Judge pass/fail from log

Successful evidence usually includes:

```text
application-identifier = S3NPTV6S84.com.netease.technicalcenter
Signing Identity: Apple Development: Qinlin Li (XUKN5ANLY9)
Provisioning Profile: profile5test
```

Failure triage:

- `requires a development team`
  - signing args were not injected correctly
- `No profiles for 'com.netease.tx' were found`
  - wrong bundle id was generated
- `No profiles for 'com.netease.technicalcenter' were found`
  - profile missing or wrong team/profile combination
- `errSecInternalComponent` during `CodeSign .../*.framework` or `CodeSign Game.app`
  - first verify whether SSH can access the signing private key:

```powershell
ssh mac-h74 "security show-keychain-info ~/Library/Keychains/login.keychain-db 2>&1 || true"
```

  - if it prints `User interaction is not allowed`, the signing inputs are not the root cause; the blocker is macOS keychain/private-key access from a non-interactive SSH session
  - confirm with a disposable framework copy:

```powershell
ssh mac-h74 "rm -rf /tmp/codex_sign_probe.framework; cp -R /Users/game-netease/Desktop/messiah_official_nbs_dev/messiah/Engine/Sources/External/cclivesdk/ios/MLiveCCPlayer.framework /tmp/codex_sign_probe.framework; /usr/bin/codesign --force --verbose=4 --sign F6C9244F650A766DCC1D6D91941EE253D5586E7E --timestamp=none /tmp/codex_sign_probe.framework 2>&1 || true"
```

  - if ad-hoc signing works but Apple Development/Distribution signing fails, do not keep changing bundle id/profile/project files; unlock or re-authorize the login keychain/private key in the macOS GUI session, or run `security unlock-keychain`/`security set-key-partition-list` only when the keychain password is explicitly available outside Codex
  - if signing succeeds in the macOS GUI Terminal but still fails through SSH, the blocker is SSH session isolation from the GUI login keychain context; continue the build from GUI Terminal/Xcode, or create a dedicated build keychain for CI-style SSH signing instead of spending more time on project signing settings
- code compile errors reappear
  - remote source became dirty again or build inputs changed

## Historical evidence chain

Previously verified logs on the same remote workspace:

- `.codex-build/xcodebuild_hybrid_manual_profile_codex_20260710_1618.log`
- `.codex-build/xcodebuild_hybrid_signed_retry_20260710.log`
- `.codex-build/xcodebuild_hybrid_signed_retry2_20260710.log`

Key facts from those logs:

- automatic signing failed for `com.netease.tx`
- automatic signing also failed for `com.netease.technicalcenter`
- manual signing with `profile5test` succeeded and produced `application-identifier = S3NPTV6S84.com.netease.technicalcenter`

## Guardrails

- Prefer command-line signing over Xcode UI clicking
- Avoid editing tracked signing files if command-line overrides are enough
- Keep the remote source clean before judging signing results
- Always save the current build log into `.codex-build/` for comparison
