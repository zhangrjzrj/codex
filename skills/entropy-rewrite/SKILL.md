---
name: "entropy-rewrite"
description: "Rewrite complex sentences, specifications, protocols, requirements, and architecture notes into lower-entropy expressions without changing their meaning, responsibilities, constraints, or failure boundaries. Use when the user asks to reduce information entropy, split a long sentence, clarify dense logic, make text suitable for human reading, or compare old and new wording by responsibility."
---

# Entropy Rewrite

Rewrite dense expressions by reducing ambiguity, duplication, and hidden relationships while preserving the original logical content.

## Core rule

Do not optimize for fewer words. Optimize for fewer possible interpretations and fewer relationships that the reader must hold at once.

Preserve:

- every valid responsibility;
- every condition and exception;
- every owner and direction of a relationship;
- persistence, failure, authorization, and publication boundaries;
- the distinction between facts, projections, candidates, decisions, and commands.

## Workflow

1. Extract the source meaning before rewriting.
2. Split the source into independent responsibilities.
3. Mark each responsibility as keep, remove, move, merge, or unresolved.
4. Remove duplicated wording without removing a unique responsibility.
5. Rewrite each responsibility as a short positive rule, a table row, or one flow edge.
6. Use an ASCII flow or data diagram when relationships are easier to read visually.
7. Compare the rewritten responsibilities against the source and report omissions or newly introduced rules.

## Output format

For a review request, provide:

```text
Source contains N responsibilities:
1. ...
2. ...

Rewrite contains M responsibilities:
1. ...
2. ...

Responsibility comparison:
Keep: ...
Remove: ...
Move: ...
Add: ...
Omissions: none / ...
```

For a rewrite request, provide the rewritten text first, followed by a short responsibility check. Do not silently invent a rule to make the text sound complete.

## Precision safeguards

- Never delete a paragraph merely because it contains an obsolete term; isolate the obsolete responsibility first.
- If one paragraph mixes two layers, split the layers before deleting anything.
- If a rule is valid only for one subsystem, state that scope explicitly.
- Keep one authoritative statement for each responsibility and point later sections to it.
- Prefer positive rules over chains of negative reminders.
- Do not turn an explanation, example, or temporary calculation into a persistent schema field.
- If the source is ambiguous, identify the ambiguity instead of guessing.

## Suitable forms

Use the form that minimizes interpretation cost:

- short sentences for independent rules;
- tables for old-to-new responsibility mapping;
- ASCII flowcharts for process order and ownership;
- tree diagrams for data structures;
- before/after comparisons for migration review.

This skill changes expression, not the underlying design. Any semantic change must be called out explicitly for human approval.
