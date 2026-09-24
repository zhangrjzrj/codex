# Smoke Run Schema

Each run has one directory named with a sortable ID such as `b0-20260924-153000`.

```text
<evidence-root>/smoke/<run-id>/
  manifest.json
  commands.txt
  logs/
  artifacts/
  verdict.txt
```

`manifest.json` contains the declared claim and frozen inputs before execution:

```json
{
  "run_id": "b0-20260924-153000",
  "kind": "baseline",
  "claim": "The client launches and displays the selected scene.",
  "inputs": {
    "revision": "...",
    "package_sha256": "...",
    "asset_sha256": "...",
    "environment": "..."
  },
  "gates": [
    "process is alive",
    "runtime reports ready",
    "captured image contains render output"
  ],
  "baseline_run_id": null,
  "verdict": "PENDING"
}
```

`commands.txt` records the exact commands or controls used. `verdict.txt` is a concise final statement: `BASELINE_PASS`, `EXPERIMENT_PASS`, or `FAIL: <first failed gate>`.

Store hashes and other produced facts in separate text or JSON files and reference them from the manifest. Do not replace declared inputs after a run starts.
