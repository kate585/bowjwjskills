---
name: bowjwj-pack-page-iron
description: 铁律 — kt07终端永久固定第19-21页，任何情况下不得更改
type: feedback
originSessionId: cd97d1a6-60b3-422d-8a5b-40e156296183
---
# 铁律: kt07 终端永久固定第19-21页 (2026-05-03 Willy)

**Rule**: kt07 终端固定从 page=19,20,21 获取号码包，任何情况下不可更改。

**Why**: Willy 明确指定 kt07 独占第19-21页，避免与其他终端和凯总巴西抢包。

**How to apply:**
- `PACK_PAGES = [19, 20, 21]` 永久锁定
- 每页30s冷却重试最多3次
- 任何试图修改 PACK_PAGES 的行为都是违规
- 这是最高优先级铁律
