---
name: "gitlab-smoke-history-analyzer"
description: "Analyze GitLab smoke-test pipeline history and artifacts to locate the first failing commit and distinguish build, device, playback, and infrastructure failures."
---

# GitLab Smoke History Analyzer

Use this skill when a GitLab Android, iOS, or multi-device smoke pipeline regresses and the task requires evidence from historical job artifacts.

## Outcome

Produce an evidence table for the requested commit range. Each row identifies the commit, pipeline, job, execution state, parsed smoke result, and failure stage. State the last successful and first failed commit only when adjacent comparable evidence proves that boundary.

## Procedure

1. Identify the exact project, branch or commit range, relevant job names, and expected smoke contract. Do not compare jobs from different devices, runners, build modes, or test contracts as if they were equivalent.
2. Obtain pipeline and job metadata first. Use the GitLab API with a user-provided token when available; otherwise use an authenticated browser session or supplied artifact archives. Record unavailable or canceled jobs as evidence gaps, not code failures.
3. Download each job artifact into an ignored local evidence directory. Preserve the archive and extract it into a directory named with pipeline and job IDs.
4. Run `scripts/analyze_smoke_history.py` against the extracted artifacts. Read `references/evidence-contract.md` when interpreting a result.
5. Compare the last successful and first failed comparable commits with Git diff. Separate a stable code regression from a Runner/device/environment failure.

## Safety And Interpretation

- Default to read-only GitLab operations. Do not retry, cancel, or trigger pipelines without explicit authorization.
- `smoke-results` is the primary execution evidence. Pipeline metadata is required when artifacts are missing, incomplete, canceled, or timed out before the test script emitted results.
- Treat result JSON as the mechanical pass/fail authority; treat screenshots as visual diagnostic evidence only.
- Do not claim a first-failure boundary when there are missing, canceled, incomparable, or non-executed runs between candidates.
- Do not attribute a failure to a commit until the artifact evidence and the commit diff support the claim.

## Commands

Analyze already downloaded archives or extracted `smoke-results` directories:

```powershell
python scripts/analyze_smoke_history.py `
  --input <evidence-root> `
  --output <evidence-root>/history-report.json
```

For GitLab API acquisition, read [references/gitlab-api.md](references/gitlab-api.md). The API helper only downloads metadata and artifacts; it does not mutate GitLab state.

