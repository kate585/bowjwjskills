---
name: bowjwj-batch-send
description: bowjwj 按 seq 批量/单个/条件发信协调器。**任何时候** Willy 说"发 #67"、"发 #67,#120"、"扫 Smart 侧未测"、"扫全部 561"、"test-only 扫一批"时加载。解析 targets → 安全闸门 → 调 bowjwj-auto-campaign 底层 helper 去 test-send。只做协调, 不自带 bash/python 脚本。
---

# bowjwj-batch-send (协调器)

## 新后台覆盖规则 (2026-05-26)

本节优先于后面的旧 `bowjwj.cc` 规则。

- Base URL: `https://aicrm.bo-pro.cc`
- 必带 header: `Authorization: Bearer $JWT` 和 `X-AICRM-Tenant: aicrm-default`
- 发信前先读 `bowjwj-aicrm` 的“新后台覆盖规则”。
- 新后台有 API 字典：`GET /api/_meta/endpoints?search=send-direct`、`GET /api/_meta/endpoints?module=campaigns`。如果接口行为不确定，先查字典，不凭旧记忆拼 body。

### 发信入口分层

旧的模板直发入口仍存在：

```text
POST /api/campaign-templates/:id/send-direct
POST /api/campaign-templates/:id/send-direct/test-send
```

但新后台还提供 campaign 和编排入口：

```text
POST /api/campaigns/bulk-launch
POST /api/campaigns/bulk-send
POST /api/campaigns/:id/launch
POST /api/campaigns/:id/send
POST /api/campaigns/:id/send-batch
POST /api/campaigns/:id/test-send
GET/POST /api/auto-send-plans...
GET/POST /api/orchestrated-send-tasks...
```

默认仍按安全模式 `test-send`，不裸直发；涉及 `bulk-send`、`run-now`、`orchestrated-send-tasks`、`auto-send-plans/*/publish|run-now` 必须单独确认。

### 短链模式

`shortlinkMappingMode` 现在是三值：

- `pack`
- `recipient`
- `content`

`content` 是固定文案短链，短信原文必须已包含可用短链，不替换 `${shortUrl}`。批量发信脚本不能把 `content` 当 `pack` 或 `recipient` 自动补短链域名。

### 号码包选择

新后台号码包选择要考虑包源权限：

```text
GET /api/phone-packs/categories?backendInstanceId=<BID>&requiredAccess=USE&poolMode=own_with_public_fallback
GET /api/phone-packs/categories/:key/packs?backendInstanceId=<BID>&requiredAccess=USE&poolMode=own_with_public_fallback
GET /api/phone-packs/categories/:key/selection?backendInstanceId=<BID>&requiredAccess=USE&poolMode=own_with_public_fallback
```

挑包过滤在旧规则基础上追加：

- `sourcePoolType`：优先个人可用池，公共池只作兜底。
- `labelLifecycleStatus`：只用可用态，跳过 cooling/deprecated 等异常态。
- `labelRiskStatus`：跳过 high risk。
- `dataViewLocked=true` 时不假设能看明细。

## 何时触发

- `发 #N` / `跑 #N`              → 单组合
- `发 #A, #B, #C`                → 指定若干
- `发 Smart 侧前 10 个未测`       → 过滤后取 N
- `扫全部未测` / `扫全部 561`     → 全量
- `test-only 扫 #1-#50`          → 只测不放量模式

任何含 "seq#" 或"批量扫"意图的发信请求都走本 skill。单纯"查组合"不触发本 skill, 走 dashboard 看。

## 协调目标

本 skill 是**薄协调层**, 不自带脚本, 也不直接调后台 API。真正发送走 `bowjwj-auto-campaign` 里的 `/send-direct/test-send` + 放量流程, 只是批量发起 + 守门 + 结果汇总。

## 数据源 (都已经在)

