---
name: "design-closure-review"
description: "Review a software, protocol, state-machine, knowledge-system, AI-agent design, or specification change for structural closure and logical minimality, and identify which changes require human review. Use when the user asks to find hidden ambiguity, check a changed spec against itself or related specs, extract human-review scope, classify semantic changes versus cross-section synchronization or wording cleanup, test abstraction boundaries, prevent state/version/combination explosion, or make a design precise enough for unambiguous coding."
---

# Design Closure Review

Treat the proposed design as a model that must remain coherent under execution, failure, concurrency, growth, and migration. Do not wait for the user to identify contradictions.

## Workflow

### 0. Establish the review surface

When reviewing a specification change:

1. Read the diff before reading the whole document.
2. Extract every changed concept, field, state, invariant, transition, owner, and source of truth.
3. Search the current specification for all definitions and references to those items.
4. Search related specifications for the same items and for concepts connected by references, lifecycle, publication, validation, or ownership.
5. Build the smallest affected rule graph. Do not treat files as independent when their rules share an entity or transition.

Classify each finding as one of:

- contradiction within the changed section
- contradiction elsewhere in the same specification
- contradiction with another specification
- undefined or stale reference
- duplicated truth or responsibility
- unnecessary concept, field, state, branch, version, or process
- wording ambiguity that permits materially different implementations

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

### 4. Recheck the specifications

After a proposed or applied change:

1. Re-run the affected-term and reference searches.
2. Re-read every changed definition together with its callers, consumers, validation rules, failure exits, and publication rules.
3. Confirm that superseded terms and rules are removed rather than left as competing historical language.
4. Confirm that related specifications either remain compatible or are updated in the same change.
5. Repeat the minimality test on the fix itself; reject a fix that closes one contradiction by adding a parallel source of truth or an unnecessary state.

### 5. Extract the human review scope

When the user asks what they need to review, classify changes by semantic effect rather than diff size, file count, or wording size. Trace each change back to the first authoritative rule that introduced it.

1. **Must review:** A change adds, removes, or alters a requirement, entity, field, identity, state, invariant, decision condition, ownership boundary, source of truth, process branch, failure exit, validation rule, publication gate, security boundary, or externally observable behavior.
2. **Sample review:** A previously confirmed logical change is synchronized into summaries, diagrams, detailed sections, hard rules, or related specifications without adding independent semantics. Group all such locations under the originating logical change instead of asking for line-by-line review.
3. **Diff scan only:** Terminology, grammar, references, formatting, or residue cleanup changes that preserve every executable and semantic conclusion.
4. **Uncertain:** A change whose semantic effect cannot be proven from the authoritative rule and affected rule graph. Escalate it to human review; never downgrade it merely because the textual edit is small.
5. **Coverage proof:** For every logical change, list the authoritative definition and all synchronized sections, diagrams, hard rules, schemas, and related specifications. State explicitly when expected counterparts were not changed and why.

Treat wording changes as logical changes when they alter identity or lifecycle implications. For example, replacing "published" with "built-in" is not cosmetic when it removes a Registry, release identity, or governance lifecycle.

Do not create an author field, review state, approval object, or parallel checklist in the reviewed system. Human-review triage is a report about the change, not a new product workflow or source of truth.

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
- Apply logical minimality, not linguistic compression. A specification may explain a rule fully, but every concept, field, state, branch, version, and process must carry an independent necessary responsibility.
- For each proposed element, ask: if it is removed and the remaining rules are derived from existing truth, does any required behavior, semantic distinction, validation boundary, auditability, or governance guarantee disappear? If not, remove it.
- Prefer deriving data from authoritative facts over persisting a second representation. Performance caches must be explicitly rebuildable and must not become truth.
- Do not call a design minimal merely because it has fewer words. Dense wording that hides multiple rules, implicit states, or unresolved branches is not simplification.

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

跨 Spec 一致性：
同一 Spec 与相关 Spec 中受影响的定义、引用和冲突。

逻辑最简检查：
可删除项、重复真相，以及不能删除项所承担的独立责任。

最小修正：
1. 需要改变的边界或结构。

演化检查：
首次、失败、并发、增长、版本迁移后的结果。

可直接落盘的硬规则：
仅列已确认且无歧义的规则。
```

When human-review triage is requested, append or provide this focused view instead of repeating the full review:

```text
必须人工确认：
1. 逻辑变化、权威定义、原因和影响。

建议抽查的跨篇同步：
1. 对应逻辑变化，以及同步到的章节、图、Schema 或硬规则。

只需最后扫 Diff：
纯术语、引用、格式或残留清理。

存疑项：
无法证明不改变语义的修改；没有则明确写“无”。

覆盖证明：
每项逻辑变化的权威定义及全部同步落点；指出遗漏或无需同步的理由。
```
