---
name: "bug-test-distiller"
description: "Distill a fixed bug, human-found defect, failed closed-loop test, or direction-correction review into reusable regression assets. Use after bug fixes, AI closed-loop repairs, manual testing discoveries, timing/race fixes, state-machine fixes, source-of-truth fixes, product E2E failures, or when the user asks to extract tests,沉淀测试用例, define correctness, add gates, or answer 'how will this bug fail automatically next time'."
---

# Bug Test Distiller

## Purpose

Turn a bug fix into durable correctness assets. Do not stop at "fixed and tested"; extract what the system must never do again, then encode that as tests, source guards, product gates, documentation, or explicit follow-up work.

Use this skill after the fix or direction correction is understood. If the root cause is still unknown, first identify the root cause and event/data flow, then return to this workflow.

## Core Question

Always answer:

```text
How will this class of bug fail automatically next time?
```

If there is no automatic failure yet, say that clearly and create the smallest practical guard. If automation is not currently possible, write the manual gate and the exact future automation entry point.

## Workflow

1. Reconstruct the bug.
   - Identify the user-visible symptom.
   - Identify the confirmed root cause, not just the surface failure.
   - Identify the event sequence, data flow, state transition, or configuration path that made the bug possible.
   - List the evidence used: logs, task ids, screenshots, tests, commits, files.

2. Extract the invariant.
   - Write one sentence that must remain true after future refactors.
   - Prefer product or architecture language over implementation detail.
   - For direction bugs, state what must not become a second truth source, fallback path, or reporting channel.

3. Extract the forbidden sequence.
   - For timing bugs, list the exact bad order of events.
   - For source-of-truth bugs, list the illegal read/write path.
   - For UI/product bugs, list the sequence that makes the user see wrong, duplicated, stale, or misleading state.
   - For deployment/config bugs, list the drift path that must fail loudly.

4. Design the smallest regression test.
   - Prefer deterministic unit/protocol/source tests before heavy E2E.
   - Include the assertion that would have failed before the fix.
   - Make the test fail on the class of bug, not only on one literal string or one exact screenshot.

5. Add or update a source guard when the bug came from an architectural prohibition.
   - Use source guards for "must never add this bypass again" rules.
   - Guard against silent fallback, second truth source, out-of-order protocol handling, hidden retry, swallowed error, or product-state shortcut.
   - Do not use source guards as the only validation when behavior can be tested directly.

6. Define the product E2E gate.
   - Specify the real user path, starting state, and final visible evidence.
   - Include screenshots or UI snapshots for App/web product behavior.
   - Include continuity checks when relevant: repeat action, restart/reopen, reconnect, background/foreground, or next message after completion.

7. Implement and run the selected gates when the user asked for execution or the current task is a coding task.
   - Keep edits scoped to tests, guards, and docs unless more code change is required.
   - Respect repository style and existing test locations.
   - Do not add try/catch, silent fallback, sleeps, retries, or workaround logic unless the user explicitly approves.

8. Report the distillation.
   - State what was added.
   - State what now fails automatically.
   - State what remains manual and why.
   - State any residual risk.

## Required Output Shape

Use this structure in the final report or in the committed document/test note:

```text
Invariant:
  ...

Forbidden sequence:
  1. ...
  2. ...

Regression asset:
  - Source guard: ...
  - Unit/protocol test: ...
  - E2E gate: ...

Before-fix failure:
  ...

After-fix evidence:
  ...

Remaining manual risk:
  ...
```

## Test Selection Rules

- Use a source guard when the risk is architectural drift that is hard to trigger in one runtime test.
- Use a unit/protocol test when the bug is a deterministic state transition, parser, event reducer, API contract, or message ordering issue.
- Use an integration test when the bug crosses backend/frontend, file/Redis, runner/gateway, deployment config, or multiple services.
- Use product E2E when the bug is user-visible, timing-dependent, App/web lifecycle-dependent, or previously found by manual testing.
- For high-risk fixes, use at least one deterministic test plus one product-level gate.

## Quality Bar

The result is not acceptable if it only says:

- "Add more tests."
- "Manual test passed."
- "The closed loop passed."
- "The bug is fixed."

The result is acceptable when it identifies a future failing condition:

```text
If someone reintroduces X, test/guard Y fails with assertion Z.
```

## References

Read `references/templates.md` when the bug type is timing/race, source-of-truth, deployment/config drift, frontend history/real-time state, or product E2E display.
