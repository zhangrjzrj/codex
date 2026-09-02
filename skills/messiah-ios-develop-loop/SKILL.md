---
name: "messiah-ios-develop-loop"
description: "Close the complete Messiah public develop iOS loop on a remote Mac: locate an integrated commit, create an isolated worktree, pull required Git LFS artifacts, prepare Resources.mpk, generate the Xcode project, build with an SSH-capable signing keychain, verify and install Game.app, inject and verify the complete runtime shader patch plus NBS asset, launch it, connect through CoreDevice IPv6 or iproxy, control it through Telnet, verify NBS playback and visual correctness, and collect crash evidence. Use when Codex needs to reproduce or validate a Messiah develop iOS version end to end rather than only compile or sign it."
---

# Messiah iOS Develop Loop

Use this skill as the top-level iOS workflow. Route focused operations to:

- `messiah-mac-bridge` for SSH/CoreDevice transport.
- `messiah-ios-manual-sign` for signing diagnosis.
- `messiah-telnet-control` for runtime commands.
- `messiah-feedback-loop` for evidence-gated iteration.

Read [references/verified-flow.md](references/verified-flow.md) before executing the workflow.

When the target lacks a reliable iOS listener on port `9113`, read [references/cpp-telnet.md](references/cpp-telnet.md). It owns the archived public-baseline patch, applicability gate, implementation invariants, and bidirectional acceptance contract.

## Success contract

Require evidence for every completed gate:

```text
target commit
-> isolated worktree
-> real LFS libraries
-> Resources.mpk
-> Python home points to Lib314
-> GenerateIOS
-> signed Hybrid build
-> strict signature verification
-> device install registration
-> device launch
-> C++ Telnet patch applicability when needed
-> CoreDevice IPv6 or iproxy/Telnet welcome
-> Telnet bidirectional text echo
-> Telnet Python command marker and disconnect survival
-> full shader roots copied, verified, and refreshed
-> NBS asset copied and verified
-> NBS ready or proven native crash
```

Do not report success from `BUILD SUCCEEDED` alone. The pass signal is runtime NBS state:

```text
decoder >= 0
ready = True
clipCount >= 1
visible = True
```

If playback produces a native crash report, report the closed loop as blocked at runtime and preserve the `.ips`; do not relabel it as a signing or installation failure.

## Operating rules

1. Inspect remote status before writes. Never overwrite the known-good sample workspace.
2. Prefer a dedicated Git worktree at the exact integrated public commit.
3. Keep evidence under the remote worktree's ignored `.j-evidence/` directory.
4. Put signing secrets only on the Mac. Never print passwords, p12 contents, or the protected password file.
5. Prove SSH signing with a disposable framework before running `xcodebuild`.
6. Run long builds in the remote background with a PID and log; poll process and log progress.
7. Use the exact `Game.app` path reported by the build log; do not guess DerivedData paths.
8. Query the installed app immediately after `devicectl install`; retrying launch without proving registration hides the real failure.
9. If iOS startup shows `_apple_support`, `init_apple_streams`, or `ModuleNotFoundError`, verify `Engine/Sources/Runtime/Plugins/Python/Source/MPython.cpp` sets Python home from `builtin_home`, not `builtin_script`; the runtime standard library must resolve to `Package/Script/Python/Lib314`.
10. Before install, verify `Game.app` physically contains `Resources.mpk` and `Resources.mpkinfo`. A live process with a black screen is not a valid substitute for this gate.
10.1 The source MPK gate is the active worktree `MpkCooked/Resources.mpk` and `MpkCooked/Resources.mpkinfo`; do not substitute `Package` or any other path when preparing the iOS bundle.
11. Do not accept MPK-bundled shaders as the NBS visual baseline. Overlay both `Engine/EngineShaders` and `Engine/Shaders` into `Documents/LocalData/Patch/Shaders`, clear stale shader caches, and prove refresh or reload before playback.
12. Copy the exact NBS asset into the app data container and verify the device-side size or hash before playback.
13. Treat Telnet forwarding as a separate gate from app launch.
13.1 Prefer the current CoreDevice IPv6 tunnel address for direct device port `9113` access. `iproxy` is a compatibility route, not a required implementation.
13.2 Do not accept a listening socket or welcome banner alone. Send a unique text marker and require the same marker in the response.
13.3 Echo proves only that text parsing works. Execute a Python command that writes a unique app-container marker, pull the marker back, close the client connection, and require the App PID to remain alive.
14. For new `switchToFile`-based NBS playback, use a Messiah-mounted path such as `LocalData/Videos/<file>.nbs`; historical `Videos/<file>.nbs` applies to the older direct-create route.
15. Preserve crash logs and compare old/new library versions with the same app, shader patch, NBS file, device, and playback command.

## Stop conditions

Stop only when:

- NBS runtime state passes;
- a reproducible native crash or external environment blocker is proven;
- the user stops or changes the target.

When an A/B library experiment is requested, change only the library/header files named by the target commit, keep the worktree diff explicit, and never touch the staged area without user authorization.
