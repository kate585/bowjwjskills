---
name: bowjwj-auto-campaign
description: bowjwj AICRM 自动化发信循环协调器。当 Willy 说"开始发信 / 跑自动发信 / 继续发短信 / 停发信"时加载。每 3 分钟一轮, smart + globe 并行, 每轮 2 个 TG 审批由 Willy 手点。详见 bowjwj-aicrm skill 的 API 地图。
---

# bowjwj 自动发信循环 skill

## 何时加载

- Willy 说 "开始发信" / "跑自动发信" / "启动 NN33 发送" / "跑一轮"
- Willy 说 "停发信" / "看一下当前批次进度"
- Willy 问 "今天发了多少" / "有没有点击量"

同时加载 `bowjwj-aicrm` skill 拿基础 API 地图。

---

## ⚠️ 先看这里 — 2026-04-24 血泪教训汇总

**在做任何 POST 前, 把这一节从头读一遍。** 以下每条都由真金白银换来。

### 🔴 核心原则: "同 batch 放量" 正确姿势 (2026-04-24 血泪)

**错误做法 (浪费归因 + 重洗代理线)**:
```
test-send 跑好 → 再发 test-send + 19 新包
→ 19 个全新 batch, 19 个新代理线, 5 个轮换短链
→ 等于又开 19 个独立 L0 实验, 不是爆款放大
→ 注册/FTD 归到各自新代理线, 原爆款数据无延续
```

**正确做法**:

(1) **L0 开局时就多带包**, 系统留 remaining:
```
POST /api/campaign-templates/{tid}/send-direct/test-send
body:
  phonePackIds: [20 个包]   ← 不是 1 个
  
系统行为:
  tested=1 (挑 cleanCount>=100 的 1 个测试)
  remaining=19 (留给放量)
  同 batchId / agent_line / shortlink
```

(2) **点击达标后放量**:
```
POST /api/campaign-templates/{tid}/send-direct   (无 /test-send 后缀!)
body:
  verificationSessionIds: [原 session id]
  (其他参数系统自动从 session 继承)

→ 系统发 remaining 19 个 + 重用原 batchId
→ FTD 归因到同一个代理线
→ 数据可以连续看
```

**本 skill 以后坚持**:
- 任何 "L0 探索" 要 phonePackIds 带 5-20 个 (按预期层级准备)
- 放量用 send-direct + verificationSessionIds, **不重开 test-send**
- 如果 L0 只传了 1 个包, 跟单只能换 round_id 开新实验 (归因断裂, 接受)

### 🔥 0. CTR 分母陷阱 (2026-04-24 second-round 踩)

```
错: CTR = click / phonePack.cleanCount  (用 200)
错: CTR = click / uploadSummaryJson.total (用 200)
对: CTR = click / send_log.successCount  (用 135)

原因: SMPP 真投递前系统二次去重, cleanCount 和真发数差 30%+

每轮 verdict 前必拉一次:
  GET /api/send-logs?campaignId=<campaignId>
  → 用 successCount 回写 session.sent_count
  → 这才是真"送达"基线, click 的分母
```

### 📊 "发送记录"三层数据真相 (别只看一个口径)

```
① 送达层: GET /api/send-logs?campaignId=X
   targetCount / successCount / failedCount / dedupSkippedCount / status / failureReason
   (这一层最权威, 答案就是真发了多少)

② 访客层: GET /api/shortlinks/{shortlinkId}/visits  
   list[] 每次访问: ip / userAgent / visitedAt / isBot
   区分 real click 和 bot (Google 扫链很多, 要滤 isBot=true)

③ 审计层: GET /api/audit-logs?resourceId=X
   actionCode / userId / ip / detail
   谁批的/何时批的/执行结果, 用来回溯操作链
```

### 🔥 1. 端点写错一字, 全量发送 ~1491 条 (2026-04-24 轮 1, $5.59)$7 学费**
   - `/api/campaign-templates/{id}/send-direct` = 全量直发, **不测试**
   - `/api/campaign-templates/{id}/send-direct/test-send` = 测试发信, 走 verification 流程
   - 两个端点差一个子路径, 行为完全不同
   - **自检**: POST 后响应里必须有 `verificationSessions: [...]` 非空数组, 且 approval.summary.title 是"测试发送验证"不是"模板批次待审批发送"
   - **看到 "模板批次待审批发送" title 立即停, 告诉 Willy"走错了"**

2. **🔥 session 不是按"模板×通道"排列, 是按 phone-pack 排列**
   - 之前算 5 模板×7 通道=35 session × 100 条=3500 条/轮 → **全错**
   - 实际: 20 号码包 → 20 session, 每 session 管 1 个包
   - 单轮真实量 ≈ 20 × 100 = 2000 条 (有去重)
   - 单轮真实成本 ≈ 0.21 PHP × 1800 = ~380 PHP ≈ $7 USD

3. **🔥 "剩 19 包"的真实语义是 "一个 passed 组合接管其它 failed 组合的 pack"**
   - **不是** "1 个 session 里剩 19 包待定" (每 session 只有 1 pack, remaining=[])
   - **是** 20 session 里有 N 个 passed, 其余 20-N 个 failed/no_click, failed 的 pack 重分配到 passed 的 (模板, 通道) 组合去发
   - 源码 `buildVerificationRedistributionPlan`: `failed[i].remainingCampaigns` round-robin 塞给 `passed[cursor % passed.length]`
   - **但还没完全实测通**: 重分配用的是 `remainingCampaigns`, 而 session 只有 1 pack 测完 remaining=[], 所以重分配数组其实是 **[]** — 这部分语义还有疑问, **需要用浏览器走一遍前端 + HAR 抓包才能 100% 确认**
   - skill 在这里**不乱猜**, 留待下次实测补齐

4. **⏰ 双重时间窗口陷阱 (Session 10 秒 × Approval 10 分钟)**
   - `pollUntil = session.createdAt + 10 秒` — session 创建瞬间就开始倒计时
   - `expiresAt = approval.createdAt + 10 分钟` — approval 独立倒计时
   - 如果 Willy TG 没在 10 秒内 approve, session 窗口过期, clickCount 再怎么涨都是 testing, 不会 passed
   - 10 分钟 approval 过期后, TG 按钮点下去也是 "已过期"

5. **🚫 窗口外绝不 POST test-send**
   - 就算 plannedAt 算到下个窗口, 也不行
   - 因为 session pollUntil 从 createdAt 起 10 秒, plannedAt 到时早过期
   - **正确**: 先 `in_send_window(now_bj())` 检查, 不在就 sleep_to_next_window 再 POST

