# Smoke Evidence Contract

## Primary Evidence

Read these files when present:

| Evidence | Meaning |
|---|---|
| `nbs_six_parallel_playback_result.json` | Mechanical six-stream outcome: `success`, count, per-stream advancement, completed steps, and errors. |
| `result.json` | Runner summary, platform, source commit, and final status. |
| `xcodebuild.log` | iOS compilation and signing result. `** BUILD SUCCEEDED **` proves the Xcode build phase. |
| `gradle-build.log` | Android compilation/package result. `BUILD SUCCESSFUL` proves the Gradle build phase. |
| `cmake-configure.log` | Native dependency resolution and CMake configuration. |
| `install.log`, `launch.log`, `processes.log` | iOS deployment and launch evidence. |
| `android.log`, `activity-top.txt`, `device-files.txt` | Android launch, runtime, and device-file evidence. |
| screenshots | Visual diagnosis only; do not override a result JSON with a screenshot. |

## Failure Stages

Classify one dominant stage per job in this order:

1. `pipeline` - job never ran, was canceled, or has no execution evidence.
2. `configure` - CMake or dependency resolution failed.
3. `build` - Gradle or Xcode build failed.
4. `install` - application installation failed.
5. `launch` - application did not start or terminate unexpectedly.
6. `playback` - result JSON exists and shows a failed stream contract.
7. `validation` - result JSON is mechanically successful but the job still fails in a later validator.
8. `passed` - result JSON passes the expected contract, or the relevant build-only job has an explicit successful build marker.
9. `unknown` - artifact evidence is absent or insufficient.

## Comparability

Only use neighboring results to identify a regression boundary when all are true:

- same job purpose and test contract;
- same target platform and ABI;
- same device or explicitly equivalent device pool;
- no canceled/missing/incomplete run between the candidates;
- relevant artifact exists for both sides.