```
pool.json           ~/.hermes/state/bowjwj/pool.json          (561 组合定义, seq 1-561)
stats.db            ~/.hermes/state/bowjwj/stats.db           (combo_coverage 表, 最新覆盖)
events.jsonl        ~/.hermes/state/bowjwj/events.jsonl       (法医证据)
dashboard data.json ~/.hermes/state/bowjwj/dashboard/data.json (561 合并后数据)
```

## targets 解析 (伪码, 非脚本, AI 现读现算)

```
输入 → 目标 seq 集合:

1) "#67" / "#67,#120,#200"
   → [67, 120, 200]

2) "Smart 侧前 10 个未测"
   → SELECT seq FROM combo_coverage 
     WHERE carrier_group='Smart' AND tested_rounds=0 AND NOT is_frozen
     ORDER BY seq LIMIT 10

3) "扫全部未测"
   → SELECT seq FROM combo_coverage WHERE tested_rounds=0 AND NOT is_frozen
   (561 - 已测 - 冻结)

4) "扫所有 CTR>2% 的组合再测一轮"
   → SELECT seq FROM combo_coverage WHERE tested_rounds>0 
     AND total_click*1.0/total_sent > 0.02

解析完打印一个清单给 Willy 确认, 再动手。
```

## 🔴 每 test-send POST = 1 个 approval (2026-04-24 实测)

10 组合 batch = 10 次 POST `/send-direct/test-send` = **10 个独立 approvalId**. Willy 要 TG 批 10 次.

原因: URL path 绑 `tpl_id` (`/api/campaign-templates/:id/send-direct/test-send`), 多 tpl 多请求.

实测节奏: 串行 POST 间 `time.sleep(1)` 足够, 无 rate limit.

合并可能性: `/api/campaign-templates/ai-send-all-templates/test-send` 传 `templateIds=[...]` 理论上多 tpl 共 1 approval, 但**没实测过**, 且 URL 是 "ai-" 前缀, 语义可能不同 (AI 随机挑模板 vs 精确用 N 模板). 需要时先小样本验证.

## 🔴 "分散通道"挑 seq 算法 (情报最大化)

按 `seq ASC LIMIT N` **错** — seq 低位是同通道不同模板, 挑出来 10 个可能全在 1 个通道上, 探测价值 0.

**正确算法**: 按 ch_id GROUP 轮询取样, 一次扫越多不同通道越好:

```python
# 每 carrier 下, 每个 ch_id 取第 1 个未测 combo
chs = conn.execute("SELECT DISTINCT ch_id FROM combo_coverage WHERE carrier_group=?",
                   (car,)).fetchall()
picked = []
for ch in chs[:need_count]:
    row = conn.execute(
        "SELECT seq, tpl_id, ch_id FROM combo_coverage "
        "WHERE carrier_group=? AND ch_id=? AND tested_rounds=0 AND NOT is_frozen "
        "LIMIT 1", (car, ch['ch_id'])
    ).fetchone()
    if row: picked.append(row)
```

情报密度:
- seq ASC LIMIT 10 (错): 10 组合跨 1-2 通道, 只探测 1-2 通道
- GROUP BY ch_id 挑 (对): 10 组合跨 10 通道, 1 轮覆盖整个通道池

## 🎯 告警基础设施 (2026-04-24 P0 极简版就位)

batch-send 发起后主动 raise_alert(), 让 Willy 不盯屏也知道状态:

```python
import sys
sys.path.insert(0, os.path.expanduser("~/.hermes/state/bowjwj"))
import alert_raise as ar

ar.raise_alert(
    source="batch-send", category="system", severity="P1",
    title=f"batch{N} 已发起 {ok}/{total}, 去 TG 批准",
    entity_id=round_id,
    detail={"round_id": round_id, "count": ok}
)
```

TG credentials 本地: `~/.hermes/state/bowjwj/.tg-creds.json` (bot 8619649742, chat 6694261813). 24h 内同 fingerprint 去重, P0/P1 立即 TG, P2/P3 只落库.



