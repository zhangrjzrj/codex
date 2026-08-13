---
name: "five-step-simplification"
description: "Apply a strict five-step simplification workflow to specifications, designs, protocols, data models, processes, or implementations: delete requirements, delete structure, delete process steps, optimize, then automate. Use when the user asks for 马斯克五步工作法, 五步工作法, 前三步删减, requirement/structure/process deletion, simplification before optimization, or an explicit first-N-step review."
---

# Five-Step Simplification

Apply the steps in order. Treat deletion as removal of unnecessary logic, not compression of wording. Never optimize or automate an element before proving it survives all earlier deletion steps.

## Scope

Interpret the requested range literally:

- `前 3 步` means execute Steps 1-3 and stop before optimization.
- `第 2 步` means inspect structure, but first identify the surviving requirements needed to judge it.
- `完整五步` means execute all steps in order.
- If no range is stated, perform Steps 1-3 first and report whether the design is stable enough to continue.

For a changed specification, read the diff first, then all definitions, references, callers, consumers, validation rules, failure exits, and related specifications affected by the changed concepts.

## Step 1: Delete Requirements

For every requirement, ask:

1. What concrete required outcome or invariant does it protect?
2. What observable failure occurs if it is deleted?
3. Is it solving measured evidence or a speculative edge case?
4. Is another existing requirement already sufficient?
5. Is the requirement compensating for a flawed structure or process?

Delete a requirement when its removal changes no required behavior, semantic boundary, validation guarantee, safety boundary, auditability, or governance outcome.

Do not keep a requirement merely because it is useful, conventional, reassuring, or might help someday. Mark uncertain low-evidence requirements as candidates for deletion, not permanent architecture.

Output for each retained requirement: its independent responsibility and a concrete deletion counterexample.

## Step 2: Delete Structure

Inspect every object, field, state, event type, reference, wrapper, version, registry, manifest, cache, and source of truth.

Delete or merge structures that are:

- mechanically and uniquely derivable from authoritative data
- duplicate representations of the same semantic fact
- wrappers that only rename or forward another object
- type fields already determined by a closed schema branch
- IDs duplicated by immutable content-addressed identity without a separate semantic role
- states that do not change legal behavior or transitions
- separate tables or unions whose only difference is a type-specific payload
- caches presented as truth rather than rebuildable projections

Do not unify structures when the common wrapper adds another level without removing real duplication. Prefer direct typed references when they are simpler than a generic envelope.

For every retained structure, state why deleting it loses identity, meaning, validation, concurrency control, publication consistency, or required audit history.

## Step 3: Delete Process Steps

Map the end-to-end path as a compact flow. For each step or gate, ask:

1. Does it produce a new necessary fact, decision, artifact, or authority boundary?
2. Is the same check already performed earlier or later?
3. Is it optional in practice but incorrectly placed on the mandatory path?
4. Is it only converting between redundant structures?
5. Can it be derived at the point of use instead of persisted or staged?
6. Does it exist only to repair complexity introduced by an earlier step?

Delete duplicate checks, unnecessary handoffs, reversible intermediate states, parallel flows with identical rules, and optional prechecks from the mandatory path.

Retain separate steps when they isolate genuinely different proof obligations, trust boundaries, failure ownership, or atomic publication boundaries.

After deletion, verify the normal, insufficient-evidence, failure, concurrency, retry, version-change, and publication paths remain deterministic and explainable.

## Step 4: Optimize

Run only after Steps 1-3 are stable.

Optimize the surviving model for latency, throughput, storage, query cost, context size, usability, and maintainability. Optimizations must not introduce a second source of truth or restore deleted requirements, structures, or process steps under a different name.

Mark derived performance data as rebuildable projection or cache.

## Step 5: Automate

Run only after the process is necessary, minimal, closed, and optimized.

Automate deterministic decisions, validation, transitions, publication, and reconstruction. Keep semantic judgment at the layer that owns semantics. Define inputs, outputs, failure behavior, authority, idempotency, and observable evidence before automating.

Do not automate ambiguity, unstable policy, or a process still under structural debate.

## Cross-Check

After every applied deletion:

1. Search the current artifact for stale definitions and references.
2. Search related artifacts for contradictions.
3. Recheck sources of truth, lifecycle transitions, failure exits, and publication boundaries.
4. Test whether the deletion merely moved complexity elsewhere.
5. Delete superseded language rather than preserving historical alternatives in the final specification.

Use `design-closure-review` when the deletion exposes a structural contradiction requiring deeper model closure.

## Output

```text
结论：
已执行到第几步，是否可以进入下一步。

第 1 步：需求删减
- 删除项 / 保留项及独立责任。

第 2 步：结构删减
- 删除项 / 保留项及不可删除原因。

第 3 步：流程删减
- 删除或合并的步骤，以及剩余最小流程。

未闭合问题：
- 阻止进入下一步的矛盾或证据缺口。

可直接修改：
- 已确认且不会引入回归的最小变更。
```

Only include sections for steps actually requested. Findings come before summaries. Do not claim completion when unresolved contradictions remain.
