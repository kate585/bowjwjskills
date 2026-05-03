---
name: bowjwj-5page-isolation-iron-rule
description: IRON RULE: 21终端×5页固定隔离，任何更改须Willy同意
type: project
originSessionId: 90be422a-8814-4457-816b-eab01a15d95f
---
All 21 KT terminals use 5-page fixed intervals, locked as iron rule. Source filter: 凯特ai发送.

**Why:** 每个终端独占5页区间，杜绝抢包冲突。页区不重叠 = 包不交叉 = 零抢包。

**How to apply:** NEVER change any terminal's packPage/packPageMax without Willy's explicit approval. Any page change request → ask Willy first.

### 凯特组 — 包源: 凯特ai发送 (2,275页)
| Terminal | Pages | Script |
|----------|-------|--------|
| kt01 | 1-5 | fast_send.py --config send_rules_kt01.json |
| kt02 | 6-10 | fast_send.py --config send_rules_kt02.json |
| kt03 | 11-15 | fast_send.py --config send_rules_kt03.json |
| kt04 | 16-20 | fast_send_kt04.py |
| kt05 | 21-25 | fast_send.py --config send_rules_kt05.json |
| kt06 | 26-30 | fast_send.py --config send_rules_kt06.json |
| kt07 | 31-35 | auto_send_kt07.py |

### 小财财组 — 包源: 小财财ai发送 (1,636页)
| Terminal | Pages | Script |
|----------|-------|--------|
| kt08 | 1-5 | fast_send_kt08.py |
| kt09 | 6-10 | fast_send.py --config send_rules_kt09.json |
| kt10 | 11-15 | fast_send.py --config send_rules_kt10.json |
| kt11 | 16-20 | fast_send.py --config send_rules_kt11.json |
| kt12 | 21-25 | fast_send.py --config send_rules_kt12.json |
| kt13 | 26-30 | fast_send.py --config send_rules_kt13.json |
| kt14 | 31-35 | fast_send.py --config send_rules_kt14.json |
| kt15 | 36-40 | fast_send.py --config send_rules_kt15.json |

### 威龙组 — 包源: 威龙ai发送 (7,678页)
| Terminal | Pages | Script |
|----------|-------|--------|
| kt16 | 1-5 | fast_send.py --config send_rules_kt16.json |
| kt17 | 6-10 | fast_send.py --config send_rules_kt17.json |
| kt18 | 11-15 | fast_send.py --config send_rules_kt18.json |
| kt19 | 16-20 | fast_send.py --config send_rules_kt19.json |
| kt20 | 21-25 | fast_send.py --config send_rules_kt20.json |
| kt21 | 26-30 | fast_send.py --config send_rules_kt21.json |

Locked by Willy 2026-05-04. Total: 21 terminals × 5 pages = 105 pages (3组独立页区).
跨组页号独立计数，三组各从第1页起。
