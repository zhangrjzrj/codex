---
name: messiah-mac-bridge
description: "Operate Messiah workflows on remote macOS host via SSH/SCP/rsync: list files, sync scripts, run source_ios_hybrid.sh, build/archive/export, and collect logs with safety guardrails."
---

# Messiah Mac Bridge

## When to use

Use this skill when you need Codex to operate a remote Mac host for Messiah tasks, including:

- remote file listing or content check
- syncing local scripts/files to Mac
- running iOS generation/build commands remotely
- collecting build logs and artifacts back to local

## Fixed connection profile

- SSH host alias: `mac-h74`
- Remote user/home: `game-netease`, `/Users/game-netease`
- Remote workspace root: `/Users/game-netease/Desktop/messiah_h74`
- Remote Messiah root: `/Users/game-netease/Desktop/messiah_h74/messiah`

## Core commands

### 1) Connectivity check

```powershell
ssh mac-h74 "echo SSH_OK && pwd"
```

### 2) Remote list/check

```powershell
ssh mac-h74 "ls -la /Users/game-netease/Desktop/messiah_h74"
ssh mac-h74 "ls -la /Users/game-netease/Desktop/messiah_h74/messiah | head -n 80"
```

### 3) Sync a single file to Mac

```powershell
scp <local_file> mac-h74:/Users/game-netease/Desktop/messiah_h74/<target_dir>/
```

Example:

```powershell
scp F:\messiah_h74_new_branch\scripts\pack_ios_flow.sh mac-h74:/Users/game-netease/Desktop/messiah_h74/scripts/
```

### 4) Sync directory incrementally (preferred)

```powershell
rsync -av --delete <local_dir>/ mac-h74:/Users/game-netease/Desktop/messiah_h74/<target_dir>/
```

### 5) Run iOS prepare/build remotely

```powershell
ssh mac-h74 "cd /Users/game-netease/Desktop/messiah_h74/messiah && bash source_ios_hybrid.sh"

ssh mac-h74 "cd /Users/game-netease/Desktop/messiah_h74 && bash scripts/pack_ios_flow.sh --messiah-root /Users/game-netease/Desktop/messiah_h74/messiah --ref-package /Users/game-netease/Desktop/messiah_h74/<ipa_name>.ipa --build-type debug --scheme Game --no-signing"
```

### 6) Archive/export (signed flow)

```powershell
ssh mac-h74 "cd /Users/game-netease/Desktop/messiah_h74/messiah && xcodebuild -project Engine/Intermediate/Messiah-iOS.xcodeproj -scheme Game -configuration Release -destination 'generic/platform=iOS' -archivePath /Users/game-netease/Desktop/messiah_h74/artifacts/Game.xcarchive -allowProvisioningUpdates DEVELOPMENT_TEAM=<TEAM_ID> CODE_SIGN_STYLE=Automatic archive"
```

## Closed feedback loop protocol

Every round must output:

1. Round goal
2. Evidence collected
3. Action executed
4. Pass/fail decision
5. Next round plan

Stop only when:

- user goal reached, or
- hard blocker proven with evidence

## Guardrails

- Default to read-only checks first
- For write/sync/build, run smallest necessary command
- Never run destructive remote commands (e.g. `rm -rf`) unless explicitly asked
- Keep remote path explicit; avoid ambiguous relative paths

## Troubleshooting quick map

- `Host key verification failed`: reset known_hosts entry for the host
- `Connection reset`: verify SSH service/network on Mac
- `python: command not found`: fix pyenv/python before source/build
- `Signing requires development team/profile`: use `--no-signing` for compile-only, otherwise configure signing
- `CompileC ... MetalShader.mm`: collect exact `error:` lines and patch code/API mismatch