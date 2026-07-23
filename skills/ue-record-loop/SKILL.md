---
name: ue-record-loop
description: "Run generic Unreal recording loops from Codex: launch UE, drive an automated capture, wait for output, collect logs/artifacts, and repeat until evidence is gathered. Use when the user asks to record frames, smoke-test a render path, or build a reusable recording loop for any scene, map, sequence, or Movie Render Graph graph."
---

# UE Record Loop

## Core Scope

Use this skill for recording only. The executable orchestration is in `scripts/run-ue-record-loop.ps1`.

Keep it scene-agnostic and pass-agnostic:

- start or connect to Unreal Editor
- drive an automated capture or MRQ/MRG run
- wait for output to land
- collect the output directory, logs, and file list
- report success or failure clearly

Do not hardcode a specific map, sequence, render layer, or acceptance rule in the skill itself.
Those details belong to the calling task or its project adapter.

The runner has two execution backends with one contract:

```text
Local  -> launch hook -> record hook -> wait -> collect
Remote -> SSH launch hook -> SSH record hook -> wait -> SCP collect
```

Use `-Mode Local` for a local UE project and `-Mode Remote` with `-RemoteHost`,
`-RemoteOutputPath`, and `-PullDestination` for an SSH-controlled machine. Launch
and record hooks remain caller-supplied so the skill stays project-agnostic.

## Workflow

1. Read the task-specific inputs from the user or project state.
2. Choose the least coupled way to trigger recording.
3. Start Unreal Editor in the background when needed.
4. Run the capture or recording script.
5. Poll for completion and collect logs/output files.
6. Return the artifact paths and the shortest useful conclusion.

For L46, call the project adapter after collection:

```powershell
& .\scripts\mrg\validate_l46_aov_record.ps1 `
  -OutputPath F:\path\to\output `
  -ExpectedFrameCount 10
```

The L46 adapter checks the seven-output file-count contract and, when ImageMagick
is available, verifies PNG dimensions. EXR semantic checks remain with the EXR
header reader and NBS encoder validation tools.

## Guardrails

- Keep the skill generic.
- Do not mix recording with scene semantics, asset cleanup, or render correctness logic.
- If a project already has reusable recording scripts, prefer those instead of inventing a new path.
- If the recording fails, report the failure evidence and stop at the real blocker.