| N | 闸门 |
|---|------|
| 1 | 直接跑, 无警告 |
| 2-10 | 显示 seq 清单 + 预估预算 + TG 次数, 等 A/G 回复 |
| 11-50 | 摘要模式: 组合数/预算/TG 次数/预估时长, 要 "GO" |
| 51+ | **强制二次确认**: 说清楚"这是大规模, 预算 $X, TG 要点 N 次, 要 30min+" 要 Willy 明示 "确认扫" |

**闸门不走 skill 脚本**, 走 AI 对话里的 Q/ABC 模式 (遵循 Willy 澄清式偏好)。

## 并发参数 (默认值)

```
default_concurrency     = 10         (同时并行几个 test-send 请求)
default_pack_per_combo  = 20         (每组合吃 20 个号码包, 测 1 剩 19)
default_budget_cap_usd  = 15.0       (超此预算 skill 主动拒绝)
default_mode            = test-send  (不直接 direct, 保底)
inter_batch_sleep_sec   = 2          (创建 approval 之间隔 2 秒, 避免后台节流)
```

### test-only 模式 (Willy Q3 选了 I)

```
mode = "test-only"
  → 所有 targets 只跑 /send-direct/test-send
  → clickCount 监测完就结束, 不触发放量 approval
  → 用途: 大规模探 CTR, 不真放量, 单成本 $0.28/组合
  → 闸门降级: 51+ 仍需明示, 但预算警告阈值 raise 到 $50
```

## 号码包绑定 (关键)

每组合**必须**配对应运营商号码包, 不能瞎配:

```
Smart 侧 (seq 1-231)   → 配 source 含 "Smart" 的包   (33K 包可用)
Globe 侧 (seq 232-528) → 配 source 含 "Globe" 或 "DITO" 的包 (7.7K 可用)
全网通  (seq 529-561)  → 任意有 cleanCount>0 的包

额外过滤 (bowjwj-auto-campaign skill 已定):
  source 含 "yo家黑名单" → 跳过
  reuseLocked=true         → 跳过
  assignmentCampaignId 非空 → 跳过 (系统侧认为已用)
```

运行时拉 `~/.hermes/state/bowjwj/dashboard/data.json` 的 `inventory.top_sources` 或直接查 `/api/phone-packs?backendInstanceId=...` 过滤。

## 完整流程 (AI 主协调的 7 步)

每次批量发起:

1. **解析 targets** → 拿到 `seq_list`
2. **打开 stats.db**, 对每个 seq 拿 tpl_id + ch_id + carrier_group
3. **预算计算** = `len(targets) × 0.28`, 超 budget_cap 直接拒
4. **号码包挑选**: 按 carrier 分组, 从 `unused + 该 carrier source` 里取 N×pack_per_combo 个
5. **过闸门**: 把清单 + 预算 + TG 次数告诉 Willy, 拿到 A/G/GO/确认扫
6. **分批并发**: 每批 `concurrency` 个并行 `test-send`, 批间 `inter_batch_sleep_sec` 秒
   - 每个请求成功 → `bowjwj_log.round_init(...)` + `round_append_poll(...)`
   - 失败 → 记 `event(kind='send_failed', seq=X, error=Y)`
7. **完成后**: 单行摘要给 Willy + 调 `export.py` 刷 dashboard, 让 Willy 自己 F5

## TG approval 节奏

```
Willy 已明示: 不用 userbot, 不改源码, 接受手批慢
51+ targets 场景 AI 要先问 "TG N 条接连来, 你跟得上吗?"
  跟不上 → 降 concurrency 或分 session 分时段
  跟得上 → GO
```

## 结果产物

每次批量跑完, skill 最后吐一份:

```
📦 批次摘要
  round_id: batch-20260424-nnnn
  targets: [#67, #120, #200, ...]  (N 个)
  成功创 session: N / 失败 M
  累计 sent: XXX
  累计 click: XX (30min 内)
  CTR 达标 (>=3): Y 个
  CTR 不达 (<3): Z 个
  verdict: passed_group=[seq...] / rejected_group=[seq...] / zero_click_group=[seq...]
  下一步建议: "放量 passed Y 个" / "冻结 zero Z 个" / "继续扫剩 N 个"
```

