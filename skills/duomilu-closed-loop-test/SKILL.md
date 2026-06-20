---
name: "duomilu-closed-loop-test"
description: "Design and run Duomilu/App4 closed-loop acceptance tests from test-case design through evidence-gated execution, ordinary bug self-fix, rerun, and final verdict. Use when the user asks Codex to build or execute a Duomilu feedback loop, validate DomiLu task behavior, run app/emulator/PC-web task acceptance, add screenshot evidence gates, or keep iterating until a Duomilu test case passes or a real blocker is proven."
---

# Duomilu Closed Loop Test

## Goal

Drive a complete Duomilu acceptance loop:

```text
design or load test case
-> prepare isolated app/backend/device/PC slot environment
-> let Duomilu execute the product behavior
-> collect app_* and pc_* evidence
-> judge assertions
-> fix ordinary engineering bugs
-> restart/repack/rerun
-> stop only on pass, real blocker, or max rounds
```

Codex must not replace Duomilu as the product executor. Codex is the verifier and repair engineer.

## Default App4 Test Environment

Use this default only when the current workspace is `D:\hanhan\app4` or the user asks for app4:

```text
frontend: D:\hanhan\app4
backend: D:\hanhan\ai_backend
backend instance: app4
HTTP: 8787
WS: 7275
ADB device: emulator-5562
test account: 44444444 / 44444444
PC slots: 9333, 9334, 9335, 9336, 9337
```

Restart app4 backend with:

```powershell
D:\hanhan\ai_backend\scripts\restart_backend_instance.ps1 -InstanceId app4
```

When installing app4 to the fifth emulator, pass:

```powershell
-DeviceId emulator-5562
```

## Evidence Vocabulary

Use explicit evidence names:

```text
app_screenshot      ADB/real-device screenshot of the Duomilu App UI.
app_ui_dump         ADB/UIAutomator or equivalent App UI tree.
pc_screenshot       CDP screenshot of the PC web task现场.
pc_page_structure   CDP/MCP structured page model.
pc_raw_text         Visible/raw text from the PC web page.
pc_dom_dump         DOM/diagnostic dump from the PC web page.
task_status         CodexTask status and status.json.
ws_events           task_started/task_waiting/task_snapshot/task_finished messages.
backend_logs        Gateway/CodexTask/MCP/backend log excerpts.
redis_state         active task, recent task stack, pending choice, slot/runtime locks.
final_verdict       Machine-readable pass/fail/blocked verdict.
```

Do not treat screenshots as the only truth. Prefer structured evidence and logs, then use screenshots as keyframe proof or visual fallback.

## Phase 1: Test Case Contract

If a test case already exists, read it first. For app4 task acceptance, prefer:

```text
D:\hanhan\app4\docs\acceptance\realtime-task-and-concurrency-matrix.md
```

If no suitable case exists, design one before executing. Include:

```text
case_id
goal
entry point
preconditions
instructions/prompts
keyframes
evidence required for each keyframe
assertions
failure classifications
ordinary bug self-fix scope
blocked/manual gates
cleanup
max rerun rounds
stop condition
```

Minimum keyframe format:

```text
id:
when:
required evidence:
assertions:
```

## Phase 2: Environment Gate

Before running the product test:

1. Confirm the intended workspace, backend instance, device serial, account, and PC slot pool.
2. Confirm the backend is reachable.
3. Confirm the selected emulator/device is online.
4. Confirm PC slot state is readable and sufficient for the case.
5. Confirm whether code changes require backend restart or App repack/install.
6. Put temporary logs, screenshots, UI dumps, and diagnostic files under the project's ignored local evidence directory when available, such as `.local-artifacts/runtime-evidence/`.

Do not operate the wrong emulator or backend instance.

## Phase 3: Execute Through Duomilu

Use Duomilu as the executor:

1. Launch the App on the selected device.
2. Complete the local debug login flow automatically unless a real external gate appears.
3. For skill/task validation, enter the left menu panel and use the "技能训练" entry. Do not use the ordinary homepage chat input for skill-training acceptance.
4. Send the test case instruction in Chinese.
5. Let Duomilu start and run the task.
6. Poll task state, websocket events, logs, and PC slot state.
7. Capture required keyframe evidence.

If a captcha, SMS code, third-party authorization, real payment, or user decision appears, stop as `blocked:user_gate` or `blocked:product_decision` instead of forcing through.

## Phase 4: Evidence-Gated Verdict

For each keyframe, record:

```text
pass/fail/uncertain
evidence paths
observed state
assertion result
failure reason if any
```

A final pass requires all required assertions to pass. "Looks fine" is not enough.

Recommended `final_verdict.json` fields:

```json
{
  "case_id": "",
  "pass": false,
  "status": "pass|fail|blocked",
  "failed_stage": "",
  "failure_type": "ordinary_bug|user_gate|product_decision|environment|unknown",
  "task_ids": [],
  "evidence": [],
  "summary": "",
  "next_action": "stop|fix_and_rerun|ask_user"
}
```

## Phase 5: Ordinary Bug Self-Fix

Automatically fix ordinary engineering bugs when the evidence proves the root cause and the fix is inside the agreed scope.

Allowed ordinary bug areas:

```text
MCP result completeness
DOM/page_structure/raw_text extraction
click/type/scroll/hit-test reliability
screenshot/evidence trace writing
task state transitions
active/recent task routing
WebSocket task event payloads
PC slot/runtime lock handling
frontend test feedback display
prompt/tool-use guidance that makes Duomilu use existing capabilities correctly
```

Do not self-fix without user confirmation:

```text
payment or real order submission
production cloud resource changes
account authorization or captcha bypass
deleting user data
product strategy decisions
large UX behavior changes
security/compliance boundaries
```

When fixing:

1. State the current round goal, evidence, action, and whether another round is needed.
2. Prefer root-cause fixes over superficial sleeps/retries/fallbacks.
3. Mark any temporary workaround as `WORKAROUND:` with reason, risk, and removal condition.
4. Run relevant syntax/build checks.
5. Restart backend or repack/install only when needed.
6. Rerun the same test case.

## Phase 6: Stop Conditions

Stop only when one condition is met:

```text
pass: final_verdict proves all assertions passed
blocked:user_gate: external login/captcha/payment/user decision required
blocked:environment: device/backend/network/tooling unavailable after evidence-backed retries
blocked:scope: required change is outside self-fix boundary
max_rounds: configured rerun limit reached with evidence summary
```

Do not stop at "analysis only" when ordinary self-fix is in scope and the environment can run.

## Reporting

Each loop round must report:

```text
本轮目标
本轮证据
本轮动作
是否进入下一轮
```

Final response must include:

```text
case_id
verdict
changed files
verification run
evidence paths
remaining risks or blockers
```
