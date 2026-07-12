---
name: "adversarial-review-loop"
description: "Run a first-principles, multi-subagent adversarial review loop with explicit P0-P3 issue triage and a hard stop rule. Use when the user asks for 第一性原理、多 subagents 对抗式 review、review 大闭环、根据 review 闭环修复、判断是否该停止 review、避免无限回归 or review until risk is acceptable."
---

# Adversarial Review Loop

Use this skill to turn long review prompts into a bounded review-development-review convergence loop.

## Core Principle

Run review, implement fixes when justified, review again, and repeat until the main goal risk has fallen to an acceptable level and the expected benefit of more review is lower than the complexity, regression, or delay risk it may introduce.

Do not use "can we still find issues?" as the stop condition. Use "do remaining issues block the current goal?" as the stop condition.

## Workflow

1. State the current main goal in one sentence.
2. Define the review scope and non-goals.
3. Split the review into 2-4 independent surfaces.
4. Spawn subagents only for read-only review, reproduction, testing, log analysis, or patch suggestions unless the user explicitly authorizes code edits.
5. Ask each subagent to review from first principles and report evidence, not broad opinions.
6. Locally inspect the critical path yourself; do not blindly forward subagent conclusions.
7. Merge findings and classify every issue as P0, P1, P2, or P3.
8. Let P0 findings drive implementation in the current loop.
9. After implementation, rerun targeted review against the changed risk surface.
10. Repeat review -> implementation -> targeted review until no P0 remains and P1/P2/P3 do not block the current main goal.

## Issue Triage

- `P0`: Blocks the current main goal or can break the main runtime path. Fix in the current loop.
- `P1`: Should be fixed before production or final release, but does not block this loop's main goal.
- `P2`: Useful follow-up, observability, cleanup, performance, or maintainability improvement.
- `P3`: Theoretical, speculative, already mitigated, or not worth handling now.

Only P0 findings may automatically extend the current review-development-review loop. P1/P2/P3 findings are not ignored: record them and evaluate whether they create cumulative architectural smell.

Promote non-P0 findings when justified:

- If multiple P1/P2/P3 findings combine into a credible risk to the main goal, promote the combined risk to P0 or define a bounded follow-up loop.
- If fixing them would mainly pursue theoretical cleanliness and increase complexity, regression, or delivery risk, stop and record them.
- If the user changes the main goal, reclassify all findings against the new goal.

## Stop Rules

Stop the large review loop when all are true:

- The main end-to-end path is stable enough for the current phase.
- Known remaining issues are classified and none are P0.
- Remaining P1/P2/P3 findings have been checked for cumulative architectural smell and do not credibly threaten the current main goal.
- More review is more likely to add complexity, weaken a stable boundary, delay delivery, or reopen settled architecture than to reduce current-goal risk.
- A standard regression or acceptance test can now provide better evidence than more architectural review.

When stopping, say explicitly:

- "Stop large review now."
- Which issues remain and why they are not P0.
- What acceptance test or rollout step should happen next.

## Guardrails

- Do not expand scope just because subagents found more possible improvements.
- Do not loosen stable safety gates without direct evidence that they block a valid path.
- Do not convert P1/P2/P3 into immediate refactors unless the user explicitly changes the goal.
- Do not stop immediately after the first review when P0 exists; implement the P0 fix, collect evidence, and re-review the affected surface.
- Do not treat P1/P2/P3 as harmless by default; judge whether they form a pattern that changes the risk classification.
- Do not let parallel Codex instances independently modify core architecture when there is a main surgeon thread.
- Prefer the main surgeon Codex for implementation and final integration.
- Let other Codex agents act as reviewers, testers, reproducers, and evidence collectors.

## Recommended Subagent Slices

Pick slices that match the system under review. Examples:

- Frontend state/projection/UI consistency.
- Backend identity/event/runner lifecycle.
- MCP/tooling/trace/learning loop.
- Deployment/config/environment boundary.
- Regression test and evidence quality.

## Output Format

Use concise Chinese output by default:

```text
结论：
是否继续大闭环，或是否应停止。

P0：
- ...

P1：
- ...

P2/P3：
- ...

已清掉：
- ...

下一步：
- 标准回归 / 真机验收 / 只修 P0 / 推进上线
```
