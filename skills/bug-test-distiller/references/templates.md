# Bug Test Distillation Templates

## Timing Or Race Bug

Use when event order, delayed restore, reconnect, pending queue, async completion, or lifecycle timing caused the bug.

```text
Symptom:
  ...

Bad sequence:
  1. ...
  2. ...
  3. ...

Correct sequence:
  1. ...
  2. ...
  3. ...

Invariant:
  ...

Minimal deterministic test:
  Arrange: ...
  Act: ...
  Assert: ...

Product E2E gate:
  Start state: ...
  User action: ...
  Expected visible result: ...
  Continuity check: ...
```

Example invariant:

```text
Chat restore must complete or explicitly fail before the composer can send a new user message.
```

Example forbidden sequence:

```text
page mounted -> history restore pending -> user sends -> realtime task_finished displays -> delayed loadHistory merges another completion reply
```

## Source Of Truth Bug

Use when the bug came from Redis/file/status snapshot/task ledger/runtime state disagreement.

```text
Primary truth:
  ...

Subordinate runtime ledgers:
  ...

Forbidden write/read path:
  ...

Invariant:
  ...

Regression test:
  Create conflicting subordinate state.
  Read through the public API/path.
  Assert primary truth is not overwritten or reconstructed from runtime artifacts.

Source guard:
  Ban or pin the helper/call site that previously upgraded runtime observations into business truth.
```

## Frontend Realtime Or History Bug

Use when WebSocket events, chat history, task events, audio events, or UI state competed.

```text
Channels involved:
  - realtime:
  - history:
  - local pending:

Single allowed reporting channel:
  ...

Forbidden duplicate path:
  ...

Invariant:
  ...

Tests:
  - Protocol reducer/order test:
  - Source guard:
  - Product E2E screenshot gate:
```

Useful assertions:

```text
Only one assistant completion message exists for the same task_id + attempt_id.
Events with stale session_id/reply_id/attempt_id are ignored.
History restore cannot inject a live task completion into an already active turn.
```

## Deployment Or Config Drift Bug

Use when an app space, backend instance, env file, port, database, visible/headless mode, or forwarding config drifted.

```text
Configured source of truth:
  ...

Runtime file generated from it:
  ...

Drift that occurred:
  ...

Invariant:
  Deployment must generate or verify runtime config from the source of truth before starting the service.

Regression assets:
  - Config parser/unit test:
  - Deploy source guard:
  - Real deploy smoke gate:
```

Useful assertions:

```text
Missing config fails loudly.
The deploy script reads the instance config before restart.
The generated backend.env contains the expected DB_HOST/DB_PORT for the selected space.
Login smoke uses the deployed instance, not a fallback instance.
```

## Product E2E Display Bug

Use when backend success did not equal product success.

```text
Backend success condition:
  ...

Product success condition:
  ...

Invariant:
  ...

E2E gate:
  1. Capture initial visible state.
  2. Perform real user action.
  3. Capture in-progress visible state if relevant.
  4. Capture final visible state.
  5. Perform continuity check: send next message, reopen, or restart.
  6. Assert no duplicate, stale, fallback, or misleading text.

Evidence:
  - task id:
  - screenshot path:
  - log path:
  - status/result path:
```

Useful assertion:

```text
Backend done is necessary but not sufficient; the final App/web UI must show the correct result and remain usable afterward.
```
