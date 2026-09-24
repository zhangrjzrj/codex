---
name: local-smoke-baseline
description: "Establish and run a local, evidence-isolated smoke baseline before experiments, fixes, or A/B comparisons; use when a known-good executable state must be reproducible."
---

# Local Smoke Baseline

Use this skill when repeated diagnosis has mixed setup changes, stale state, and the hypothesis being tested. Its purpose is to create one small, known-good executable state that later work can cite without rerunning or redefining it.

## Core Model

```text
declared inputs
-> isolated smoke run
-> observable gates
-> immutable evidence
-> BASELINE_PASS
-> one-variable experiment
```

A smoke baseline is not a full regression suite. It proves only the narrow precondition needed for the next decision, such as "app launches and plays this asset" or "service accepts one authenticated request".

## Establish A Baseline

1. State the smallest claim the baseline must prove and its explicit pass signals.
2. Freeze all inputs that can affect that claim: revision, executable/package, asset/config hashes, device/environment identity, and launch command.
3. Choose only observables that prove the claim. Prefer a runtime state plus a user-visible or external result when both matter.
4. Create a new evidence directory for the run. Never reuse or overwrite a prior run.
5. Execute the minimum scenario. Preserve the command trace, result, relevant logs, and declared artifacts.
6. Write `BASELINE_PASS` only when every declared gate passes. Otherwise write the first failed gate and preserve the evidence.

Use [the run schema](references/run-schema.md) for the required minimum record. Use `scripts/create_smoke_run.py` to create a collision-safe run directory and manifest.

## Experiment Rules

- A later experiment must name the passed baseline run it relies on.
- Change one declared variable at a time. If setup, environment, and tested code all change, establish a new baseline instead.
- Keep experiment evidence beside, not inside, the baseline run. A baseline remains immutable after its verdict.
- If an experiment fails before the target condition, classify it as an earlier gate failure; do not infer conclusions about the target behavior.
- Re-establish the baseline when a frozen input changes or when its environment is no longer available.

## Scope And Safety

- Keep evidence in the project's ignored local evidence convention when one exists; otherwise ask before choosing a location.
- The skill does not authorize product changes, installation, deletion, external communication, or retries. Obtain the authorization required by the underlying task.
- Do not turn a tool-specific implementation into a universal requirement. Projects supply their own launch, control, and capture commands.