## ⚠️ 已知坑 (继承 bowjwj-auto-campaign)

1. `send-direct` ≠ `send-direct/test-send` — 本 skill 默认走 test-send, 永远不裸 direct
2. approval TTL 10min, 大批量扫时 TG 点慢会过期 → 闸门预警
3. plannedAt 发送窗口规则 — 当前时间不在 BJ 12-02 窗口内, 创了也得等
4. **不改源码**, Willy 明示
5. 号码包 `cleanCount` 是参考值, 实发约 75-85% (去重 15-25%)
6. 同一 (tpl, ch) 短期重测效果衰减, 24h 内再测别期待
8. 批量场景下 `IP_NOT_WHITELISTED` 403 如果触发, 联系 Willy 手动加白 (SUPER_ADMIN 权限)
9. **域名池预检**: `customShortlinkDomainConfigIds` 传多域名系统轮询挑, 发前最好 curl -I 每个域名看 302 还是 timeout. now.vip 等小众域名常挂 (2026-04-24 实测导致 4/19 campaign 打水漂).
8. **send-direct/test-send 必传 7 字段, 缺任一返回 VALIDATION_ERROR**:
   ```json
   {
     "templateIds": ["<tpl_id>"],
     "smsInstanceIds": ["<ch_id>"],
     "phonePackIds": ["<pack_id>"],
     "shortlinkMappingMode": "pack",
     "shortlinkMode": "domain",
     "customShortlinkDomainConfigIds": ["<5 个域名 id>"],
     "titlePrefix": "batch-xxx-seqN",
     "plannedAt": "2026-04-24T00:22:59.000Z"
   }
   ```
   历史已用域名 id (沿用即可): 7d96e095 / 808b87ea / cb4c35a9 / 0fd370ec / 4583d70f
