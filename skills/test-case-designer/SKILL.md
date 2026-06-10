---
name: "test-case-designer"
description: "Design complete test cases and verification gates before or during a feedback loop. Use when Codex must validate a bug fix, feature, migration, state machine, integration, intermittent issue, or user-reported behavior with explicit normal, boundary, failure, delay, regression, logging, manual, and cleanup coverage."
---

# Test Case Designer

## Purpose

Use this skill to turn a debugging or development goal into a concrete verification plan. Do not fix code directly from this skill. Produce test cases, evidence gates, and cleanup requirements that the active feedback loop can execute.

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

Stop condition:
```

## Rules

- Prefer evidence that can be checked by the agent without relying on user perception.
- Do not accept "looks fixed" as sufficient evidence when logs or deterministic checks can be added.
- Separate product fixes from diagnostic code. Product fixes may remain; diagnostic code must be removed unless explicitly promoted to a supported diagnostic capability.
- Require a final diff review before commit to confirm no mock, artificial delay, fake data, debug UI, or forced state remains.
- When a device or human-only step is unavoidable, make the manual step minimal and pair it with logs that Codex can inspect afterward.
