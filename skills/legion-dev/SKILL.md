---
name: legion-dev
description: "军团化协议：先执行卡，按证据门禁推进，明确切换与停止条件。"
---

# legion-dev（军团化协议）

## 目标
把高风险任务转成低歧义协议：先定义执行卡，再按证据门禁逐轮推进，过程可审计、可回滚、可交接。

## Entry（启用条件）
满足任一条件即启用：
- 高风险改动（改分支指针、跨模块大改、批量重构）。
- 任务需要明确门禁后才能放行。
- 已出现多轮重复尝试但无新增证据。

启用后第一步必须先产出 `Execution Card`。

## Execution Card（执行前必填）
执行前填写：
- Goal：一句话目标。
- Scope：范围（in/out）。
- Steps：3-7 个顺序步骤。
- Gates：每步 PASS/FAIL 标准。
- Evidence：每步用什么证据判定。
- Risks：前三风险与缓解措施。
- Stop Conditions：何时停止并升级。

未确认执行卡前，不执行高风险变更。


## 角色契约（轻量）
- Orchestrator（编排者）：定义执行卡、收敛门禁、裁决本轮决策（next/switch/stop）。
- Developer（执行者）：按本轮目标做最小实现，提供改动摘要与必要证据。
- Tester（验证者）：按门禁给出 PASS/FAIL 与复现实证，不扩展需求。
- Reviewer（审阅者）：基于“改动摘要 + 门禁证据”做放行/驳回。
- 最小协作顺序：Orchestrator -> Developer -> Tester -> Reviewer -> Orchestrator（决策 next/switch/stop）。

## Round Protocol（每轮固定输出）
每轮必须输出：
1. Round Goal（本轮目标）
2. Round Evidence（本轮证据）
3. Round Action（本轮动作）
4. Round Decision（`next` | `switch` | `stop`）

## Gate Protocol（门禁协议）
每步必须有二值门禁：
- PASS：进入下一步。
- FAIL：停止前进，先处理失败路径，再评估。

每步最小证据包：
- Step ID
- 改动摘要
- 门禁结果（PASS/FAIL）
- 关键证据（日志/测试/断言/快照）

## Strategy Rules（策略规则）
每轮只允许一个主策略：
- 逆向：从失败点沿证据链向上回溯。
- 正向二分：仅在逆向受阻时拆分假设收敛。

同一轮不得把两者同时作为主策略。

## Switch Rules（切换条件）
从逆向切到正向二分，仅当：
- 上游证据已无法继续延展，且
- 当前路径没有实质新增证据。

切换时必须记录：
- 当前卡点
- 卡住原因
- 切换后第一道门禁

## Escalation Rules（升级条件）
满足任一条件，升级到人工决策点：
- 连续 2-3 轮无新增证据；
- 外部依赖/权限阻塞导致无法推进。

## Stop Rules（停止条件）
仅在以下条件之一成立时停止：
- 目标已达成且有门禁证据；
- 路径已被充分证据证明不可行；
- 用户明确中止。

## Memory Contract（落盘约定）
项目内落盘到 `.codex-memory/`：
- `index.md`：主题索引
- `threads/*.md`：轮次记录

每轮记录最小字段：
- Goal
- Evidence
- Action
- Decision
- Next Step