6. **🛑 IP 白名单**
   - bowjwj 有全站 IP 白名单, 所有 `/api/*` 返回 `IP_NOT_WHITELISTED`
   - OPS_ADMIN 读不了 `/api/ip-whitelist` (403), 必须 SUPER_ADMIN (Willy 本人前端操作)
   - 开跑前先 `GET /api/me` 自检, 403 直接停
   - 家里 IP 变化快, 长期稳定方案: ECS `47.83.26.52` 加白 + 用 `ssh git` 当跳板

7. **📉 第一批 20 campaign 零点击的启示**
   - 2026-04-24 02:00 BJ 发 1983 条, T+30 分钟全 0 点击/0 注册/0 FTD
   - 系统分析 "点击率偏低, 优化文案/短链/时段"
   - **结论不是流程错, 是号码包/文案/短链本身效果差**
   - 跑 test-send 的真正价值: 挡掉这种零点击批次, 省掉放量的大钱

8. **🕵️ 当你有源码时, 不要靠 bundle.js 反推 API 语义**
   - 这次从 bundle 反推看到 "send-direct" API, 就猜是"一键发送", 其实前端那个按钮叫 "测试发送" 的走另一个子路径
   - **正确做法**: `rg onClick web-app/src/pages/TemplateDirectSendModal.tsx` 找真实组件, 看 handler 调哪个 URL
   - 这个教训普适于任何"前端 + 后端都有源码"场景

---

## 业务目标 (Willy 原话)

```
循环跑"创建 → 测试发 1 包 → 看点击 → 过了放量"
按 smart 套和 globe 套分别独立
每 3 分钟一轮
号码包耗尽 → 10 分钟后重试
在发送窗口 (00:00-02:00 ∪ 12:00-13:30 ∪ 17:30-21:00 BJ) 内跑
```

## 业务参数 (Willy 拍板 2026-04-24)

```
站点          : NN33 (ph 地区)
  backendInstanceId = c7ee7c4c-ce0a-49c9-880a-9315d07c07b6

模板          : 5 个 (API 返回序前 5 个 status=active, NN33 backend)
  当前观察顺序: 大官人通道加白模版 3/2/1 → NN33 汤丁 → NN33 到账领取 P333

号码包/轮     : 20 包 × 100 条 = 2000 号码
  筛选: source 含关键词 (忽略大小写)
    smart 套 → source 匹配 /smart/i
    globe 套 → source 匹配 /globe/i
    跳过    → source 匹配 /yo家黑名单/
    条件    → reuseLocked=false && assignmentCampaignId == null

通道 (固定白名单, 按 adapter.name 精确匹配取 id):
  smart 套 (7 条 smart&TNT)
  globe 套 (9 条 Globe&Dito)
  (具体名字见本 skill 附带的 references/channel-whitelist.md)

短链映射      : "pack"  (一个号码包共用一条短链)
短链模式      : "domain"
域名          : 30 条 (createdAt desc, NN33 backend 的 shortlink-options)
标题前缀      : YYYYMMDD-HHMM (北京时间当前时刻)
计划时间      : 北京时间 + 3 分钟 (ISO)
发送窗口      : 00:00-02:00 ∪ 12:00-13:30 ∪ 17:30-21:00 (北京)
阈值          : session.clickCount >= 3 (含 3 放量; <3 放弃)
并行          : smart 和 globe 独立跑自己的轮
循环节奏      : 每 3 分钟开一轮新窗口
耗尽处理      : 号码包耗尽 → sleep 10 分钟 → 再检查 → 有续, 无再 sleep
终止          : Willy 手动停 / JWT 过期 / API 连续 3 次 5xx
```

## 审批成本

```
每轮 2 次 TG approve:
  1) CAMPAIGN_SEND_VERIFICATION_TEST_APPROVAL   (启动测试)
  2) CAMPAIGN_SEND_BATCH_APPROVAL              (放量 / 带 verificationSessionIds)

smart + globe 并行: 每 3 分钟 4 次 TG approve
窗口内 7h/天 × 20 轮/h × 4 = 560 次/天

Willy 已绑 TG (telegramId=6694261813), approve 是他的事
skill 不考虑"自动 approve" (源码硬性要求 TG, 已经确认)
```

---

## API 调用序列 (一轮, smart 套; globe 套同构)

### 前置只读 (不耗审批, 5 秒内完成)

```
A. 模板
   GET /api/campaign-templates?backendInstanceId={NN33}&status=active&campaignType=activity&pageSize=10
   → 取前 5 条 id

B. 号码包
   GET /api/phone-packs/categories?backendInstanceId={NN33}&pageSize=200
   → 本地 filter: source match /smart/i && !/yo家黑名单/
   每个命中 category:
     GET /api/phone-packs/categories/{encKey}/packs?backendInstanceId={NN33}&page=1&pageSize=50
     → filter reuseLocked=false && assignmentCampaignId==null
   → 按 latestCreatedAt desc, 取前 20 个 phone-pack id

C. 通道
   GET /api/adapters/instances?type=sms
   → 按 name 精确匹配白名单 (见 references/channel-whitelist.md), 取 id

D. 域名
   GET /api/domains/shortlink-options?backendInstanceId={NN33}
   → 按 createdAt desc, 取前 30 个 id
```

### 写入 (产生审批)

```
E. 启动测试 (审批 #1)  ⚠️ 端点必须是 /send-direct/test-send
   POST /api/campaign-templates/{firstTemplateId}/send-direct/test-send
   body = {
     templateIds:          [5 个 id],
     smsInstanceIds:       [7 或 9 个 id],
     phonePackIds:         [20 个 id],
     shortlinkMappingMode: "pack",
     shortlinkMode:        "domain",
     customShortlinkDomainConfigIds: [30 个 id],
     titlePrefix:          "YYYYMMDD-HHMM",
     plannedAt:            "<UTC ISO>"
   }
   返回: 202 {
     kind: "approval",
     approvalId: "...",
     verificationSessions: [{id, status:"testing", ...}, ...20 个],  ⚠️ 必须非空
     campaignIds: [...], campaignBatchIds: [...],
     summary: {title: "测试发送验证", ...}   ⚠️ 不是"模板批次待审批发送"
   }

   ⚠️ 检查清单 (POST 后立即执行):
     - resp.verificationSessions 是数组且长度 > 0
     - resp.summary.title 不含 "模板批次待审批发送"
     不满足任一条 → 立即停, 告诉 Willy 走错路径

   → 告知 Willy approvalId, 等 TG approve  (10 秒内, 不然 session 窗口过期)

F. 轮询 (10-15 秒, 每秒一次)
   sessionIds 直接从 E 响应的 verificationSessions[].id 取 (不要查 approval.result)
   GET /api/send-verification-sessions?ids=<逗号分隔>
   评估每个 session:
     · status='passed'  && clickCount >= 3 → 加入"放量候选"列表
     · status='passed'  && clickCount <  3 → 丢弃 (不达阈值)
     · status='no_click' → 丢弃
     · status='testing' → 继续轮询 (直到 pollUntil 过期或超 15 秒)

G. 放量 (审批 #2)  — **就用 /send-direct 带 verificationSessionIds, 不是 /confirm**
   若放量候选 > 0:
     POST /api/campaign-templates/{sameTemplateId}/send-direct
     body = {
       ...E 的 body 所有字段...,
       verificationSessionIds: [放量候选的 sessionId, ...]
     }
     返回 202 {kind:"approval", approvalId, ...}
     → 告知 Willy, 等 TG approve
     → 系统走 createVerifiedSendApprovalFromSessions, 重分配 failed session 的 pack 给 passed 组合发
   若放量候选 = 0:
     本轮全部丢弃, 不 POST, 关窗等下一轮
```

