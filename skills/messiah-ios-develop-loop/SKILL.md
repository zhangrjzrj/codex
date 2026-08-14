---
name: "messiah-ios-develop-loop"
description: "Close the complete Messiah public develop iOS loop on a remote Mac: locate an integrated commit, create an isolated worktree, pull required Git LFS artifacts, prepare Resources.mpk, generate the Xcode project, build with an SSH-capable signing keychain, verify and install Game.app, launch it, establish iproxy, control it through Telnet, verify NBS playback, and collect crash evidence. Use when Codex needs to reproduce or validate a Messiah develop iOS version end to end rather than only compile or sign it."
---

# Messiah iOS Develop Loop

Use this skill as the top-level iOS workflow. Route focused operations to:

- `messiah-mac-bridge` for SSH/CoreDevice transport.
- `messiah-ios-manual-sign` for signing diagnosis.
- `messiah-telnet-control` for runtime commands.
- `messiah-feedback-loop` for evidence-gated iteration.

Read [references/verified-flow.md](references/verified-flow.md) before executing the workflow.

## Success contract

Require evidence for every completed gate:

```text
target commit
→ isolated worktree
→ real LFS libraries
→ Resources.mpk
→ GenerateIOS
→ signed Hybrid build
→ strict signature verification
→ device install registration
→ device launch
→ iproxy/Telnet welcome
→ NBS ready or proven native crash
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
9. Treat Telnet forwarding as a separate gate from app launch.
10. For new `switchToFile`-based NBS playback, use a Messiah-mounted path such as `LocalData/Videos/<file>.nbs`; historical `Videos/<file>.nbs` applies to the older direct-create route.
11. Preserve crash logs and compare old/new library versions with the same app, file, device, and playback command.

## Stop conditions

Stop only when:

- NBS runtime state passes;
- a reproducible native crash or external environment blocker is proven;
- the user stops or changes the target.

When an A/B library experiment is requested, change only the library/header files named by the target commit, keep the worktree diff explicit, and never touch the staged area without user authorization.
