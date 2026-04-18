# Scenario Contract

## Goal

Keep one stable loop skill while supporting many test behaviors as pluggable scenarios.

## Built-in Scenarios

- `aov_record`
  - Start: `NBSTest().AOVPre()`
  - Done: recording state seen once, then returns to non-recording.

- `nbs_playback`
  - Start: `NBSTest().startPre()`
  - Done: playback seen once, then montage stops and decoder id returns to -1.

## Standalone Repro

- `MiniGif` 生命周期复现已拆到独立旁路脚本：
  - `scripts/run_minigif_repro.py`
  - `scripts/in_game/minigif_repro_operator.py`
- 目的：不污染通用 `run_loop.py` / `auto_loop_operator.py` 的正常登录与播放场景。

## Add a New Scenario

1. Add start logic in `scripts/in_game/auto_loop_operator.py` inside `start_scenario`.
2. Add completion polling logic in `poll_scenario`.
3. Add CLI mapping in `scripts/run_loop.py` parser `--scenario` choices.
4. Keep payload format stable (`AUTO_JSON::...` + `AUTO_END`).
5. Validate by running one round and checking `result.json` and `commands.trace`.

## Result Expectations

Every run must output:

- `result.json` with `phase_status`, `outcome`, `next_action`
- `commands.trace`
- copied client logs
- dump files (if crash)
- `fix_plan.md` when outcome is not pass and approval gate is enabled