**关于 `/api/send-verification-sessions/confirm`**: 这是另一套接口 (bulk confirm + 强制把 testing 标 failed), 前端代码实际没调用这个做"放量"。**不要用**。放量就用 `/send-direct` + `verificationSessionIds`。

---

## 凭据

```bash
# ⚠️ Willy 偏好: 不要用 op read, 每次弹 TouchID 太烦 (2026-04-24 明确要求)
# JWT 落盘 ~/.hermes/state/bowjwj/.jwt (600 权限, .gitignore 已加)
JWT=$(cat ~/.hermes/state/bowjwj/.jwt)
BASE=https://bowjwj.cc
NN33_BID=c7ee7c4c-ce0a-49c9-880a-9315d07c07b6
```

Python 脚本一律用 `open(os.path.expanduser("~/.hermes/state/bowjwj/.jwt")).read().strip()`, **不要**`subprocess.run(["op","read",...])`. 所有脚本 (sync.py/export.py/pool 生成) 都遵循此规则.

JWT 7 天过期, 过期时整个循环停下提醒 Willy 续。续时一次性从 1P 重读并覆盖 `.jwt` 文件. 续法见 bowjwj-aicrm skill。

## 状态文件与日志

```
~/.hermes/state/bowjwj/
├── bowjwj_log.py              # 日志 helper (import 或 CLI)
├── events.jsonl               # 主事件流 (append-only, 所有 HTTP/决策/审批状态)
├── rounds/
│   └── {YYYYMMDD-HHMM}-{smart|globe}-{FLOW}/
│       ├── request.json        # E/G body
│       ├── response.json       # 原响应
│       ├── approval.json       # TG 状态快照
│       ├── polls/              # 每秒 poll 快照
│       │   └── {HHMMSS}.json
│       └── verdict.json        # 本轮结果
└── session-ids.txt             # 当前 round 的 sessionIds (多行或 CSV)
```

### 日志 API (直接可用)

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.hermes/state/bowjwj"))
import bowjwj_log as L

L.round_init("20260424-1200-smart-TESTSEND")
L.http("POST", "/api/campaign-templates/.../send-direct/test-send", 202, body={...}, response={...})
L.round_write(round_id, "request.json", {...})
L.round_append_poll(round_id, sessions_snapshot)   # 每次轮询
L.verdict(round_id, status="passed_3_of_20", reason="3 sessions >=3 clicks", detail={...})
L.event(kind="decision", reason="...")
```

### CLI 查

```bash
python3 ~/.hermes/state/bowjwj/bowjwj_log.py tail 30    # 最近 30 条事件
python3 ~/.hermes/state/bowjwj/bowjwj_log.py rounds     # 列所有 round + verdict
```

---

## 执行器 (伪代码)

```python
def run_round(suite: "smart" | "globe"):
    # 开跑前自检
    if not can_reach_api():              # GET /api/me 是否 200
        return "IP_BLOCKED"
    if not in_send_window(now_bj()):
        return "OUT_OF_WINDOW"
    if jwt_expires_in() < 12 * 3600:
        return "JWT_EXPIRING"

    # 前置
    templates   = get_first_5_active(suite)      # A
    phone_packs = pick_phone_packs(suite, 20)    # B
    if len(phone_packs) < 20:
        return "PAUSE_EMPTY"                      # 触发 10 分钟等待
    sms_ids     = resolve_channel_ids(suite)      # C
    domain_ids  = get_latest_30_domains()         # D

    # 组装 body
    body_e = build_body(templates, sms_ids, phone_packs, domain_ids,
                        plannedAt=now_bj() + 3min,
                        titlePrefix=now_bj().strftime("%Y%m%d-%H%M"))

    round_id = f"{titlePrefix}-{suite}-TESTSEND"
    L.round_init(round_id)
    L.round_write(round_id, "request.json", body_e)

    # E: 测试发送
    resp_e = POST /send-direct/test-send  body=body_e
    L.http("POST", "/send-direct/test-send", 202, body_e, resp_e)
    L.round_write(round_id, "response.json", resp_e)

    # 关键自检 - 走对路径了吗
    sessions = resp_e.get("verificationSessions", [])
    if not sessions or "模板批次待审批发送" in resp_e.get("summary",{}).get("title",""):
        L.verdict(round_id, "WRONG_ENDPOINT", "响应不含 verificationSessions 或 title 错")
        return "WRONG_ENDPOINT"

    notify_willy(f"🔔 TG approve #1, approvalId={resp_e['approvalId']} (10s 内!)")
    wait_approval_executed(resp_e["approvalId"], timeout=60s)  # 超时回 TIMEOUT

    # F: 轮询
    session_ids = [s["id"] for s in sessions]
    candidates = []
    for i in range(15):
        sessions_now = GET /send-verification-sessions?ids=...
        L.round_append_poll(round_id, sessions_now)
        for s in sessions_now:
            if s["status"] == "passed" and s["clickCount"] >= 3 and s["id"] not in candidates:
                candidates.append(s["id"])
        if all(s["status"] in ("passed","no_click") for s in sessions_now):
            break
        sleep(1)

    if not candidates:
        L.verdict(round_id, "NO_PASSED", "所有 session < 3 clicks 或 no_click")
        return "NO_CLICK"

    # G: 放量
    body_g = {**body_e, "verificationSessionIds": candidates}
    resp_g = POST /send-direct  body=body_g
    L.http("POST", "/send-direct", 202, body_g, resp_g)
    notify_willy(f"🔔 TG approve #2, approvalId={resp_g['approvalId']}")
    wait_approval_executed(resp_g["approvalId"], timeout=60s)

    L.verdict(round_id, "OK", f"{len(candidates)}/{len(sessions)} passed & released",
              detail={"pass_sessions": candidates})
    return "OK"

def main_loop():
    async/并行:
        while True:
            r = run_round("smart")
            handle_round_result(r)
        while True:
            r = run_round("globe")
            handle_round_result(r)
