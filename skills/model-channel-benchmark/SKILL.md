---
name: "model-channel-benchmark"
description: "Benchmark every model available under one fixed Codex provider through independent CLI processes, measuring end-to-end latency, success rate, timeout rate, instruction adherence, P50/P95, and error categories without changing providers or credentials. Use when selecting the most stable model for the current channel, inventorying model behavior, or repeating multi-CLI model comparisons fairly."
---

# Model Channel Benchmark

Use `scripts/benchmark_models.py` for repeatable measurements under one fixed provider. Treat each request as a fresh CLI process and save machine-readable evidence.

## Workflow

1. Lock the current provider and its existing credentials for the entire benchmark. Do not switch providers or tokens while comparing models.
2. Enumerate that provider's complete declared model IDs from its authenticated `/v1/models` endpoint when available. Print only model IDs.
3. Separate text, image, review-only, and other specialized models. Do not rank incompatible modalities with one prompt.
4. Choose one explicit prompt and expected output. Prefer `只输出 OK，不要解释。` with expected output `OK` for transport/latency checks.
5. Run one warm-up request per model when measuring sustained latency. Exclude warm-up from the formal result.
6. Run at least 3 formal requests for a quick comparison and 10 for a default-model decision.
7. Execute models in interleaved order when possible. Avoid testing one model only during a different network/load window.
8. Report request success separately from strict output adherence.

## Run

```powershell
python scripts\benchmark_models.py `
  --models gpt-5.6-luna gpt-5.4-mini gpt-5.5 `
  --runs 3 `
  --timeout-sec 60 `
  --prompt "只输出 OK，不要解释。" `
  --expected "OK" `
  --output-dir .j-evidence\model-benchmark
```

By default, inherit the provider already selected by the current CLI configuration. Use `--provider <name>` only to pin that same provider explicitly; never combine results from different providers in one ranking.

The script writes:

```text
results.json
results.csv
summary.json
runs/<model>/<run>.stdout.jsonl
runs/<model>/<run>.stderr.txt
```

## Interpret Results

- `exit_code = 0`: the CLI request completed successfully.
- `strict_match = true`: the final agent message exactly matches the expected output.
- `timed_out = true`: the request exceeded the explicit wall-clock limit and its process tree was terminated.
- HTTP `401`: current-provider credential failure, not model latency.
- Reconnect exhaustion or HTTP `5xx`: channel/provider instability.
- CLI argument or trusted-directory errors: harness failure; exclude them from model statistics.
- P50 describes typical latency; P95 exposes long-tail stalls.

Do not call a model "stable" from latency alone. Require high request success, low timeout/error rate, acceptable strict adherence, and controlled P95.

## Fairness Rules

- Keep the current provider, credentials, prompt, reasoning settings, timeout, and CLI version fixed.
- Use independent ephemeral sessions; do not reuse conversation history.
- Do not run incompatible image models through a text-only benchmark.
- Do not merge results from different providers; start a separate evidence directory and report if provider comparison is explicitly requested later.
- State that CLI wall-clock time includes process startup and transport overhead; it is not pure model TTFB.
- Preserve raw JSONL and stderr, but redact secrets if a provider unexpectedly echoes request headers.

## Stop Rules

- Stop the benchmark after repeated credential failures because no model under that provider can be judged fairly.
- Stop a model after the requested run count; never add hidden retries.
- Mark a result incomplete when the harness fails or output is buffered without per-run evidence.