9. **挑 pack 时必须过滤 cleanCount < 20**: 太少没测试意义 (04-24 #1 踩过 clean=4 包, 没发送价值)
10. **每 session 1 请求 1 approval**: 10 组合 = 10 次 POST + 10 次 TG 批准, 不合并
11. **plannedAt = now + 3min** 最稳 (太近可能系统 launch 时已过; 太远 TG 过期前发不完)
12. **发起后必存到 stats.db.sessions + 落盘 rounds/<round_id>/**, 否则监测阶段查不到 cid/sid
13. **监测节奏**: T+5-8min 拉第一次 (status sent), T+15min 看点击起量, T+30min 最终 verdict

## 🔴 必读: POST 前先抄历史 request, 别凭记忆拼 body

2026-04-24 seq #68 实跑踩过:

**现象**: 我凭印象拼 `/send-direct/test-send` body, 只给了 `templateIds/smsInstanceIds/phonePackIds`, 后台报 `VALIDATION_ERROR`:
```
fieldErrors:
  shortlinkMappingMode: [此项为必填项]
  plannedAt: [必须填写文本内容]
```

**根因**: test-send body 有 8 个必填字段 (见 bowjwj-auto-campaign skill E 段), 我只给了 3 个. 更糟的是 plannedAt 写成 null, 后台拒.

**正确做法** (每次拼 body 前 30 秒):
```bash
# 从历史 request 里 cp 一份完整的, 再改 ids
grep -l "test-send" ~/.hermes/state/bowjwj/rounds/*/step1_test_send_request.json
cat ~/.hermes/state/bowjwj/rounds/20260424-0244-smart-MINI-2pack/step1_test_send_request.json
# ↑ 这个是上次成功的完整 body, 照抄
```

**test-send 必填 8 字段清单** (缺一个就 400):
```json
{
  "templateIds": ["<tpl-uuid>"],
  "smsInstanceIds": ["<ch-uuid>"],
  "phonePackIds": ["<pack-uuid>"],
  "shortlinkMappingMode": "pack",
  "shortlinkMode": "domain",
  "customShortlinkDomainConfigIds": ["<domain-uuid-1>", "..."],  // 5-30 条
  "titlePrefix": "seq{N}-YYYYMMDD-HHMM",
  "plannedAt": "<UTC ISO 字符串, 不能 null>"  // 现在+30s 即可
}
```

**plannedAt 格式**: `2026-04-24T14:30:00.000Z` (UTC, ISO 8601). 不是 null/空串/\"now\".

**域名 id 5 个沿用历史** (shortlink-options 返回的 createdAt desc 前 5):
```
7d96e095-a999-49a1-a416-c468fb2a4717
808b87ea-f105-481e-897a-88ef8377fd76
cb4c35a9-7a54-4912-8ef1-fcde5b158d15
0fd370ec-fd7b-4ffe-a5e0-34cc5761a491
4583d70f-500d-4329-9c0f-0834485e94d4
```
(如果发现线上变更, 走 `GET /api/domains/shortlink-options?backendInstanceId=NN33_BID` 重拉)

## 🔑 JWT 读法纪律 (2026-04-24 Willy 明示)

**别用 `op read`, 会弹 TouchID**. 直接读本地:
```python
JWT = open(os.path.expanduser("~/.hermes/state/bowjwj/.jwt")).read().strip()
```
`~/.hermes/state/bowjwj/.jwt` 已 chmod 600, 进 `.gitignore`. JWT 7 天过期 (当前到 2026-05-01), 过期后 Willy 从 1P 重新复制覆盖该文件即可.

## 📝 bowjwj_log API 签名 (别记错)

```python
blog.round_init(round_id)                           # 只接 round_id 一个参数
blog.event(kind="...", **extra_fields)              # 任意 kwargs
blog.http(method, url, status, body, response, note="")  # 5 位置参数 + note kw
blog.round_append_poll(round_id, sessions)
blog.verdict(round_id, status, reason, detail=None)
```

我之前给 `round_init` 传了 `tpl_id=`/`tpl_name=`/`pack_ids=` 全部炸. **不要加, 元数据走单独的 `blog.event(kind="seq_pick", round_id=..., seq=..., tpl_id=..., ...)`**.

## 🖼️ 单发流程最小脚本 (模板)

```python
import os, json, subprocess, time, sys, datetime
STATE = os.path.expanduser("~/.hermes/state/bowjwj")
sys.path.insert(0, STATE)
import bowjwj_log as blog

JWT = open(f"{STATE}/.jwt").read().strip()
H = ["-H", f"Authorization: Bearer {JWT}", "-H", "Content-Type: application/json"]
BID = "c7ee7c4c-ce0a-49c9-880a-9315d07c07b6"

# 从 stats.db combo_coverage 取 tpl_id + ch_id + carrier_group
# (用 seq 查; pool.json 也有全量)

# 按 carrier 过滤选 pack
for page in range(1, 10):
    d = json.loads(subprocess.run(["curl","-sS",*H,
        f"https://bowjwj.cc/api/phone-packs?pageSize=500&page={page}&backendInstanceId={BID}"],
        capture_output=True,text=True).stdout)
    for p in d.get("data", []):
        src = p.get("source") or ""
        carrier_match = {"Smart": "Smart" in src, "Globe": ("Globe" in src or "DITO" in src), "全网通": True}[CARRIER]
        if (p.get("cleanCount") or 0) >= 80 and not p.get("assignmentCampaignId") \
           and not p.get("reuseLocked") and carrier_match and "yo家黑名单" not in src:
            picked = p; break
    if picked: break

round_id = f"batch-{time.strftime('%Y%m%d-%H%M')}-seq{SEQ}"
blog.round_init(round_id)
blog.event(kind="seq_pick", round_id=round_id, seq=SEQ, tpl_id=TPL_ID, ch_id=CH_ID, pack_id=picked["id"])

planned = (datetime.datetime.utcnow() + datetime.timedelta(seconds=30)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
body = {
    "templateIds": [TPL_ID],
    "smsInstanceIds": [CH_ID],
    "phonePackIds": [picked["id"]],
    "shortlinkMappingMode": "pack",
    "shortlinkMode": "domain",
    "customShortlinkDomainConfigIds": [...5 个域名 id...],
    "titlePrefix": f"seq{SEQ}-{time.strftime('%Y%m%d-%H%M')}",
    "plannedAt": planned,
}
url = f"https://bowjwj.cc/api/campaign-templates/{TPL_ID}/send-direct/test-send"
os.makedirs(f"{STATE}/rounds/{round_id}", exist_ok=True)
json.dump({"url":url,"body":body}, open(f"{STATE}/rounds/{round_id}/step1_test_send_request.json","w"), ensure_ascii=False, indent=2)

r = subprocess.run(["curl","-sS","-X","POST",*H,"-d",json.dumps(body),url], capture_output=True,text=True)
resp = json.loads(r.stdout)
json.dump(resp, open(f"{STATE}/rounds/{round_id}/step1_test_send_response.json","w"), ensure_ascii=False, indent=2)
blog.http("POST", url, 200 if "error" not in resp else 400, body, resp, note=f"seq{SEQ}")

# ✅ 必做 3 项自检:
#   resp.verificationSessions 非空
#   resp.summary.title = "测试发送验证"
#   resp.approvalId 存在
# 任一失败 → verdict WRONG_ENDPOINT 或 VALIDATION_ERROR
```

## 🔗 依赖 skills

```
bowjwj-aicrm           — API 地图, 模板/通道/号码包底层操作
bowjwj-auto-campaign   — 单轮完整闭环 (test → 点击监测 → 放量/弃), 本 skill 继承其规范
```

## Verdict 更新自动化

```
每跑完一个 round (verdict() 被调):
  → bowjwj_log.verdict() 里的 hook 已挂:
    db.refresh_combo_coverage_for_round(round_id)
  → combo_coverage 表自动同步
  → Willy 跑 export.py + F5 即可看到 dashboard 组合矩阵新数据
```

## 📊 verdict 前必拉 send-logs (CTR 分母矫正)

**每个 session 做 verdict 前强制步骤**:

```
1. GET /api/send-logs?campaignId=<testCampaignId>
   → 拿 successCount (真送达数)
2. UPDATE sessions SET sent_count = successCount WHERE session_id=?
3. GET /api/shortlinks/<shortlinkId>/visits
   → 滤 isBot=false 取真实点击数 → final_click_count
4. 计算 CTR = final_click_count / sent_count (successCount 口径)
5. 再决定 verdict:
   click >= 3    → passed
   click 1-2     → passed_below_threshold_3
   click == 0    → zero_click → policy.py 冻结评估
```

**绝对禁止**: 用 cleanCount 或 uploadSummaryJson.total 当 CTR 分母。
真实差距:
- #68: cleanCount=200, successCount=135 (差 32.5%)
- 这 32.5% 的 dedup 包含系统二次去重 + 黑名单过滤

```
orchestrator 落盘结构:
  rounds/<round_id>/send_logs.json       (GET /api/send-logs?campaignId=X 原始)
  rounds/<round_id>/visits_<slid>.json   (GET /api/shortlinks/X/visits 原始)
```

## 不做的事 (红线)

- ❌ 不自带 sh/py 脚本 (协调器纯文字)
- ❌ 不自动 export dashboard (让 Willy 主动刷, 他喜欢)
- ❌ 不并发 >20 (TG 点不过来)
- ❌ 不做 "approval 自动批准" (Willy 明确要求手批)
- ❌ 不做 "自动放量" (51+ 场景永远手动批放量)
- ❌ 不改源码
- ❌ 不跨越数据源 (只操作 NN33 ph, 其他 backend 不管)
