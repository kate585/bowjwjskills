---
name: bowjwj-5page-isolation-iron-rule
description: IRON RULE: 21终端×5页固定隔离，任何更改须Willy同意
type: project
originSessionId: 90be422a-8814-4457-816b-eab01a15d95f
---
All 21 KT terminals use 5-page fixed intervals, locked as iron rule. Source filter: 凯特ai发送.

**How to apply:** NEVER change any terminal's packPage/packPageMax without Willy's explicit approval. Any page change request → ask Willy first.

| Terminal | Pages | Script |
|----------|-------|--------|
| kt01 | 1-5 | fast_send.py --config send_rules_kt01.json |
| kt02 | 6-10 | fast_send.py --config send_rules_kt02.json |
| kt03 | 11-15 | fast_send.py --config send_rules_kt03.json |
| kt04 | 16-20 | fast_send_kt04.py |
| kt05 | 21-25 | fast_send.py --config send_rules_kt05.json |
| kt06 | 26-30 | fast_send.py --config send_rules_kt06.json |
| kt07 | 31-35 | auto_send_kt07.py |
| kt08 | 36-40 | fast_send_kt08.py |
| kt09 | 41-45 | fast_send.py --config send_rules_kt09.json |
| kt10 | 46-50 | fast_send.py --config send_rules_kt10.json |
| kt11 | 51-55 | fast_send.py --config send_rules_kt11.json |
| kt12 | 56-60 | fast_send.py --config send_rules_kt12.json |
| kt13 | 61-65 | fast_send.py --config send_rules_kt13.json |
| kt14 | 66-70 | fast_send.py --config send_rules_kt14.json |
| kt15 | 71-75 | fast_send.py --config send_rules_kt15.json |
| kt16 | 76-80 | fast_send.py --config send_rules_kt16.json |
| kt17 | 81-85 | fast_send.py --config send_rules_kt17.json |
| kt18 | 86-90 | fast_send.py --config send_rules_kt18.json |
| kt19 | 91-95 | fast_send.py --config send_rules_kt19.json |
| kt20 | 96-100 | fast_send.py --config send_rules_kt20.json |
| kt21 | 101-105 | fast_send.py --config send_rules_kt21.json |

Locked by Willy 2026-05-04. Total: 21 terminals × 5 pages = 105 pages.
Pack source: 凯特ai发送 (228页总量, 覆盖46%).
kt07 query fixed: 凯特ai发送：银河v数据4月 → 凯特ai发送 (2026-05-04, 旧查询返回0包).
