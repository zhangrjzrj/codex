---
name: "test-case-designer"
description: "Design complete test cases and verification gates before or during a feedback loop. Use when Codex must validate a bug fix, feature, migration, state machine, integration, intermittent issue, or user-reported behavior with explicit normal, boundary, failure, delay, regression, logging, manual, and cleanup coverage."
---

# Test Case Designer

## Purpose

Use this skill to turn a debugging or development goal into a concrete verification plan. Do not fix code directly from this skill. Produce test cases, evidence gates, cleanup requirements, and the explicit verification level that the active feedback loop can execute.

## Verification Levels

When the user asks for "complete tests", "closed-loop verification", "闭环通过", or similar wording without naming a level, choose the lowest level that can honestly prove the change based on risk, then report the actual level reached. Do not call a result product-complete unless L4 passed.

```text
L1 Code check:
  lint, syntax checks, static checks, unit tests, narrow component tests.
  Proves the changed code is locally coherent.

L2 API / contract:
  service, controller, protocol, event envelope, state-machine, or fixture-driven tests.
  Proves a rule or interface contract behaves correctly.

L3 HTTP / integration:
  real backend process plus HTTP, WebSocket, queue, database, runner, or other live dependencies.
  Proves connected system modules work from a system boundary.

L4 Product E2E:
  real app, browser, emulator, device, or user-visible workflow from the product entry point.
  Proves the user-facing product path works end to end.
```

Default escalation:

```text
Pure utility or internal refactor -> L1/L2.
API, protocol, event, state-machine, persistence, or queue changes -> L2/L3.
Frontend-backend linkage, async task chains, runners, or deployment paths -> L3.
Login, app UX, payment/order flows, audio/video, task execution, device behavior, or any user-visible main path -> L4.
```

If L4 is required but blocked, state the blocker and mark the result as only L1/L2/L3. If the user explicitly names a target level, design and execute gates up to that level unless blocked.

## Workflow

1. Restate the behavior under test in one sentence.
2. Identify the state machine or business flow, including inputs, transitions, outputs, async waits, queues, retries, and external services.
3. List the observable evidence already available: logs, UI events, screenshots, network calls, database rows, files, builds, metrics, or device traces.
4. Design test cases across these buckets:
   - Normal path
   - Boundary path
   - Failure path
   - Delay or race path
   - Regression path for the original bug
   - Cleanup path after completion or cancellation
5. For each test case, define:
   - Setup
   - Trigger
   - Expected result
   - Pass/fail evidence
   - Automation level: automatic, log-verified, or manual
   - Required cleanup
6. If reproduction is unstable, require a controllable reproduction mechanism before changing production logic: mock, artificial delay, fixture, feature flag, local-only switch, or targeted debug log.
7. If temporary test code is added, require it to be marked, removed after validation, and followed by a real-path verification run.
8. End with a minimal verification matrix and the exact stop condition for the feedback loop.
9. State the target verification level and the level actually reached. If they differ, state the missing evidence.

## Output Format

Use this structure unless the user requests otherwise:

```text
Behavior under test:

Flow / state machine:

Evidence sources:

Test cases:
TC1 ...
TC2 ...

Unstable reproduction plan:

Temporary code policy:

Verification matrix:

Verification level:

Stop condition:
```

## Rules

- Prefer evidence that can be checked by the agent without relying on user perception.
- Do not accept "looks fixed" as sufficient evidence when logs or deterministic checks can be added.
- Separate product fixes from diagnostic code. Product fixes may remain; diagnostic code must be removed unless explicitly promoted to a supported diagnostic capability.
- Require a final diff review before commit to confirm no mock, artificial delay, fake data, debug UI, or forced state remains.
- When a device or human-only step is unavoidable, make the manual step minimal and pair it with logs that Codex can inspect afterward.
- Always distinguish rule-level closure from product-level closure. Passing L1/L2 tests is not enough to claim full user-visible regression coverage for an L4 path.