```

---

## 禁区

- ❌ 不自动续 JWT — 过期就停, 等 Willy 贴新
- ❌ 不自动点 TG approve — 源码硬性要求, 做不了
- ❌ 不自动重启 — 挂了就挂, cron 不做 restart
- ❌ 不跑首轮自动 — 第一轮必须 Willy 在旁边看 body 点头
- ❌ 不修改模板/通道/域名 — 只读 + POST 走链路, 不 PUT/DELETE
- ❌ 不缓存 phone-pack 列表超过 1 轮
- ❌ **不 POST `/send-direct` 不带 verificationSessionIds** (= 全量直发, 跳过测试, 会扣大钱)
- ✅ 可并行 smart + globe
- ✅ 窗口内按 3 分钟节奏开新轮

## 首次实跑流程 (必须 Willy 盯着, 不 auto-loop)

```
1. Willy 说 "跑一轮 smart dry-run"
2. Hermes 执行 A/B/C/D 前置, 打印 E body 完整 JSON
3. Willy 扫一眼 → 回 "真跑"
4. Hermes POST E → 检查 verificationSessions 非空 → 告知 approvalId
5. Willy TG 10 秒内 approve
6. Hermes 轮询 sessions 15 秒 → 打印每 session 的 clickCount
7. 有候选 → POST G → 告知 approvalId → Willy TG approve
8. Hermes L.verdict 记录本轮
9. Willy 决定是否开自动循环
```

---

## 未完全验证的细节 (后续实测补齐)

1. **放量时 /send-direct + verificationSessionIds 到底发哪些 pack?**
   - 源码 `buildVerificationRedistributionPlan` 用 `failed.remainingCampaigns` round-robin 给 passed combo
   - 但 session `remainingCampaignIds = []` (1 pack 测完就空), 那重分配的 reassignedPhonePacks 也应该 = []
   - 矛盾: `sendPlan.sendCampaignIds = []` 那岂不是没东西发?
   - **解法**: 下次用浏览器 DevTools 录一次完整 HAR (test-send → 点一键发送), 比对真实请求/响应

2. **Willy 的"3 分钟一轮"节奏是否和 session 10 秒窗口冲突?**
   - POST 后 session 立即倒计时 10 秒, Willy 必须 10 秒内 TG approve
   - Willy 一天要点几百次 TG 10 秒极限操作, 现实吗?
   - **解法**: 先跑 3-5 轮真实实测, 看 Willy 平均 approve 时间, 再决定要不要做"提前创建 session+手动延后 approve"或请求 Willy 改业务

3. **同时并行 smart + globe 两套时 TG 消息会不会混?**
   - TG 会同时收到 2 条 approval 消息, Willy 可能点错
   - **解法**: 先跑单套验证, 并行改 TG 消息 title 区分 (附带 suite 名) 后再开

---

## 更新历史

- 2026-04-24 v1: 首次创建, 假定 35 session × 100 条 (错)
- 2026-04-24 v2: 实跑踩坑, 发现 `/send-direct` vs `/test-send` 差异, 重写端点说明
- 2026-04-24 v3: 实跑再次踩坑, 发现 session 按 pack 排列不是 模板×通道; session/approval 双窗口陷阱; IP 白名单
- 2026-04-24 v4: **本次重写**, 合并所有踩坑到顶部教训段, 放量用 `/send-direct`+sessionIds 不用 `/confirm`, 明示"重分配语义未完全验证"不再瞎猜
- 2026-04-24 v5: session 数公式修正 (实测 `session=len(pack)`, 不是 `tpl×sms`), 加干验证方法, 加 Willy"最终否决权"纪律
- 2026-04-24 v6: 加 561 组合池 (33 tpl × 17 ch) + 运营商匹配规则 + dashboard 3 个踩坑 (script 位置/函数重名/IIFE 初始化) + JWT 本地化偏好


## ✅ 2026-04-24 实测验证的 8 条真相 (session 数公式已修正, 见干验证 #2)

1. **⚠️ session 数真正公式 (2026-04-24 干验证推翻之前所有推测)**: 
   - **`session 数 = len(phonePackIds)`** 就这么简单. 1 pack 1 session, 每 session 一个 (tpl, sms, pack) 三元组
   - tpl 和 sms 是被 round-robin **分配**给 session 的, 不是笛卡尔积
   - 实测矩阵:
     ```
     1×1×1  → 1 session
     1×1×2  → 2 session (轮 3 实际给的是 2 pack, 但源码内部把首包合成 1 测, remaining=1)
     1×1×20 → 20 session? 不, 实测 1 session 含 allPacks=20 ← 这里结果和干验证 #1/#2 冲突, 见下
     1×5×5  → 5 session (干验证 #1)
     5×5×5  → 5 session (干验证 #2, 不是 25!)
     5×7×20 → 20 session (轮 1 观察)
     ```
   - **关键**: 想覆盖 N 组合, 至少要 N pack. 5 tpl × 5 sms = 25 组合只能采样 5 组合 (如果只给 5 pack).
   - 矛盾点: 轮 4 的 1×1×20 给 20 pack, 但 session=1 且 allPacks=20 — 这和 "session=pack数" 冲突, 说明**当 tpl×sms=1 时, 所有 pack 并入 1 session**
   - **最可能的真实规则**: `session 数 = min(pack 数, tpl × sms 唯一组合数)`, pack 超量时超出的归到已有 session 的 remaining
   - 这个规则下次还需再验证, 目前先按"想覆盖 N 组合就给 N pack"设计
2. **pack 分配**: 若 pack 数 > 组合数, 多余 pack 被塞到 session.remainingPhonePackIds (轮 4 验证)
3. **测试切分**: `first.phonePackCleanCount>=100 ? [first] : [first,second]` — 单 session 若拿到多 pack, 首包测, 余下 remaining
4. **dedup 真实**: 号码包 cleanCount=100 实际发出 ~75 条 (去 25%), 成本要乘 0.75
5. **approval TTL**: 10 分钟, 过则 expired 无法批
6. **IP 白名单**: OPS_ADMIN 读 `/api/ip-whitelist` 403, 必须 SUPER_ADMIN 加白
7. **放量先决**: 至少 1 session status=passed, 否则 `/send-direct` 带 verificationSessionIds 抛 `verificationContinueRequiresPassedCombo`
8. **业务 vs 系统阈值**: 系统 `clickCount>0 → passed`, Willy 业务要 `>=3`, 由 Hermes 侧二次过滤

## 🎯 5 个配置优化点 (为实现"先测 1 包 + 剩 19 包放量")

### A. **配置必须是 1×1×N**
```
错: 5 模板 × 7 通道 × 20 包 → 20 session 每个 1 包 (remaining=[] 无法放量)
对: 1 模板 × 1 通道 × 20 包 → 1 session 含 20 包 (测 1 剩 19)
```

### B. **要覆盖 5 模板 × 7 通道 = 至少 35 个号码包/轮, 或分多轮**
```
方案 A (单大轮探索): 35 pack × 5 tpl × 7 sms → 35 session 覆盖 35 组合
  成本: 35 × 75 × 0.21 = 551 PHP ≈ $10 (仅测试)
  TG: 1 次 (测试) + 每个胜出组合再开独立 1×1×N 放量 (每个 2 次 TG)
  胜出 3 个: $10 + 3 × $5.6 = $27, TG 7 次

方案 B (串行小轮): 35 轮独立 1×1×20, round-robin
  每轮: 20 pack, session=1, 测 1 pack 成本 $0.27, 放量 $5.3
  一天窗口 7h 能跑 ~50 轮
  优势: 单轮 TG 仅 2 次, 总花费跟方案 A 相似但可增量
  劣势: 探索慢, 35 组合要 35 轮 (7h 内跑完可以)
```

### C. **成本精算公式**
```
每轮测试成本 = 1 × 75 × 0.21 PHP ≈ $0.27
每轮放量成本 = 19 × 75 × 0.21 PHP ≈ $5.3
最坏全放 (全 passed) = $5.6/轮
最好全失败 = $0.27/轮
```

### D. **轮询监控只看 3 字段**
`session.status` / `session.clickCount` / `session.pollUntil`

### E. **前 15 秒密集 (1s 1 次)** → pollUntil 到就退

## ❄️ 冻结系统 — D 策略 (双重确认, Willy 2026-04-24 拍板)

### 为什么不做系统级禁用 adapter/template

系统有 `PATCH /api/adapters/instances/:id` 改 enabled, 但那是**全局影响 + 需 TG 审批**, 不适合频繁轮换。

**方案: 本地 policy 文件**, 不改系统状态, 只影响 Hermes 侧选组合:

```
~/.hermes/state/bowjwj/policy.json
~/.hermes/state/bowjwj/policy.py      ← CLI 工具
```

### D 策略: 单轮 0 点击不冻, 交叉 0 点击才冻

```
本轮 (tpl_X, sms_Y) clickCount==0 →
  tpl_X.suspect_with += [sms_Y]
  sms_Y.suspect_with += [tpl_X]
  
  if len(tpl_X.suspect_with) >= 2 不同 sms → 冻 tpl_X (模板坏)
  if len(sms_Y.suspect_with) >= 2 不同 tpl → 冻 sms_Y (通道坏)

本轮 click > 0 → 互相从 suspect_with 里删除 (证据推翻)
```

### 冻结时长

- 通道: 冻 20 轮, 之后自动解冻
- 模板: 冻 10 轮, 之后自动解冻
- 解冻后 3 轮内仍 0 点击 → 永久冻 (需 `python3 policy.py unfreeze`)

### Active combos 算法

每轮选组合时:
```python
active_combos = [(tpl,sms) for tpl in all_tpls if not frozen for sms in all_smses if not frozen]
# 然后 round-robin 挑一个
```

### CLI

```bash
python3 ~/.hermes/state/bowjwj/policy.py show        # 当前状态摘要
python3 ~/.hermes/state/bowjwj/policy.py full        # 完整 JSON
python3 ~/.hermes/state/bowjwj/policy.py unfreeze channels <id 前缀>
python3 ~/.hermes/state/bowjwj/policy.py unfreeze templates <id 前缀>
python3 ~/.hermes/state/bowjwj/policy.py reset       # 清空
```

## 🔍 轮询机制 — 5 分钟慢速轮询 (P1=A, Willy 2026-04-24 拍板)

### 系统 10 秒窗口是前端显示用, 不影响 clickCount 累加

**关键反直觉事实 (源码验证)**:

```ts
// src/core/send-verification-service.ts: countVerificationClicks
// 每次 refresh 都是从 DB 重算:
prisma.shortLinkVisit.count({ where: { shortLinkId: in session.shortlinks } })
```

所以:
- `session.pollUntil` 过期后, status 变 `no_click` — **只是标签**
- **shortLinkVisit 表仍在累加新访问**
- **继续调 `/api/send-verification-sessions?ids=...` 仍能拿到更新后的 clickCount**
- 不要被 `status=no_click` 骗到, **看 clickCount 数字**

### 推荐轮询节奏

```
阶段 A: 0-30 秒     每 2 秒查 1 次 (抓立即点击, 15 次)
阶段 B: 30s-5m30s  每 30 秒查 1 次 (抓滞后点击, 10 次)
总耗时: ~5m30s, 总请求数 ~25 次

终止条件:
  clickCount >= 3 → 立即退出, 进入放量
  阶段 B 结束     → 按最终 clickCount 决策:
    <3 → 按 D 策略记录 + 写 verdict
    >=3 但 session status=no_click → 仍可放量 (status 无效, 看数字)
```

### 为什么 5m30s

- 菲律宾用户实际看短信到点击有 1-10 分钟延迟
- 10 秒根本抓不到
- 5m30s 是经验值, 以后按 timeline 分析数据再调

## 🎬 完整一轮真实时间线 (实测 2026-04-24)

```
T+0s    Hermes POST test-send → 202 + approvalId + 1 session
T+10s   Willy 收到 TG 消息 (自动推送)
T+30s   Willy 点 approve (手动)
T+45s   approval executed, 测试短信入 SMPP 队列
T+90s   第 1 包真发到手机 (SMPP 延迟 ~45s)
T+3m    plannedAt 才到 (如果 plannedAt = 现在+3 分钟的话)
         ↑ 注意: approval approve 后不会立即发, 还要等 plannedAt
         建议 plannedAt 设为"现在 + 30 秒", 加速测试

轮询期间 (5m30s):
  T+2,4,6,...30s   密集轮询, 抓早期点击
  T+60,90,...330s  缓速, 抓滞后点击

T+5m30s 决策:
  clickCount>=3 → POST send-direct (带 sessionIds) → 新 approval
                 Willy 再批 → 放量 19 包 (SMPP 队列)
  clickCount<3  → D 策略记录 + 收工本轮

T+10-15m 一轮完整结束
```

## 📊 分析工具 `analyze.py`

```bash
python3 ~/.hermes/state/bowjwj/analyze.py summary     # 每轮概览 + 合计
python3 ~/.hermes/state/bowjwj/analyze.py by-channel  # 通道 CTR
python3 ~/.hermes/state/bowjwj/analyze.py by-template # 模板 CTR
python3 ~/.hermes/state/bowjwj/analyze.py cost        # 成本分布
python3 ~/.hermes/state/bowjwj/analyze.py timeline    # 按小时 CTR
python3 ~/.hermes/state/bowjwj/analyze.py events 30   # events 尾 30 条
python3 ~/.hermes/state/bowjwj/analyze.py watch       # 实时监控
```

跨轮积累足够样本后, 这个工具产出:
- 哪个通道 CTR 最高 → 加量
- 哪个模板文案最有效 → 优先
- 几点发效果最好 → 调 plannedAt


## 📝 踩坑记录 (2026-04-24 晚)

1. **走错 API**: `/send-direct` 无 sessionIds = 裸发, 损失 $7 + 1983 条发出去零点击
2. **配置漏洞**: 5×7×20 config 在 test-send 模式下 pack 被稀释到 1 session 1 pack, 违背"剩 N 包"业务意图
3. **审批超时**: 20:24 发的 test-send, 10 分钟没批, 废
4. **IP 白名单**: 初次遇到 IP_NOT_WHITELISTED, Willy 手动加白解除
5. **点击率现实**: 1983 条 30 分钟 0 点击 — 这批号码/文案/短链组合本身效果差 (即系统分析所言 "点击率偏低")
6. **"查日志慢"问题 — 是我的实现错, 不是日志系统慢**:
   - 本地 `analyze.py` 读 `rounds/` 文件 **0.03 秒**
   - 但我之前 Willy 说"查日志"时, 下意识打了 8 个在线 curl (每个 ~2s, 合计 16s+), 还串了 op read JWT 和 3 次 terminal() 跑子脚本, 300s 超时
   - Willy 直接质疑 "查日志为什么那么久" — 这是信号: 我混淆了"在线拉最新"和"查本地历史"
   - **纪律**: "查日志" = 立即 `python3 ~/.hermes/state/bowjwj/analyze.py <cmd>`, 0.03s 出结果. 要在线拉新状态, 明说"我去拉一下线上", 且一次拉完落盘, 不要散着拉
7. **status='passed' 是 sticky 的**:
   - 一旦 session.clickCount 曾 >0 过, status 就锁定 'passed', 之后 pollUntil 过期也不会变 'no_click'
   - 但 clickCount 本身**会继续涨**, 因为 `countVerificationClicks` 每次都从 DB 重查 shortLinkVisit
   - 实证: 轮 4 (2026-04-24 03:07) pollUntil 03:07:38 过期, 03:15:01 时 clickCount 已涨到 3 (涨了 7m23s)
   - **结论**: 5m30s 慢速轮询是对的, 关注 clickCount 数字 不看 status 标签
8. **Willy 有最终否决权, 过了阈值不等于必须放量**:
   - 轮 4 clickCount=3 触达 C1 阈值, 我已经 POST 出放量 approval, 但 Willy TG 拒绝了
   - **不要在 skill 里把"过阈值→自动放量"当硬规则**, Willy 看后台可能发现其它异常 (号码包重复/短信质量差/同一 IP 刷点击等)
   - **纪律**: skill 执行流到"准备放量"阶段, 永远通过创建 approval 等 Willy TG 操作, 不做"本地决定自动跳过 TG"的捷径. Willy 拒 → 按 no_click 处理, verdict 写 `rejected_at_release_stage`
9. **plannedAt 建议设为 "现在+30s" 不是 "现在+3min"**:
   - approval 走完只要几秒, 但 plannedAt 不到就不发 — 相当于凭空等几分钟, 让 session 10 秒窗口白烧
   - **建议**: plannedAt = 现在 + 30 秒 (给 approval 消息 + TG approve 留缓冲)
   - Willy 原话"每 3 分钟一轮"指**轮与轮之间**节奏, 不是 plannedAt



## 📏 日志 vs 在线查询 — 严格分离 (2026-04-24)

**Willy 实测踩坑**: 把"在线查 session + 本地日志读"绑在一个脚本里, 导致"查日志" 3 分钟超时。

**纪律**:

| 动作 | 命令 | 耗时 | 碰网络? |
|---|---|---|---|
| 查日志 / 看数据 | `python3 ~/.hermes/state/bowjwj/analyze.py <cmd>` | <50ms | ❌ 不 |
| 在线刷新 round 状态 | 显式命令或单独 curl | 5-30s | ✅ 是 |
| 轮询 session | 后台 background process | 持续 | ✅ 是 |

**Willy 说"查日志"/"看数据"时绝对只走本地**, 不在线。在线要显式触发词: "刷新"/"同步"/"拉最新"/"再查一下".

写代码时的惯性检查: 脚本里如果出现 `subprocess.run(["curl"...])` 或 `requests.get`, 就不是"查日志"而是"在线查", 要显式说明.


## 🗄️ 数据库基础设施 (2026-04-24 新增 — Willy 要求跨会话记忆)

### 为什么上 SQLite 不上 Postgres

Willy 原话: "因为我们前期要无数轮去测试出来最合适的方式, 然而你是有记忆短板的"

意图是**防 Hermes 跨会话失忆**, 不是大数据查询。SQLite 完全够:
- 本地单文件 (~/.hermes/state/bowjwj/stats.db), 备份只需 cp
- 零运维, 不占 Willy 的 bowjwj 生产 pg
- 查询毫秒级 (比 JSONL 全扫快)
- 未来真要上 pg, `pg_restore` 一条命令迁

### Schema (6 张表)

```
rounds         (round_id, started_at, mode, tpl/sms/pack_count, sent_count, click_count, cost_php, verdict, bj_hour)
sessions       (session_id, round_id, tpl_id/name, sms_id/name, pack_ids_json, all/tested/remaining_count, final_status, final_click_count, sent_count, dedup_count)
polls          (poll_id, session_id, ts, elapsed_sec, status, click_count) — 每次轮询快照, 画曲线用
approvals      (approval_id, round_id, action_code, status, created_at, approved_at, rejected_at, expires_at)
combo_stats    (tpl_id, sms_id, tpl_name, sms_name, rounds_tested, total_sent, total_click, last_round_id, last_tested_at, ctr virtual)
policy_events  (id, ts, round_id, entity_kind, entity_id, action, reason, detail_json)
shortlink_visits (visit_id, shortlink_id, session_id, visited_at, ip, user_agent, is_bot)
```

### 用法 — db.py helper

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/.hermes/state/bowjwj"))
import db

# 写入 (round 开始/结束)
db.log_round_start(round_id, mode, tpl_count, sms_count, pack_count, session_count)
db.update_round_end(round_id, sent=..., click=..., cost_php=..., verdict=..., verdict_reason=...)

# 写入 (session)
db.log_session(session_id, round_id, session_data)   # session_data = bowjwj 返回的完整 dict
db.update_session_send(session_id, sent_count, dedup_count)
db.log_poll(session_id, status, click_count, elapsed_sec)

# 写入 (审批)
db.log_approval(approval_id, round_id, action_code, status, created_at=..., ...)

# 写入 (冻结/政策变更)
db.log_policy_event(round_id, "channel"|"template", entity_id, action, reason, detail=None)

# 写入 (点击流水)
db.log_shortlink_visits(session_id, visits_list)  # visits_list = /api/shortlinks/:id/visits 返回的 list

# 写入 (累加组合统计)
db.upsert_combo_stats(tpl_id, tpl_name, sms_id, sms_name, round_id, sent, click)

# 查询
db.top_combos(limit=10)        # CTR 排名
db.recent_rounds(limit=20)
db.session_trail(session_id)   # 单 session 点击曲线
db.combo_confidence(tpl_id, sms_id)  # 样本量 low/medium/high
```

### analyze.py v2 命令 (纯本地, <50ms)

```bash
python3 ~/.hermes/state/bowjwj/analyze.py summary      # 最近 20 轮
python3 ~/.hermes/state/bowjwj/analyze.py combos       # 组合 CTR 排名 (样本>=10)
python3 ~/.hermes/state/bowjwj/analyze.py timeline     # 按 BJ 小时
python3 ~/.hermes/state/bowjwj/analyze.py cost         # 按 verdict 分成本
python3 ~/.hermes/state/bowjwj/analyze.py frozen       # 当前 policy 冻结名单
python3 ~/.hermes/state/bowjwj/analyze.py session <id> # 单 session 详情+ polls trail
python3 ~/.hermes/state/bowjwj/analyze.py visits <id>  # 人类 vs bot 流水
python3 ~/.hermes/state/bowjwj/analyze.py events 30
```

### sync.py (显式在线同步)

```bash
python3 ~/.hermes/state/bowjwj/sync.py <round_id>     # 拉某轮最新
python3 ~/.hermes/state/bowjwj/sync.py                # 所有未结束 round
```

**只有在明确"刷新/同步"意图时才调 sync.py**, 查日志走 analyze.py.

### 双写机制

- `bowjwj_log.py` 已加 hook: `L.verdict()` 时自动 double-write 到 SQLite
- 新的 POST/poll 逻辑应同时调 `L.round_write(...)` (JSONL) + `db.log_xxx(...)` (SQLite)
- JSONL 是法医证据 (永不改), SQLite 是结构化镜像 (方便查)

## 🔍 shortlink visits API — 精细点击分析

```
GET /api/shortlinks/{shortlinkId}/visits?pageSize=200
→ {list: [{id, shortLinkId, visitedAt, ip, userAgent, referrer, isBot, createdAt}], total, page, pageSize}
```

**字段解读**:
- `isBot=true`: Google/bot prefetch (UA 含 "Googlebot/..." 之类), 不算 session.clickCount
- `isBot=false`: 真人点击, 算 session.clickCount
- `ip`: 真实用户 IP (可做地理分析), bot 常是 Google CDN IP (66.102.x.x, 64.233.x.x)
- `userAgent`: 区分 Android/iOS/Web 设备

**使用场景**:
1. session.clickCount=0 但怀疑有点击 → 查 visits 看是不是全 bot
2. 同一 IP 反复点 → 可能是 Willy 自己测, 或作弊
3. 按 UA 统计 Android/iOS 分布

**实测**: 轮 4 shortlink 总 visits=6, isBot=3 人类=3, session.clickCount 也=3, 说明系统已自动去 bot.


## 🖼️ Dashboard — 静态 HTML + Chart.js (2026-04-24)

### 为什么选静态方案不上 Flask/FastAPI

- 一人场景, 不需要实时推送, 手动刷新够用
- Python http.server 零依赖, ~5 行配好
- data.json 由 `export.py` 按需生成, 跟 stats.db 解耦
- 想要实时? 挂个 cron 每 10 分钟跑 export.py

### 文件布局

```
~/.hermes/state/bowjwj/dashboard/
├── index.html      6 卡片 + 最近轮次表格 + Chart.js 折线图
├── style.css       dark theme
├── app.js          fetch('data.json') → 渲染
└── data.json       由 export.py 生成的数据快照
```

### 启动 (必须走 http://, 不能 file://)

**坑 1**: `file:///.../index.html` 打开, `fetch('data.json')` 会 CORS 失败报 "Failed to fetch". 必须 http 协议。

```bash
cd ~/.hermes/state/bowjwj/dashboard
python3 -m http.server 8080 --bind 127.0.0.1
# Hermes 用 terminal(background=true, watch_patterns=["Serving"]) 起
open http://127.0.0.1:8080/
```

**坑 2**: `fetch('../data.json')` 路径错误 — data.json 跟 index.html 同目录时用 `fetch('data.json')`, 不要加 `../`。

### 更新数据流

```
跑发信 → events.jsonl + stats.db (双写)
         ↓
       export.py 读 stats.db → 生成 data.json
         ↓
       浏览器按 F5 刷新 → 加载新 data.json
```

### 一键刷新 (未实现, 可加)

```bash
#!/bin/bash
# ~/.hermes/state/bowjwj/refresh.sh
python3 ~/.hermes/state/bowjwj/sync.py      # 在线拉最新进 DB
python3 ~/.hermes/state/bowjwj/export.py    # 导 data.json
# 浏览器不能主动刷新, Willy 自己按 F5 (或加 auto-reload)
```

### 默认展示内容 (index.html 6 卡片)

1. 总轮次 / 总发送条数 / 总点击 / 全局 CTR
2. 总成本 (PHP + USD 换算)
3. 冻结组合数 (通道+模板)
4. 最近 5 轮表格
5. 组合 CTR 排名 (top 10, 带置信度低/中/高)
6. Chart.js 按 BJ 小时 CTR 折线图

### 未来可加 (不现做)

- live round 实时进度 (当前轮 session 状态)
- 按组合的点击曲线 (polls 表已有数据)
- 部署到 ECS 47.83.26.52 (Willy 手机外网可看)

---

## 🗺️ 组合矩阵 — 561 组合池 (2026-04-24 落档)

### 池子定义 (NN33 ph)

```
模板: 33 条  (status=active + backendInstanceId=NN33)
       → 96 active 里过滤到 NN33 ph 真实 33 条

通道: 17 条  (需同时满足):
  · enabled=true && type=sms
  · backendInstanceIds 含 NN33 BID
  · 排除 "包料"、"对方给料"、"大官人Globe通道"  (对方给料, 你料子发不出)
  · 排除 "猫王" H005/H006 (需通道侧额外加白)
  → 剩 17 条: 7 Smart+TNT + 9 Globe+DITO + 1 GG家全网通

合法组合: 33 × 17 = 561
  Smart 侧: 33 × 7 = 231   → 配 Smart 号码包
  Globe 侧: 33 × 9 = 297   → 配 Globe/DITO 号码包
  全网通:   33 × 1 = 33    → 任意包
```

### 号码包匹配规则 (必做)

运营商约束**必须**在选包时应用, 不然配错就废:

```python
def pick_pack_for_carrier(carrier_group):
    if carrier_group == "Smart":
        return source.match(/smart/i) and not 'yo家黑名单'
    if carrier_group == "Globe":
        return (source.match(/globe/i) or source.match(/dito/i)) and not 'yo家黑名单'
    if carrier_group == "全网通":
        return any pack, not 'yo家黑名单'
```

### 通道分类规则 (按 adapter.name)

```
Smart+TNT 通道:  name.lower() 同时含 "smart" 和 "tnt"    → 7 条 (二三六七八九十 yo家)
Globe+DITO 通道: name.lower() 同时含 "globe" 和 "dito"   → 9 条 (一四五+十一..十六 yo家)
全网通 (GG家):   name 含 "GG家" 或 "全网通"              → 1 条
包料/对方给料:   name 含 "包料" or "对方给料"           → 排除
猫王加白:        name 含 "猫王"                         → 排除
```

### 数据落地

```
~/.hermes/state/bowjwj/pool.json   <- 池定义 (33 tpl + 17 ch + 561 组合)
stats.db.combo_coverage            <- 每组合的累计数据 (561 行, 运行时更新)
```

### hook: verdict() 自动 refresh

```python
# bowjwj_log.verdict(round_id, ...) 内部
try:
    import db as _db
    n = _db.refresh_combo_coverage_for_round(round_id)
    event(kind="combo_coverage_refresh", round_id=round_id, updated=n)
except Exception as e:
    event(kind="combo_coverage_refresh_error", round_id=round_id, error=str(e))
```

`db.refresh_combo_coverage_for_round(round_id)` 查该 round 涉及的所有 (tpl_id, sms_id) 对, 对 combo_coverage 表的对应行做 UPDATE (累计 tested_rounds/sent/click + 写 last_verdict).

### dashboard tab

组合矩阵是独立 tab, 不是主 dashboard section. HTML 有两个 `.tab-panel`:
- `#tab-dashboard` (原 6 卡片 + 轮次表格 + 组合 CTR 排行榜)
- `#tab-combos` (561 行大表 + 7 张汇总卡 + 筛选 + 排序)

### 再生池 (模板/通道变动时)

后台加新模板/通道 → 现有 pool.json 不会自动更新. 手动重建:
```python
# 重跑 pool 生成逻辑, 覆盖 pool.json, 然后重建 combo_coverage (DELETE + INSERT)
# 历史数据通过 refresh_combo_coverage_for_round 重刷回来
```

---

## 🐛 Dashboard 踩坑 (2026-04-24)

写 dashboard 加 tab/功能时必踩这 3 个坑:

### 坑 1: `<script>` 位置错 → `addEventListener` on null

**症状**: 控制台 `Cannot read properties of null (reading 'addEventListener')`

**原因**: `<script src=app.js>` 在 HTML 结构中靠前, 新加的 DOM 元素 (如 `#cb-carrier`) 还没渲染, JS 就跑到 `document.getElementById('cb-carrier').addEventListener(...)` 炸.

**修**: `<script>` 必须放在 `</body>` 紧邻之前, 保证所有 HTML 已解析.

```html
<body>
  ...所有 section...
  ...所有 tab-panel...
  <script src="app.js"></script>
</body>
```

写 HTML 插入新 section 时, 如果发现 script 已经在前面, 先把它挪后.

### 坑 2: 函数重名 → 后定义覆盖前定义

**症状**: 新加的 `renderCombos(d)` 读 `d.combinations`, 但 dashboard 实际跑的是老版 `renderCombos` 读 `d.combos`, 561 行全空.

**原因**: 之前已有一个 `renderCombos` (用于主 dashboard 的"组合 CTR 排行榜"), 我新写了一个同名. JS 同名函数后定义覆盖前定义, 但我的新版写在前面, 被老版覆盖.

**修**: 加新功能前 grep 现有 app.js:
```bash
grep -n "function renderCombos\|function renderXxx" app.js
```
找到同名的先删或改名. 或者全用唯一前缀 (如 `renderMatrixCombos` 和 `renderCtrRanking`).

### 坑 3: IIFE 启动模式下 `DOMContentLoaded` 监听器失效

**症状**: `initTabs()` 定义了但点击 tab 没反应, `document.addEventListener("DOMContentLoaded", ()=>{initTabs();...})` 没跑.

**原因**: app.js 尾部是 IIFE `(async () => { ... })()`, 页面加载时立即执行. 后追加的 `DOMContentLoaded` 监听器可能因为 DOM 已加载错过事件.

**修**: 初始化函数直接塞进 IIFE 顶部:
```javascript
(async () => {
  try {
    initTabs();            // 先绑事件
    initCombosTable();     // 再绑筛选/排序
    const data = await loadData();
    renderXxx(data);
    ...
  } catch (e) { ... }
})();
```

### 三坑联动诊断

dashboard 加新 tab/功能后报错, 按顺序查:
1. 控制台 console 看具体报错 → 定位是 null / 未定义 / 覆盖
2. `grep -n "function $name"` 看同名重复
3. HTML 里看 `<script>` 位置

---

### 目的
搞不清某个配置会产生多少 session / 成本时, 不要直接跑真轮, 先做**干验证**:

### 步骤
1. 构造最小 body (pack 数 = 疑问中的变量)
2. `POST /send-direct/test-send` 正常发送 → 拿到 response.verificationSessions
3. 从 response 得到真实 session 数 / 组合 / 分配
4. **立即告知 Willy approvalId, 请 TG 拒绝** (不 approve 就不发短信, 0 花费)

### 示例 (今晚实际用的)
```
干验证 #1: 1 tpl × 5 sms × 5 pack
  → response 显示 5 session, 每 session 1 pack, 全部 comboKey=(tpl0, smsN)
  → 结论: tpl 只有 1 个, 所以所有 session 都绑 tpl0, sms round-robin

干验证 #2: 5 tpl × 5 sms × 5 pack  
  → response 显示 5 session, 不是预期的 25
  → summary.targetLabel 显示"5 个验证会话"
  → 结论: session 数由 pack 数决定, 不是 tpl×sms 笛卡尔积
  → 节省了 $7 探索成本
```

### 关键动作: Willy TG 拒绝
```
approval 创建后, TG 会收到消息
Willy 点 "拒绝" 按钮 → approval.status = rejected → 所有 campaign 不发
或者等 10 分钟 TTL 自然过期也行
```

**拒绝后 session 残留在 DB 不影响后续轮次**, campaignIds 虽然创建了但 launchStatus 永远 pending 不发.

### 适用场景
- 新配置组合 (改了 pack/tpl/sms 数) 前先验证 session 数
- 怀疑某个新 body 字段行为不明时
- 接触新端点 (如 /continue-test, /confirm) 前摸响应结构
