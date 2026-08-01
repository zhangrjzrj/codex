---
name: "design-closure-review"
description: "Review a software, protocol, state-machine, knowledge-system, or AI-agent design for structural closure before implementation. Use when the user asks to find hidden ambiguity, reason from first principles, test abstraction boundaries, prevent state/version/combination explosion, compare alternative models, or make a design precise enough for unambiguous coding."
---

# Design Closure Review

Treat the proposed design as a model that must remain coherent under execution, failure, concurrency, growth, and migration. Do not wait for the user to identify contradictions.

## Workflow

### 1. Establish the minimal model

1. State the goal and non-goals.
2. List the minimum entities, identities, ownership boundaries, and sources of truth.
3. Draw the main data flow or state transition in compact ASCII form.
4. Distinguish facts, derived projections, decisions, commands, and side effects.
5. Remove aliases and fields that carry no independent executable or semantic responsibility.

Do not propose implementation details until the model's nouns and transitions are stable.

### 2. Attack the model

Inspect every relevant dimension. For each one, either present a concrete counterexample or state why the design closes it.

1. **Data structure:** identity, cardinality, references, invariants, and duplicated truth.
2. **State and lifecycle:** legal transitions, triggers, terminal states, and impossible combinations.
3. **Time and evolution:** delay, ordering, retries, versions, migration, historical compatibility, and unbounded growth.
4. **Failure paths:** partial success, cleanup ownership, timeout, lost acknowledgements, and fail-fast boundaries.
5. **Concurrency and isolation:** races, duplicate commands, idempotency, ownership transfer, and cross-task contamination.
6. **Abstraction boundaries:** which layer owns semantics, structure, parameters, execution, validation, and policy.
7. **Scale and context:** combinatorial explosion, registry growth, prompt size, lookup cost, and maintainability.
8. **Security and authority:** executable-data boundaries, injection, authorization, and trusted publication paths.
9. **Counterexamples:** first use, repeated use, changed external system, conflicting knowledge, partial migration, and malformed input.
10. **Minimality:** redundant fields, patch-on-patch rules, unnecessary states, duplicated versions, and concepts inferable from one source of truth.

After finding a problem, inspect the proposed fix against all ten dimensions. A fix is incomplete if it merely moves the explosion or ambiguity to another layer.

### 3. Reconverge

1. Identify the root structural cause, not the visible symptom.
2. Compare only materially different models.
3. Select the smallest model that preserves required semantics and deterministic boundaries.
4. Rewrite affected invariants, data structures, algorithms, and migration rules together.
5. Delete superseded concepts instead of documenting that they were removed.
6. Verify that normal execution, failure, delayed execution, growth, and migration all remain linear and explainable.

Stop when remaining questions are implementation details that follow mechanically from the model. Do not continue inventing abstractions merely because more abstraction is possible.

## Reasoning Rules

- Prefer one source of truth and derive projections mechanically.
- Put polymorphism at the highest layer that genuinely owns the variation; keep lower layers deterministic.
- Separate immutable facts from mutable summaries and published knowledge.
- Separate runtime eligibility from publication lifecycle unless they are truly the same fact.
- Treat backward-compatible growth and incompatible contract change as different operations.
- Require explicit triggers and gates for every lifecycle transition.
- Test zero, one, and multiple matches for every selection mechanism.
- Test first creation, reuse, failure after side effects, and replacement of an active version.
- Use fail fast when the post-side-effect state is uncertain; do not hide uncertainty with fallback execution.
- Challenge any field or state whose removal does not change behavior, meaning, validation, or governance.

## Communication

During discussion, explain the core problem with one concise analogy before precise terminology when that improves comprehension. During finalization, switch to exact terms, invariants, schemas, and transition rules. Specifications must not contain analogies, discarded fields, or historical alternatives.

Use numbered findings so the user can respond point by point. Lead with the highest-impact unresolved contradiction.

## Output

```text
结论：
设计是否闭合，以及最关键原因。

最小模型：
实体、关系、状态或主流程。

未闭合问题：
1. 问题、反例、根因、影响。

最小修正：
1. 需要改变的边界或结构。

演化检查：
首次、失败、并发、增长、版本迁移后的结果。

可直接落盘的硬规则：
仅列已确认且无歧义的规则。
```
