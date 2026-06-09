---
name: messiah-feedback-loop
description: "Run a goal-driven closed feedback loop for Messiah tasks: execute, collect evidence, analyze, patch or adjust plan, build if needed, verify again, and keep iterating until the goal is reached or a real blocker is proven."
---

# Messiah Feedback Loop

## When to use

Use this skill when the user explicitly asks for:

- 用反馈闭环方式做
- 闭环做到目标达成
- 自循环直到成功
- 按闭环执行直到达到目标
- 不要停在分析，直接循环推进

This skill is the orchestration rule for iterative problem solving.
It is not a replacement for the existing Messiah skills. It decides which existing skill to use each round and keeps the loop moving until there is a clear outcome.

## Goal

Turn a user target into a repeatable loop:

1. Define target and success condition
2. Run the smallest useful verification
3. Collect evidence
4. Analyze the result
5. Patch code or adjust execution plan
6. Build if needed
7. Verify again
8. Repeat until pass or a real blocker is proven

## Default loop

```text
目标确认
-> 后台启动目标进程并记录 PID
-> 执行测试/命令
-> 收集 result.json / commands.trace / client log / dump / patch / build log
-> 周期检查进程状态、窗口状态、日志推进和超时条件
-> 如发生进程退出/连接断开/卡死/致命弹窗，记录证据并熔断目标进程
-> 分析根因
-> 选择动作
   -> 改代码
   -> 改脚本/参数
   -> 改执行链路
   -> 补日志/补证据
-> 如有必要则编译
-> 再执行
-> 判断是否达成目标
-> 未达成则继续下一轮
```

## Round contract

Each round should explicitly produce:

1. 本轮目标
2. 本轮证据
3. 本轮判断
4. 本轮动作
5. 下一轮是否继续

Do not stop at analysis only unless there is a real blocker.

## Skill routing

Prefer the minimal existing skill needed for the current round:

- Full launch/login/scenario/artifacts:
  use `messiah-test-loop`
- Direct control on a running client:
  use `messiah-telnet-control`
- Build / compile / machine-readable errors:
  use `messiah-ib-build-fix`
- RenderDoc `.rdc` pass or shader analysis:
  use `messiah-renderdoc-analyzer`
- EXR header verification:
  use `messiah-exr-header-reader`
- Chinese direct code explanation:
  use `zh-direct-code-explainer`

## Scenario guidance

### 1. Playback / record / login / test workflow

If the user target is about:

- nbs_playback
- aov_record
- launch/login
- end-to-end test pass

Then:

- Prefer `messiah-test-loop` for the first full reproduction
- If the client is already up and the user wants speed, switch to `messiah-telnet-control`
- Always read produced run artifacts before deciding the next move

### 2. Code-fix workflow

If the issue clearly requires code changes:

- Reproduce first
- Extract the first useful evidence
- Patch the smallest responsible code path
- Build only the required target
- Re-run the verification

### 3. Rendering / depth / AOV workflow

If the target is about:

- depth_flag
- EXR metadata
- Water / Transparent / Char depth
- RenderDoc capture interpretation

Then:

- Verify runtime evidence first
- Prefer header / capture / log evidence before code changes
- Only patch after the failing stage is narrowed down

## Stop conditions

Stop only when one of these is true:

- The user goal is achieved
- There is enough evidence that the current path cannot continue
- The environment is missing a hard requirement
- The user explicitly stops or changes direction

## Guardrails

- Do not change staged files unless the user explicitly asks
- Do not make speculative large refactors in the middle of a loop
- For Windows GUI test loops, prefer background launch with a recorded PID. Periodically inspect process state, window/dialog state, recent logs, and timeout conditions.
- If the target process exits, Telnet disconnects, automation stalls, or a fatal dialog appears, record evidence and terminate the target process before diagnosing the run.
- Prefer the smallest next verification that can cut uncertainty
- When a failure happens, first decide whether it is:
  - execution failure
  - environment failure
  - code failure
  - observability failure
- If the current evidence is too weak, the next round may be “collect more evidence” rather than “patch now”

## Response style in loop mode

- Conclusion first
- Evidence before speculation
- Show the key code or key log directly when explaining
- Keep each round easy to scan
- Be explicit about why the next round is chosen

## Suggested trigger sentence

Examples the user may say:

- 用反馈闭环的方式，把这个问题做到成功
- 进入反馈闭环模式，直到目标达成
- 不要停在分析，按闭环继续推进
- 用闭环方式修到 pass 为止

When these appear, use this skill as the top-level execution policy.
