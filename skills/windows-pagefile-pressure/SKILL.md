---
name: windows-pagefile-pressure
description: Drive controlled Windows commit and pagefile pressure to reproduce low resource crashes validate pagefile growth test pagefile expansion failure and manage disk fill conditions.
---

# Windows Pagefile Pressure

Use this skill to reproduce Windows low-resource failures involving commit limit, dynamic pagefile growth, disk-full pagefile expansion, and memory pressure near crash boundaries.

## Safety Rules

- Treat disk-fill and commit pressure as risky. Announce the exact target drive, fill files, and release files before changing disk state.
- Prefer disposable fill files named `codex_pagefile_pressure_fill*.bin`.
- Never delete unknown files. Only remove fill files created for the test.
- Keep at least one clear recovery command in the final answer.
- For crash reproduction, prefer staged pressure: observe baseline, allow pagefile growth, then constrain disk, then apply workload.

## Core Concepts

- `AllocatedBaseSize`: current pagefile size in MB. This is the value that proves pagefile growth.
- `CurrentUsage`: current pagefile usage in MB.
- `CommitLimit`: total commit ceiling. It rises when pagefile successfully expands.
- `CommittedBytes`: current committed memory.
- `HeadroomMB = CommitLimit - CommittedBytes`: remaining commit room.
- `MaximumSize`: configured maximum pagefile size, not current available commit. Dynamic pagefile growth still needs disk space.

## Workflow

1. Capture baseline:
   ```powershell
   powershell -ExecutionPolicy Bypass -File <skill>\scripts\pagefile_pressure.ps1 -StatusOnly -Drive E
   ```

2. If the goal is to prove pagefile can grow, leave enough free space first:
   - Release a fill file or keep at least `512MB-2GB` free.
   - Apply commit pressure until `AllocatedBaseSize` rises.

3. If the goal is expansion-failure reproduction:
   - First let pagefile grow to a known value.
   - Fill the pagefile drive close to full.
   - Apply commit pressure or run the target workload.
   - Watch for `AllocatedBaseSize` stuck, `HeadroomMB` low, and workload failure.

4. If the goal is a stable near-boundary setup:
   - Use smaller chunks near the edge, e.g. `-ChunkMB 64`.
   - Stop before `HeadroomMB` reaches zero. Use `TargetHeadroomMB` and `SafetyMarginMB`.

## Script

Use `scripts/pagefile_pressure.ps1`.

Common commands:

```powershell
# Observe current pagefile/commit/drive state.
powershell -ExecutionPolicy Bypass -File scripts\pagefile_pressure.ps1 -StatusOnly -Drive E

# Fill a drive to a target free-space amount.
powershell -ExecutionPolicy Bypass -File scripts\pagefile_pressure.ps1 -FillDrive -Drive E -TargetDriveFreeMB 1024

# Apply memory pressure until commit headroom is near the target.
powershell -ExecutionPolicy Bypass -File scripts\pagefile_pressure.ps1 -Pressure -Drive E -ChunkMB 256 -MaxChunks 256 -TargetHeadroomMB 1024 -SafetyMarginMB 256 -ShowPageFile

# Release all fill files created by this script on the target drive.
powershell -ExecutionPolicy Bypass -File scripts\pagefile_pressure.ps1 -ReleaseFill -Drive E
```

## Interpretation

- Pagefile growth is confirmed only when `AllocatedBaseSize` increases.
- If `CurrentUsage` rises but `AllocatedBaseSize` does not, current pagefile capacity is not yet exceeded or expansion is blocked.
- If disk free space is near zero, Windows may fail to expand pagefile; use this for expansion-failure reproduction, not for growth validation.
- Do not use `headroom=0` as a target. That is an unstable failure edge.
