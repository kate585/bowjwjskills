---
name: bowjwj-terminals-config
description: 4 terminals with fixed packs/cycle, locked — no changes without Willy approval
type: project
originSessionId: 851cf687-3b38-401b-b240-381ee0d97f16
---
## 终端配置 (2026-05-03 Willy设定)

| 终端 | 间隔 | 包/轮 | 
|------|------|-------|
| 001号 | 3s | 6包 |
| 002号 | 3s | 7包 |
| 003号 | 3s | 8包 |
| 004号 | 3s | 9包 |

**Why:** Willy手动分配每终端不同发信量，梯度分布降低风控同时保证总量。

**How to apply:**
- 配置锁定在 send_rules.json `terminals` 字段, `_locked: true`
- **铁律**: 没有Willy明确允许, 任何终端不可随意更换packsPerRound/cycleSeconds
- Tier动态调整 (CTR驱动加减量) 不可覆盖终端固定配置
- 启动时用 `--terminal 001/002/003/004` 指定终端号
- fast_send.py 读取 `RULES["terminals"][terminal_id]` 取 packsPerRound/cycleSeconds
