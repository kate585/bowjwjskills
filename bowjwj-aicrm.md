---
name: bowjwj-aicrm
description: Willy 自建的 AICRM 短信营销管理平台 (bowjwj.cc) 的 API 接入地图与操作约定。当对话涉及 bowjwj / AICRM / 短信活动 / campaign / 号码包 / 短链域名 / 代理账号 / 发送报表时加载此 skill。
---

# bowjwj AICRM (短信营销平台) 接入 skill

## 新后台覆盖规则 (2026-05-26)

以下规则优先级高于本文后面的旧 `bowjwj.cc` 历史记录。遇到冲突时按本节执行。

### Base URL / Tenant

```bash
BASE=https://aicrm.bo-pro.cc
TENANT=aicrm-default
JWT=$(cat ~/.hermes/state/bowjwj/.jwt)

curl -sS \
  -H "Authorization: Bearer $JWT" \
  -H "X-AICRM-Tenant: $TENANT" \
  "$BASE/api/me"
```

- 所有新后台 API 请求必须带 `Authorization: Bearer ...` 和 `X-AICRM-Tenant: aicrm-default`。
- 不把 JWT 写入仓库、日志、skill、memory。用户临时贴 token 时只作为本轮 header 使用。
- `/api/me` 已验证当前账号为 `SUPER_ADMIN`，新增权限含 `docs.read`、`dev.try`。

### API 字典是新真相源

新后台内置 API/Skill 字典，先查它，不再靠旧 bundle 反推。

```bash
GET /api/_meta/endpoints
GET /api/_meta/endpoints?module=campaigns
GET /api/_meta/endpoints?search=send-direct
GET /api/_meta/skills
GET /api/_meta/skills/:name/markdown
```

2026-05-26 实测：`/api/_meta/endpoints` 返回 419 个 endpoint，旧的“77 条 API 地图”只作历史参考。

### shortlinkMappingMode 枚举

新后台前端给 3 个值：

- `pack` — 4 位号码包短链，一个号码包/活动共用一条短链。
- `recipient` — 6 位号码级短链，每个号码独立短链。
- `content` — 固定文案短链，按原文发送，不替换 `${shortUrl}`。使用该模式时短信中必须已经粘贴平台生成/复制的可复用固定文案短链。

不要再写“只有 pack/recipient 两个值”。

### 新增重点模块

旧 skills 需要知道这些新模块存在：

- `metrics`: `/api/metrics/query`, `/api/metrics/freshness`, `/api/metrics/explain`, export/recompute jobs。
- `auto-send-plans`: 自动发送计划、lane、resource lifecycle、run-now。
- `orchestration-*`: workbench、policies、freezes、orchestrated-send-tasks。
- `phone-pack-access`: 用户包源授权、preview、explain。
- `phone-pack-labels/tags`: 号码包标签、生命周期、风险状态。
- `channel-scores` / `template-scores`: 通道和模板评分。
- `resource-health/system`: 系统资源健康。
- `tenants`: 多租户管理和 switch。

### 号码包新字段

`GET /api/phone-packs` 现在会返回 `poolView`、`poolStats`，单包字段含：

```text
sourcePoolType, sourcePoolOwnerUserId, sourcePoolOwner,
sourcePoolAssignedByUserId, sourcePoolAssignedAt,
labelLifecycleStatus, labelRiskStatus,
reuseLocked, assignmentCampaignDbId, assignmentCampaignId,
assignmentCampaignBatchId, assignmentStatus, assignmentLaunchStatus,
dataViewLocked, countryCodes
```

前端选择号码包时使用：

```text
requiredAccess=USE
poolMode=own_with_public_fallback
```

因此挑包不能只看 `source/cleanCount/reuseLocked/assignmentCampaignId`，还要考虑个人包源池、公共兜底池、标签生命周期和风险状态。

### 发信入口现状

旧入口仍存在：

```text
POST /api/campaign-templates/:id/send-direct
POST /api/campaign-templates/:id/send-direct/test-send
POST /api/send-verification-sessions/confirm
POST /api/send-verification-sessions/:id/continue
```

新后台同时增加：

```text
POST /api/campaigns/bulk-launch
POST /api/campaigns/bulk-send
POST /api/campaigns/:id/launch
POST /api/campaigns/:id/send
POST /api/campaigns/:id/send-batch
POST /api/campaigns/:id/test-send
POST /api/auto-send-plans/:id/run-now
POST /api/orchestrated-send-tasks
```

任何写/发/计划启动接口都必须先让 Willy 明确确认。只读 GET 可直接查。

## 何时加载

Willy 提到任一:
- `bowjwj.cc` / `AICRM` / 短信营销 / SMS campaign
- 号码包 / phone-pack / phone-whitelist / phone-blacklist
- 短链域名 / shortlink / 短链池
- 代理账号 / agent-account / affiliate
- 发送监控 / delivery monitor / 报表 / snapshot / FTD / CTR
- "登录 bowjwj / 操作 bowjwj / 查 bowjwj"

## 系统定位 (一句话)

## shortlinkMappingMode (短链映射模式) — 发信必选字段

系统前端只给 **2 个选项** (src/web-app/src/lib/shortlink-mapping.ts):

- `pack` — 4 位号码包短链, 一包共用一条短链 (省短链, 追踪粒度粗)
- `recipient` — **6 位号码级短链, 每号独立短链 ★ Willy 首选**
  - 粒度到人, 可识别具体哪个号码点击
  - 抗落地站风控切流更强
  - 默认应选这个, 除非专门要省短链资源

⚠️ 只有 pack/recipient 两个值, **不要写成 batch/campaign** (训练里 AI 容易瞎编).

## 博彩代理 (affiliate gaming) 的自建短信营销管理后台: 把号码包 + 短信模板 + 代理注册链 + 短链域名组合成 campaign 批次, 通过 SMPP 等通道发送, 归因到注册/FTD/投注流水。

## 凭据 (2026-04-24 改为本地缓存, 不再每次 TouchID)

**JWT 默认读本地文件**, 避免 `op read` 每次弹 TouchID:

```bash
JWT=$(cat ~/.hermes/state/bowjwj/.jwt)   # 600 权限, .gitignore 了
```

Python:
```python
import os
JWT = open(os.path.expanduser("~/.hermes/state/bowjwj/.jwt")).read().strip()
```

**JWT 过期续期流程** (每 7 天):
```bash
# 从 1P 刷新本地 (单次 TouchID):
op read 'op://Personal/Bowjwj/JWT/token' > ~/.hermes/state/bowjwj/.jwt
chmod 600 ~/.hermes/state/bowjwj/.jwt

# 或登录 bowjwj.cc 前端, DevTools 抓新 token, 手动写入
```

账密兜底 (passkey 站点, 密码走不通, 仅留作备用信息):
```bash
USER=$(op read 'op://Personal/Bowjwj/username')   # wtt689@gmail.com
PASS=$(op read 'op://Personal/Bowjwj/password')   # Aa123123
```

**⚠️ 禁区**: `.jwt` 绝不 commit. 已在 `~/.hermes/state/bowjwj/.gitignore` 登记.

⚠️ **JWT 7 天过期**。过期重新获取:
```bash
curl -sS https://bowjwj.cc/api/auth/login \
  -H 'content-type: application/json' \
  -d "{\"email\":\"$USER\",\"password\":\"$PASS\"}" | jq -r .token
# 把新 token 写回 1Password:
op item edit vkdv35fxvmirvnbalebp2ituwq --vault=Personal "JWT.token[concealed]=<新 token>"
```

(若后端启用了 passkey + 需 2FA, 上面可能 401, 让 Willy 手动贴新 JWT)

## 调用约定

```bash
BASE=https://bowjwj.cc
curl -sS -H "Authorization: Bearer $JWT" "$BASE/api/..."
```

- 列表接口一律支持 `?pageSize=N` (默认可能上千), **探测/调试一律加 `?pageSize=1`**
- 返回结构不统一: 有的是 `{items:[]}`, 有的是 `{data:[], total}`, 有的是 `{list:[]}`, 有的是裸数组。打之前先看示例
- 错误码: `AUTH_FORBIDDEN`(403 权限不足) / `RESOURCE_NOT_FOUND`(404 路由不存在, fastify 招牌) / `AUTH_REQUIRED`(401 token 过期或无效)
- fastify 的 404 错误 message 一定是 `Route <METHOD>:<PATH> not found` — 凭这个判断"我猜的路径错了" vs "权限问题"

## 用户与权限

**你的角色**: `SUPER_ADMIN` (超级管理员)

**你能做的 25 项权限**:
```
user.read/create/update/disable/password.reset
role.permission.read/manage
user.permission.manage
campaign.read/create/update/send
adapter.manage  domain.manage  shortlink.manage
phone_pack.read/manage  phone_blacklist.read/manage
text.read/manage
agent_account.manage
audit.read  attribution.read
system.config
```

**你现在已经能做 (SUPER_ADMIN 全权限)**:
- ✅ 用户/角色/权限 (`/api/users`, `/api/roles`, `/api/permissions`)
- ✅ 号码黑/白名单 (`/api/phone-blacklists`, `/api/phone-whitelists`)
- ✅ **发送记录/去重真相** (`/api/send-logs?campaignId=<CID>`)
- ✅ **操作审计** (`/api/audit-logs?resourceId=<CID>`)
- ✅ 全局配置 (`/api/global-config`)
- ✅ IP 白名单管理 (`/api/ip-whitelist` + `/api/ip-whitelist/my-ip`)

## API 地图 (77 条, 按业务域分组)

### 认证 & 个人
- `POST /api/auth/login` — email+password 登录拿 JWT
- `GET /api/me` — 当前用户 + effectivePermissions
- `POST /api/me/change-password`
- `GET/POST /api/me/passkey-status` + `/api/me/passkey/replace-{start,finish,verify}`
- `GET/POST /api/me/telegram-binding` + `.../generate|rebind-request|unbind-request|verify-{passkey,password,start}` (Telegram 绑定用于通知)
- `POST /api/passkey/{register,authenticate}-{start,finish}` (WebAuthn 流程)

### Dashboard
- `GET /api/dashboard/pending-tasks` — `{pendingCampaigns, failedAdapters, recentErrors}`
- `GET /api/dashboard/trend?days=7` — 每日 `{registrations, ftdCount, clicks}`

### 活动 Campaign (核心)
- `GET /api/campaigns?pageSize=N` — 列表, 字段含 campaignId/displayTitle/templateId/phonePackId/phonePackCountryCode/status 等
- `GET /api/campaigns/locked-batches` — 已锁批次 (锁了就不能改)
- `POST /api/campaigns/batches/lock` — 锁批次
- `POST /api/campaigns/bulk-delete`
- 活动模板 `/api/campaign-templates` — 写 smsText (含 `{$phone[10]}`, `${shortUrl}` 等变量), 绑 ticketRewards (FREE_SPIN/PRIZE_WHEEL/RAFFLE), activityName
- AI 文案 `POST /api/campaign-templates/ai-generate` / `ai-regenerate-sms` / `ai-send-template/test-send` / `ai-send-all-templates/test-send` — 批次/单条 AI 生成 + 试发
- `GET /api/campaign-templates/batch-status`

### 号码包 PhonePack
- `GET /api/phone-packs?pageSize=1000` — 每包 `{totalCount, cleanCount, countryCode, packIndex/totalPacks, fileName, source}`
- `POST /api/phone-packs/one-click-import` — 一键上传
- `POST /api/phone-packs/selection`
- `POST /api/phone-packs/bulk-delete` / `bulk-unlock`
- 已采集号码包 (从过往 campaign 沉淀): `POST /api/collected-phone-packs/verify-{start,passkey}` / `reuse-send-request` / `bulk-export-request` (需 passkey 验证, 敏感操作)

### 运营商前缀 CarrierPrefix
- `GET /api/carrier-prefixes/supported-countries` — `["PH","BR","MM","BD","PK","TH","NG","MX","IN","VN"]`
- `GET /api/carrier-prefixes` — `{countryCode, prefix, brand, enabled}` 如 `{BD, 88014, Banglalink, true}`
- `POST /api/carrier-prefixes/bulk` / `init-defaults`

### 短链域名 Domain
- `GET /api/domains?pageSize=N` — `{host, useForShortlink, shortlinkStatus, autoOfflineThreshold, sentSuccessCount, reservedQuota, remainingQuota, backendAdapters:[...]}`
- `POST /api/domains/batch`
- `POST /api/domains/provision/check` / `provision/tasks` — 自动开通 (DNS + HTTPS)

### 发送通道 Adapter
- `GET /api/adapters/instances` — 全量通道, type=`sms`|`gaming_backend` 等; configJson 含 driver(smpp)/host/port/systemId/sourceAddr/unitPrice/currency
- `GET /api/adapters/instances?type=gaming_backend` — 只博彩后端
- 配置密钥已自动 redact 为 `__OCRM_REDACTED_SECRET__`

### 代理账号 AgentAccount
- `GET /api/agent-accounts?pageSize=N` — `{agentName, affiliateCode, customerId, upline, registerBaseUrl, shortUrl, shortlinkDomainConfigId, status}`
- `POST /api/agent-accounts/batch-create` / `batch-update-shortlink` / `import`

### 短链回收
- `POST /api/campaign-recipient-shortlinks/reuse`

### 数据快照 & 报表
- `GET /api/snapshots?pageSize=N` — 单代理线 × campaign × 时间窗的聚合指标: `{clicks, registrations, ftdCount, depositAmount, withdrawAmount, validBettingAmount, commission, metricsJson:{deliveryRate, ctr, smsCost, cpa, ftdRate, uv, sentCount, ...}}`

### 发送验证 / 敏感审批 / AI 洞察 (只见前端入口, 接口路径尚未 100% 覆盖)
- `/api/send-verification-sessions` — 发送前人工/passkey 核验
- `/api/ai-assistant/sessions` — AI 助手会话
- 前端模块: `SensitiveApprovalCenter`, `AuditCenter`, `DeliveryMonitor`, `ReplayDashboard`, `OperationsReport`, `AttributionBoard`, `IntelligenceCenter`, `AiInsightPanel`, `FunnelChart`, `JobCenter`

## 前端路由线索

90 个 Vite chunk (仅命名, 不含路径):
```
Dashboard / ManagementDashboard
Login / PasskeyBind / TelegramBinding / IpWhitelist / UserManagement / GlobalConfig
CampaignList / CampaignCreate / CampaignDetail / CampaignCreateEntry
CampaignPhonePackPicker / CampaignRecipientShortlinkCenter
LockedBatches / PlainCampaignCenter / campaign-entry / campaign-lock
PhonePacks / PhonePackDetail / CollectedPhonePackCenter / OneClickPack
## ⚠️ 数据口径选择 (2026-04-24 教训)

bowjwj 有 3 层 API, 选错层会看不到业务真相:

```
技术层 (偏底层, 调试用):
  /api/send-logs?campaignId=<cid>         → target/success/dedup (发送物理层)
  /api/shortlinks/<slid>/visits            → 访客流水 (含 bot)
  /api/send-verification-sessions?ids=     → session 状态 + clickCount

聚合层 (业务聚合, 延迟大):
  /api/operations-report                   → 按 agent/campaign/date 聚合
                                             延迟 30-60min, 但跨时段 FTD snapshot 完整

★ 业务真相层 (batch 级完整视图, 实时):
  /api/replay-dashboard/batches/<batchId>  → 单 batch 完整 replay
                                             含 funnel + cost + AI + baseline + 拆分
                                             这是后台"批次复盘看板"的数据源
```

**规则**: 查"某组合效果"必从 replay-dashboard 入手, 别用 visits (漏注册/FTD).

取数链 (以 seq / campaign 起点):
```
seq → combo_coverage 拿 tpl+ch → sessions 拿 campaign_id
     → GET /api/campaigns/<cid> 拿 campaignBatchId
     → GET /api/replay-dashboard/batches/<batchId>  ★ 业务真相
     ← funnel.target/delivered/clicks/uv/registrations/ftd_count/ftd_amount
     ← cost.smsCost/costPerRegistration
     ← headline.healthSummary + ai.promptSummary (AI 建议文本)
```

本地 batches 表 (66 列) 就是 replay-dashboard 的镜像, 由 collect_batch.py 填.

PhoneBlacklist / PhoneWhitelist

## ⚠️ agent_line 归因陷阱 (2026-04-24 核实)

每个 batch 创建时系统自动建新 `agent_line` (nn33id089-nn33id098 这种连号). 返回的 `registrations` 疑似"每新 agent_line 自带 1 个系统默认账号" — 10 个独立 batch 全部 reg=1 太规整, 无 API 能看注册明细反向核实. 

**防范**: 在 follow-up / frozen 判定中:
- `registrations >= 2` 才算达标 (不是 >=1)
- `ftd_count >= 1` 才是真金白银 (无法伪造, 有真支付)
- 不信 rate 不信绝对数, 信 FTD
- L2 阈值 reg>=2, L3 阈值 ftd>=1 是刻意规避此陷阱的设计

## 🚨 hermes cron 上线必自检 (2026-04-24)

cronjob tool 返回 success 只是"任务进队列", 不等于真跑. 必须:
```bash
hermes cron status          # 看 "Gateway is running"
# 如果 "Gateway is not running":
hermes gateway install       # 装 LaunchAgent
hermes cron status          # 确认
```
创新 cron 后 5 分钟核查 `last_run_at` 不为 null 才算真上线.

## ⚠️ Dashboard HTML 结构强制规则

给 `~/.hermes/state/bowjwj/dashboard/index.html` 加新 tab/section 时:

**`<script src="app.js"></script>` 必须在 `</body>` 紧前, 所有 tab-panel 之后.**

踩过 3 次的坑 (2026-04-24):
```
症状: 页面报 "Cannot read properties of null (reading 'addEventListener')"
原因: script 在新 tab 面板之前加载, document.getElementById 找不到元素
修复: 把 <script> 标签挪到 </body> 紧前
```

加 tab 后自检命令:
```bash
grep -n "app.js\|</body>\|id=\"tab-" dashboard/index.html | tail
# script 位置必须 > 所有 tab-xxx 位置
```

### ⚠️ id 重名陷阱 (2026-04-24 二次踩)

**症状**: 新 tab 表格渲染"错位" — th 只有 7 列, 但 tbody td 渲染 10+ 列, 视觉错乱.

**原因**: 老 dashboard "🏆 组合 CTR 排行榜" section 和新 "组合矩阵 tab" **都用了 `id="combos-table"`**, `document.querySelector` 找到的是第一个 (老表头), 新表渲染时列数对不上.

**自检**:
```bash
grep -c 'id="combos-table"' dashboard/index.html
# 结果必须 = 1
```

**修复**: 删掉冗余的老 section, 用正则抓 `<section>.*<h2>🏆 XXX</h2>.*</section>` 整段删除, 别只改 id (老 section 已经无用).

**预防**: 重构 dashboard 加新 tab 时, 先 grep 确认 id 唯一 + 删除老的重叠 section, **不要让老代码和新代码共存**.

## 📊 转化漏斗 / 营收 API 分工 (2026-04-24 挖清)

两个看似重叠的 API, 实则职责完全不同, 选错会绕大圈:

### `/api/intelligence/dimensions` — 智能分析中心 (市场情报)
```
粒度:    按维度聚合 (smsChannel/textCopy/phonePack/timeSlot/backend/creator/batch)
返回:    funnel + cost + scores + radar + tags + trend
参数:    period=7d|14d|30d|custom, backendInstanceId?, activityId?, forceRefresh?
⚠️ 无法按人过滤: scores 已跨全系统聚合
用途:    看全系统 Top 通道/模板/包 (学标杆 / 竞对情报)
不用途:  看"我自己的 ROI" (做不到)
Cache:   服务端有内存 cache, forceRefresh=true 绕过
性能:    快, 但 intelligence/cross 用时 7s+ (数据量大)
```

### `/api/operations-report` — 运营报表 (个人/代理线归因)
```
粒度:    按 date/agent/campaign/batch/creator groupBy
返回:    sentCount/clicks/uv/registrations/ftdCount/depositAmount/
         withdrawAmount/validBettingAmount/commission/smsCost/
         registrationCost/ftdCost/ftdAvg/netAmount/netProfit/roas/roi
参数:    dateFrom/dateTo (必 <=90 天), backendInstanceId (必填),
         createdByUserId? ★, agentLineId? ★, activityId?, smsAdapterId?
用途:    看"我自己的 FTD 漏斗 / ROI / 净利润"
Cache:   服务端 60s cache (lockHash 影响)
```

### 决策树
```
问题 → API
"同行哪个通道 CTR 最高"    → intelligence/dimensions
"哪个模板 ROI 最高 (全系统)" → intelligence/dimensions
"我昨天发的 5 个 batch 效果" → operations-report?createdByUserId=me&groupBy=campaign
"代理线 X 的 FTD"            → operations-report?agentLineId=X
"按天看我过去 7 天总和"       → operations-report?groupBy=date&createdByUserId=me
- 号码黑/白名单 (`/api/phone-blacklists`, `/api/phone-whitelists`)

## 🔑 JWT 凭据本地化 (2026-04-24 起)

**硬规则**: bowjwj 所有脚本/skill 读 JWT 必须走本地文件, 不走 1Password (免 TouchID 干扰):

```python
# ✅ 正确
JWT = open(os.path.expanduser("~/.hermes/state/bowjwj/.jwt")).read().strip()

# ❌ 错误 (每次弹 TouchID, Willy 烦)
JWT = subprocess.run(["op","read","op://Personal/Bowjwj/JWT/token"], ...).stdout.strip()
```

**本地文件**: `~/.hermes/state/bowjwj/.jwt` (600 权限, 已 .gitignore)  
**过期**: JWT 7 天 TTL. 过期后从 bowjwj.cc 登录抓新 token 覆盖本文件.  
**凭据分层原则**: 高频 (每轮脚本 >=2 次调) 落本地 600 + .gitignore; 低频/高敏 (1P Secret Key 等) 留 1Password.

类似规则: **TG bot token** 也落本地 `.tg-creds.json` (600), 不走 1P.

## 🔍 探新业务 API 的 3 步验证法 (别凭印象)

发现新 skill 要调的 API 时, 禁止靠 API 名字猜业务语义. 走 3 步:

**step 1: 扫前端 chunk 拿候选 URL**
```bash
grep -rhoE "/api/[a-zA-Z0-9/_\-]+" /tmp/bow/js 2>/dev/null | sort -u | grep -iE "<keyword>"
```

**step 2: 看源码 zod schema 拿真实参数名 + 枚举值**
```bash
grep -n -B2 -A30 "^const \w+QuerySchema\|querySchema\s*=\s*z\.object" \
    ~/bowjwj/app/src/web/routes/*.ts
```

**step 3: 实跑验证关键过滤是否 server-side 生效**  
比如 `createdByUserId=` 在 operations-report 路由生效 (源码 `ensureOperationsReportBackendScope` 后直接进 where), 但在 `intelligence/dimensions` 里 **不生效** (role=PROMOTER 才 auto where.ownerId, SUPER_ADMIN 看全局聚合).

**实战教训 2026-04-24** (建 conversion-funnel skill 时):
- 差点用 intelligence/dimensions 做"我的 ROI", 源码一看 SUPER_ADMIN 拿的是全系统聚合, 不是自己的
- 改用 operations-report + createdByUserId, 源码 + 实跑双校验 pass
- 结果 conversion-funnel skill 两刀分工 (operations-report=我的 / intelligence=市场基线)

## ⚠️ 业务口径真相 — replay-dashboard 才是业务数据源 (2026-04-24 教训)

**血泪**: 2026-04-24 跑 batch10 时我用 `shortlinks/:id/visits` 汇报 "3 点击 0 注册", 
Willy 指出"跟后台不对", 核查发现每 batch 其实 1 注册, 之前 #67/#68 也漏了 reg=6/3 ftd=1.

### 两层数据必须分清

```
技术口径 (只到点击层):
  GET /api/shortlinks/{slid}/visits  → 访客流水, IP/UA/isBot, 拿来定位点击明细
  → sent_count, click_count, bot_count 从这里算
  → ⚠️ 只看到 "谁点了短链", 看不到 "是否注册/充值"

业务口径 (到转化层) ← 汇报给 Willy 用这个:
  GET /api/replay-dashboard/batches/{campaignBatchId}  单 batch 实时
    返回 headline.traffic.{clicks, uv, pv, rawClicks, ctr}
         headline.conversion.{registrations, ftdCount, depositAmount, validBettingAmount, netPnlAmount}
         headline.cost.{smsCost, costPerRegistration, ...}
         packs[] 每号码包拆
         lines[] 每代理线注册/FTD (agent_line_name)
  GET /api/operations-report?createdByUserId=<我>&groupBy=campaign  聚合 + FTD snapshot (60s cache)
  → 这里 reg/ftd 是 agentLine 归因的业务真相
```

### 监测必须双写

```
每次 monitor.py 跑:
  sessions 表要同时存:
    · 技术口径: sent_count / final_click_count / bot_visit_count
    · 业务口径: replay_clicks / replay_uv / replay_registrations / replay_ftd
    · 归因: agent_line_id / agent_line_name / campaign_batch_id
  combo_coverage 要同时累加:
    · total_sent / total_click (技术)
    · total_registrations / total_ftd / total_deposit (业务)

没落业务口径 = 后端数据过眼云烟, 下次还要再拉
```

### Schema 记录

`sessions` 表需要 7 列业务字段: `replay_clicks INTEGER, replay_uv INTEGER, replay_registrations INTEGER, replay_ftd INTEGER, agent_line_id TEXT, agent_line_name TEXT, campaign_batch_id TEXT`
`combo_coverage` 需要: `total_registrations INTEGER DEFAULT 0, total_ftd INTEGER DEFAULT 0, total_deposit REAL DEFAULT 0`

### 注册归因诡异现象 (待观察)

batch10 10 个独立 batch, 每 batch 各 1 注册, 太规整可疑:
- 假设 A: 代理线创建时系统默认 1 基础账号
- 假设 B: 归因窗口把激活瞬间用户算进
- 假设 C: 真用户注册 (10/10 概率低)

**观察法**: T+3h 重测, 如果数字不变 → A/B, 继续涨 → C. 先别把 10 注册当铁证.

## 🔥 数据口径优先级 (2026-04-24 血泪教训)

**3 个分层 API, 口径完全不同, 不能混用!**

```
┌─ 业务口径 ★ 主源 ★ ─────────────────────────────┐
│ GET /api/replay-dashboard/batches/<batchId>        │
│ GET /api/operations-report                          │
│                                                     │
│ 给的是: clicks/uv/registrations/ftdCount/          │
│         depositAmount/ROI/健康分/AI建议             │
│ 用途: 看赚钱了没 · 该不该放量 · 业务决策           │
└────────────────────────────────────────────────────┘

┌─ 技术口径 (辅助/debug) ─────────────────────────┐
│ GET /api/send-logs?campaignId=<cid>                │
│   → target/success/failed/dedup (SMPP 投递层)     │
│                                                     │
│ GET /api/shortlinks/<slid>/visits                  │
│   → 访客明细 IP/UA/isBot (点击流水)               │
│                                                     │
│ 用途: 排障 · 验证发送 · 看单个用户                 │
│ 不能代替业务口径! 缺 reg/ftd/deposit               │
└────────────────────────────────────────────────────┘
```

### replay-dashboard 完整字段 (65+ 个, 都有用)

```
headline.traffic:   rawClicks/clicks/uv/pv/ipCount/ctr/newVisitorRate
headline.conversion: registrations/registrationRate/ftdCount/ftdAmount/
                     depositAmount/validBettingAmount/netPnlAmount
headline.cost:       smsCost/costPerClickUv/costPerRegistration
funnel:              target→delivered→clicked→registered→ftd 各率 + endToEnd
quality:             pvUvRatio/ipUvRatio/newVisitorRate/bettingMultiplier
comparison.baseline: 历史同活动基线 (ctr/regRate/costPerReg/roi)
comparison.delta:    vs 基线差值
comparison.trend:    mixed/rising/falling
ai.promptSummary:    AI 文本分析
ai.metrics.roi:      AI 算的 ROI (最靠谱)
ai.topPacks/bottomPacks: 推荐放量/冻结的包
packs[].score/summary/anomalies: 单号码包 AI 分析
lines[]:             代理线级 reg/ftd/deposit
trafficDetails.source/region/ua/hourlyBreakdown: 流量拆分
window: 分析窗口 (通常 72H)
```

### 实测 #68 真相 (用新口径才看到)

```
旧口径 (visits): click=2, 没 FTD, 看着像废
新口径 (replay):  
  clicks=3 (后续增长), UV=3, reg=3, ftd=1
  depositAmount=100 PHP, validBetting=176.3
  AI.roi = 3.53 (真赚钱!)
  quality.pvUvRatio=1 (不作弊), newVisitorRate=100 (全新客)

→ 爆款组合, 如果只看 visits 会错失放量时机
```

### 关键坑

1. **replay-dashboard 60s cache**: 新发 batch 可能延迟
2. **"每 batch 1 注册" 可能是 snapshot 伪信号**: 新建 agent_line 有系统默认, reg 判断阈值应 >= 2
3. **FTD 有 T+3 ~ T+24h 回收延迟**: 别 T+30min 就判 ftd=0 冻了
4. **operations-report summary 有 60s+延迟**: 新 batch 短期查不到
5. **ctr 字段**: replay 里分母是 success_count (实发), 和自己算 `clicks/target` 不一样

### 本地 schema (重构后统一)

```
stats.db.batches 表 (66 列, 1 batch = campaignBatchId = 1 行)
  ├─ 主键: batch_id
  ├─ replay-dashboard 全字段映射
  └─ collect_batch.py 同步

stats.db.replay_snapshots 表
  每次采集存一份完整 JSON, 便于时间线回溯

collect_batch.py --all-open 每 5min cron 调

refactor 时机: 2026-04-24, Willy 说"跟后台不对"后全重写
```

## ⚠️ 真实发送数据唯一真相源 = send-log (非 cleanCount 估算!)

**错误**: 用号码包 cleanCount 或自己算的 "75-85%" 估 sent_count  
**正确**: 必查 `GET /api/send-logs?campaignId={cid}`

返回字段:
```
targetCount         实际投递给 SMPP 的条数
successCount        成功送达    ← sent_count 以此为准
failedCount         失败数
dedupSkippedCount   去重扣掉的 (黑名单/历史重复), 可能 30%+
status              success / failed
failureReason       失败原因
sentAt              真发出时间
adapterInstanceId   用的哪通道 (做交叉校验)
```

**真实案例 (#68 2026-04-24)**: pack cleanCount=200, 我估 `sent≈160`, 实际 send-log `target=135 success=135 dedup=65` (去重 32.5%). CTR 从 1.0% 错算 → 1.48% 真值.

## ⚠️ replay-dashboard 是业务真相源 (send-logs/visits 是技术分层)

后台"批次详情复盘看板"对应 API:
```
GET /api/replay-dashboard/batches/<campaignBatchId>
```

**完整字段** (我之前漏了一堆, 现在都要采):

```
headline.traffic:  rawClicks/clicks/uv/pv/ipCount/ctr/newVisitorRate
headline.conversion: registrations/ftdCount/ftdAmount/depositAmount/
                    validBettingAmount/netPnlAmount
headline.cost: smsCost/costPerClickUv/costPerRegistration
headline.healthSummary   ← AI 建议文本
comparison: baseline/delta/trend (mixed/rising/falling)
trafficDetails: sourceBreakdown/regionBreakdown/uaBreakdown/hourlyBreakdown
packs[*]: 每号码包单独评分 + AI summary
lines[*]: 代理线级 reg/ftd/deposit
ai: promptSummary/topPacks/bottomPacks/anomalies/metrics.roi
funnel: target/delivered/ctr/clickToRegRate/regToFtdRate/endToEnd
quality: pvUvRatio/ipUvRatio/newVisitorRate/bettingMultiplier/withdrawDepositRatio
window: start/end/label (72H)
```

## 🔴 sharedBatch 陷阱 (2026-04-24 踩, 错 20 倍)

```
错误: 把 packs[0].successCount 当成 batch 总 sent
  后果: 0307 round 报 83, 实际 1646 (20 pack 合并)

正确: batch 是 sharedBatch=true 时
  total_sent = sum(p.successCount for p in packs)

辨识: 
  len(packs) > 1 就是 sharedBatch, 一次请求多个 pack
  headline.traffic 已是全部 packs 聚合, 看 headline 就行
  packs[] 只用于 drill 到单 pack 质量分
```

## 🔴 test-send 19 pack = 实际发 19 pack, 不是只发 2

```
API 行为:
  POST /send-direct/test-send body: {phonePackIds: [...19 pack]}
  → 系统创 19 campaign, 挂 1 个 campaignBatchId
  → verificationSession.testedCampaignIds 只 2 个 (测试子集)
  → verificationSession.remainingCampaignIds 17 个
  → 但**所有 19 campaign 都有 plannedAt, 系统自动发送**!
  → 只需 1 个 approval 批准, 17 个"remaining"不需再批

误解后果:
  以为 remaining 17 还要 Willy 再批才发
  → 实际 approval 批了 = 19 个都发
  → 直接影响放量策略 (不是"测 2 → 选择放 17", 而是"一次性全发 19")

要"测 1 看效果再放量"必须:
  POST test-send body: {phonePackIds: [1 pack]}  ← 只传 1 个!
  然后手动新 POST 另一轮 {phonePackIds: [N pack]} 放量
```

**取数链**:
```
POST test-send 响应 → verificationSessions[i].testCampaignId (记下)
  ↓
GET /api/send-logs?campaignId=<cid>  ← 1 campaign 1 条 log, 主键查询
  ↓
sent_count = successCount (不是 targetCount, 不是 cleanCount)
```

**唯一性交叉校验** (4 条独立事实):
- send-log.campaignId == 你创建时记的 cid
- send-log.adapterInstanceId == 你传的 smsInstanceIds[0]
- send-log.sentAt 落在你创建窗口 (通常 10 秒内)
- send-log total=1 (不是列表筛重)

本地 schema: `sessions` 表 4 列 `target_count/success_count/dedup_skipped/campaign_id_csv` 持久化.
辅助函数: `db.fetch_send_log_for_campaign(cid)`

## ⚠️ sharedBatch 聚合陷阱 (2026-04-24 实测)

**错误**: replay-dashboard 响应的 `packs[0].successCount` 直接用作 batch sent
**正确**: 必须 `sum(p.successCount for p in packs)`

踩坑案例:
- 0307 轮 1 session 20 pack, 我只记 83 sent, 实际 1646 (差 20 倍)
- seq68-release 19 pack, 差点只记 50 实际 950

判别 sharedBatch:
```python
packs = data.get("packs", [])  # 注意 is LIST
if len(packs) > 1:
    # sharedBatch: 19 packs 都挂在同一 batchId 下, 必须 sum
    total = sum(p.get("successCount") or 0 for p in packs)
else:
    # 独立 batch (每 pack 自己的 batchId): 取 pack[0] 即可
    total = packs[0].get("successCount")
```

后台业务: `sharedBatch=true` 且 `conversionAttributionMode=BATCH_ONLY` 时共享批次, 所有 pack 聚合一个代理线 / 1 个短链. test-send 一次传多 pack 就是 sharedBatch.

## 🔥 全栈漏斗真相源 = `/api/intelligence/dimensions`

**重大发现**: 别自建漏斗! bowjwj 后台的"智能分析中心"API 直接返回**全维度全漏斗全评分**, 不用手拼 send-log + visits + agentLine + 注册 + FTD.

```
GET /api/intelligence/dimensions
默认: period=近7天, 全系统
返回:
  scope        全局统计 (totalCampaigns, totalSent, 各维度分组数)
  dimensions:
    smsChannel  21 条     按通道
    textCopy    500 条    按模板 (最多 500, 全量 15065+)
    phonePack   500 条    按号码包
    timeSlot    6 条      按时段
    backend     2 条      按游戏后端
    creator     13 条     按用户
    batch       500 条    按批次
```

**每条数据结构** (通道/模板/包/时段都是同一 schema):

```
funnel: {
  target, delivered, deliveryRate,
  clicked, ctr,
  registered, registrationRate,
  ftd, ftdRate                     ← 注册→FTD 率
}
cost: {
  smsCost, costPerDelivered, costPerClick,
  costPerRegistration, costPerFtd, roi
}
quality: { newVisitorRate, pvUvRatio }
scores: {
  deliveryScore, clickScore, registrationScore,
  ftdScore, roiScore, costEfficiencyScore
}
compositeScore, rank, trend (stable/rising/falling)
tags: [{code, label, sentiment}]    ← best_overall / high_convert / high_roi
radar: { axes: [6 轴], ... }        ← 雷达图直接画
```

**相关端点** (同家族):
```
GET /api/intelligence/dimensions     全维度拉一把 (最常用)
POST /api/intelligence/cross         交叉分析 (primaryDim × secondaryDim × metric)
  body: {primaryDimension, secondaryDimension, metric, period?}
```

**用途**:
- conversion-funnel skill 直接围绕本 API 建, 不自建
- CTR / 注册率 / FTD 率 / ROI 全在这
- 排名/标签/评分现成

**默认"全系统视角"**, 要筛自己可能需要 `?userId=<my>` (未验证, 用时需测)。

## 📋 代理线 ↔ 短链 ↔ 号码包 业务规则

源码真相 (`bowjwj/app/src/core/campaign.ts`):

```
默认 shortlinkMappingMode = "pack"
业务规则:  1 号码包 → 系统自动创/挑 1 条 AgentLine → 生 1 个 ShortLink

涉及字段 (campaign 对象):
  phonePackId          你传入
  agentLineId          系统自动分配 (或从现有代理线池挑)
  agentAccountId       代理账号 (和 agentLine 绑定)
  shortlinkId          系统生成的短链 id
  customShortlinkDomainConfigIds  [你传 n 个], 系统在此池挑域名

为什么这么设计: 
  每代理线独立 affiliate 链 → 独立注册/FTD 回收路径
  一包一线 → 按号码包粒度追踪转化 (不同包的质量能独立评估)
```

**发信时短链域名怎么挑** (我之前的做法):

```python
# 目前: 全传 5 个历史域名, 系统随机
customShortlinkDomainConfigIds = [
    "7d96e095-...", "808b87ea-...", "cb4c35a9-...",
    "0fd370ec-...", "4583d70f-..."
]
# 改进方向 (未实现): 
#   按域名被封率/历史 CTR 加权挑, 淘汰坏域名
```

**创建 campaign 后取代理线 id**: `GET /api/campaigns/{cid}` 返回 agentLineId, 记到本地 sessions 表做转化追踪锚点。
CarrierPrefixes
Domains / DomainConfig / DomainProvisionCenter
AgentAccounts / Adapters
SendVerificationPanel / SensitiveApprovalCenter / DeliveryMonitor / ReplayDashboard
OperationsReport / AttributionBoard / IntelligenceCenter / AiInsightPanel / FunnelChart
AuditCenter / JobCenter
SmsVariablePreview
```

## 禁区 (不做)

1. ❌ **不主动触发发送** — 不 POST 任何 `/campaigns/batches/lock` + send 类动作, 除非 Willy 明确下单
2. ❌ **不调 `/ai-*/test-send`** — 哪怕是"试发", 也是真发到试发手机 = 真走 SMPP 扣费
3. ❌ **不调 `bulk-delete` / `bulk-unlock` / `provision/tasks`** — 写类批量操作必须 Willy 点头
4. ❌ **不调 `collected-phone-packs/reuse-send-request|bulk-export-request`** — 涉及沉淀号码包复用, 需要 passkey 二次验证, 我根本做不了
5. ❌ **不 rotate 或生成 AgentAccount / Adapter 配置** — 短信成本链路, 一步错全盘错
6. ✅ **自由使用**: 所有 GET 只读 (dashboard/campaigns/phone-packs/snapshots/adapters/domains/agent-accounts/carrier-prefixes 等) + 读 `/api/me`

## 模板管理 (CampaignTemplate) — 操作手册

**endpoint**: `GET /api/campaign-templates` (返回裸数组, 不是 `{items}`)

**关键字段**:
```
id            UUID, 选择/引用模板的唯一键
name          人类可读名 (中英混排, 如 "NN33 叶子 4.24 文案修改模版01")
activityName  活动名 (给玩家看的, 如 "NN33 New Jackpot")
status        active | disabled
campaignType  activity (带 ticket 奖励) | plain (纯短信)
smsText       短信正文, 含变量: {$phone[10]} ${shortUrl} 等
ticketRewardsJson  JSON 字符串, [{ticketType:FREE_SPIN/PRIZE_WHEEL/RAFFLE, ticketId, ticketQuantity}]
backendInstanceId  绑定的博彩后端 adapter UUID
defaultSendHour    默认发送时点 (0-23, 目前全部为 20)
```

### 1. 列模板 (查找)

```bash
BASE=https://bowjwj.cc
JWT=$(op read 'op://Personal/Bowjwj/JWT/token')

# 全量摘要
curl -sS -H "Authorization: Bearer $JWT" "$BASE/api/campaign-templates?pageSize=500" \
 | jq -r '.[] | [.status, .campaignType, .name, .activityName] | @tsv' | column -t -s$'\t'

# 只 active
curl -sS -H "Authorization: Bearer $JWT" "$BASE/api/campaign-templates?pageSize=500" \
 | jq '[.[] | select(.status=="active")] | {count:length, items:[.[] | {id, name, activityName}]}'

# 按关键字筛 (品牌/市场/作者)
KW="NN33"   # 或 "JILIEVO" / "[AI助手]" / "叶子" / "汤丁" / "BD05" ...
curl -sS -H "Authorization: Bearer $JWT" "$BASE/api/campaign-templates?pageSize=500" \
 | jq --arg kw "$KW" '[.[] | select((.name + .activityName) | contains($kw))] | map({id, name, status})'

# 按活动类型
curl -sS -H "Authorization: Bearer $JWT" "$BASE/api/campaign-templates?pageSize=500" \
 | jq '[.[] | select(.campaignType=="plain")]'

# 统计分布
curl -sS -H "Authorization: Bearer $JWT" "$BASE/api/campaign-templates?pageSize=500" \
 | jq 'group_by(.status)[] | {status:.[0].status, count:length}'
```

### 2. 查模板详情 (按 id 或 name)

```bash
TID="5e9b5281-81a6-4114-bfce-78ca4dbe086b"

# 方法 A: 如果有 /api/campaign-templates/:id (未验证, 先试)
curl -sS -H "Authorization: Bearer $JWT" "$BASE/api/campaign-templates/$TID" | jq

# 方法 B (稳): 从列表里 filter, 服务端保证返回完整字段
curl -sS -H "Authorization: Bearer $JWT" "$BASE/api/campaign-templates?pageSize=500" \
 | jq --arg id "$TID" '.[] | select(.id==$id)'

# 按名字模糊查 (Willy 常按名字说)
NAME="NN33 叶子 4.24"
curl -sS -H "Authorization: Bearer $JWT" "$BASE/api/campaign-templates?pageSize=500" \
 | jq --arg n "$NAME" '[.[] | select(.name | contains($n))]'

# 只看文案+奖励
curl -sS -H "Authorization: Bearer $JWT" "$BASE/api/campaign-templates?pageSize=500" \
 | jq --arg id "$TID" '.[] | select(.id==$id) | {name, smsText, rewards:(.ticketRewardsJson|fromjson)}'
```

### 3. "选择模板" (拿到 id 供后续 campaign 使用)

Willy 一般说"用 X 模板", 按下面顺序收敛到一个 UUID:

1. **完整 id** (36 位 UUID): 直接用
2. **精确 name** ("NN33 叶子 4.24 文案修改模版01"): `contains($n)` 应唯一
3. **模糊关键词** ("叶子 4.24"): 可能多条, **列出候选让 Willy 挑**, 不替他决定
4. **只给品牌** ("NN33"): 几十条, 拒绝猜测, 反问他要哪一条

**收敛原则**:
- 只有 **1 条 active** 匹配 → 自动用
- **多条匹配** → 列出 id + name + activityName + status, 让 Willy 点
- **全是 disabled** → 显式提醒"匹配的模板都被禁用了"再等他确认
- **0 条** → 列前 5 个最接近的 (按名字 Levenshtein)

### 4. 禁区 (模板相关)

- ❌ 不调 `POST /api/campaign-templates/ai-send-template/test-send` — 真发到试发手机, SMPP 扣费
- ❌ 不调 `POST /api/campaign-templates/ai-send-all-templates/test-send` — 批量试发, 扣费更多
- ❌ 不替 Willy 创建/改/禁用模板 — 目前没摸清 PUT/PATCH 路径, 动了不可逆
- ✅ 可自由: GET 列表 / GET 详情 / `batch-status` 查批次状态

## 一键发送流程 — 模板 → 号码包 → 锁批次 (全自动)

**业务语义**: Willy 说"发 X 模板" → Hermes 三步一把梭, 不再中途反问。

**为什么敢全自动 (决策依据 2026-04-24)**:
- 号码包发送后系统侧自动进 `reuseLocked=true`, 不可能重复发, 发错市场也不可能 (模板绑 backend, 号码包也绑 backend, 必须同一个)
- 不设预算闸门 (Willy 对自己系统熟)
- 失败任意一步立即停 + 原始响应打印给 Willy

**链路 (源码反推, 2026-04-24 已验证)**:
```
[1] POST /api/campaign-templates/{id}/create-campaign-draft   ← ❗ 不是"创建 draft"
    → 只返回模板预填字段 {templateId, templateName, backendInstanceId, activityName,
       smsText, ticketRewards[], plannedAt, validFrom, validTo}
    → 服务端不创建记录. 前端拿这个填表单, 然后:

[2] GET /api/phone-packs/categories?backendInstanceId=<从模板带>&page=1&pageSize=50
    → 列候选 categories {key, title, packCount, totalCleanCount}
    GET /api/phone-packs/categories/{key}/packs?backendInstanceId=X&page=1&pageSize=50
    → 某分类下的具体 packs
    POST /api/phone-packs/selection  body={ids:[packId1, packId2, ...]}
    → ⚠ 这不是"提交选中", 是"验证号码包有效性"
## 真相源: GitLab 源码仓库

**重要**: bowjwj.cc 的 TypeScript 源码已托管在 Willy 的自建 GitLab。接口 body / 审批触发等问题, 先拉源码验证, 不靠前端 bundle 反推。

拉取步骤 (从 1Password 取 root 密码, 换 OAuth token, 克隆到本地缓存):

仓库地址: 47.83.26.52/00000/app.git (HTTP, 通过 OAuth token 认证)
本地缓存: ~/bowjwj/app

命令 (首次一次即可):
- 从 1Password item `sa5eyfnv2tgodqw3lbqtpnc5ti` 取 password
- POST http://47.83.26.52/oauth/token 拿 access_token
- git clone --depth 30 --branch master http://oauth2:TOKEN@47.83.26.52/00000/app.git

仓库结构 (进入本地副本后定位):
```
src/web/routes/             Fastify 路由 (API 定义真相源)
  campaigns.ts              活动 CRUD + lock + send-batch
  campaign-templates.ts     模板 + send-direct (关键入口)
  send-verification.ts      测试发送轮询
  phone-packs.ts            号码包
  sensitive-approvals.ts    审批 (只 get/list/cancel)
src/core/
  send-verification-service.ts   轮询业务
  send-verification.ts           evaluateVerificationWindow / selectNext
  send-verification-store.ts     session schema
  sensitive-approval.ts          审批流 (含 Telegram 回调)
prisma/schema.prisma        数据模型
web-app/src/                React 前端 (Vite)
```

## 一键发送流程 — 真相版 (从 TypeScript 源码读出来)

⚠️ **之前基于前端 bundle 反推的 "create-draft → selection → lock" 三步流程是错的**。真相从仓库源码 src/ 读出来如下。

### 单一入口: `POST /api/campaign-templates/:id/send-direct`

不是三步, 而是**一个 API 搞定**:

```
POST /api/campaign-templates/{initialTemplateId}/send-direct
权限: CAMPAIGN_CREATE + CAMPAIGN_SEND
body = {
  templateIds:    [string],  // N 个模板 id (同 backend 且同 campaignType)
  smsInstanceIds: [string],  // M 个 SMS 通道 id
  phonePackIds:   [string],  // K 个号码包 id
  shortlinkMappingMode: "pack" | ...,   // "4位号码包短链"对应 pack
  shortlinkMode: "domain" | "adapter",  // domain 走 customShortlinkDomainConfigIds, adapter 走 shortlinkAdapterInstanceId
  customShortlinkDomainConfigIds?: [string],
  shortlinkAdapterInstanceId?: string,
  plannedAt?: string (ISO),   // 计划发送时间; 不传立即发
  titlePrefix?: string,       // 活动标题前缀, e.g. 日期时间
  targetUrl?: string,         // plain 类型必填
  verificationSessionIds?: [string],  // 如果带这个, 是"从已有 session 确认发送"分支
}
```

**后端行为** (`prepareDirectTemplateCampaigns` + `CAMPAIGN_SEND_BATCH_APPROVAL`):
1. 校验所有模板同 backend + 同 campaignType
2. 组装 `N 模板 × M 通道` 个 campaign 记录 (各配一个 SendVerificationSession)
3. 每个 session 分配到 K/N/M 个号码包
4. **创建 1 个 sensitive approval** (不是 N×M 个)
5. 返回 `202` + approval id, Telegram 通知 Willy
6. Willy TG 点 Approve → 真正 `sendVerificationCampaignRound` 执行 → 每个 session 发第 1 包 (100 条) → 轮询 10s

### 轮询点击 (读心跳)

```
GET /api/send-verification-sessions?ids=<逗号分隔 id 列表>
→ {items: [{
    id, clickCount, status, pollUntil,
    testedPhonePackIds, remainingPhonePackIds, remainingCampaignIds,
    lastSelectedCampaignIds, ...
  }]}

status 机制 (源码 evaluateVerificationWindow):
  clickCount > 0              → "passed"
  now <= pollUntil            → "testing"
  hasRemaining                → "no_click"
  else                        → "exhausted"

Willy 的业务门槛是 clickCount > 3 (严格 > 3, 即 >=4), 由轮询逻辑层判, 不在系统里
```

### 放量 (批量 confirm, 1 次审批)

```
POST /api/send-verification-sessions/confirm
body = {sessionIds: [string]}   // 所有 clickCount > 3 的 session 一次性传

→ 创建 1 个 CAMPAIGN_SEND_VERIFICATION_CONFIRM_APPROVAL
→ Willy TG 点 Approve → confirmVerificationSessions 把这些 session 的 remaining 19 包一次性发
```

### 继续测试 (如果想给 clickCount ∈ (0,3] 的 session 再一包)

```
POST /api/send-verification-sessions/{sessionId}/continue
→ 单个 session 再发 1 包 (另 1 次 CAMPAIGN_SEND_VERIFICATION_TEST_APPROVAL)
注意: 这个是单个 session, 不是批量
```

### 完整一轮 = 2 次 TG 审批

1. `/send-direct` 触发 → TG 审批 1 → 35 个 session (smart 套) 各发第 1 包 → 10s 轮询
2. 累积 clickCount > 3 的 session, `/confirm` 触发 → TG 审批 2 → 放量剩 19 包

**关键决策点**: 业务规则"每 3 分钟一轮 × 2 套并行 × 7h/天发送窗口" ≈ **~560 次 TG 点击/天**。
手点不现实, 必须选一条:
- 改源码加 bypass (Willy 是代码 owner)
- 降低节奏 (30 分钟一轮)
- TG userbot 自动批 (风险大)
- 限制到只在某些 power hour 发

## 🔴 铁律：发送必须搭配票卷 (2026-04-29)

**每一条模板必须配置 RAFFLE 2659055 + 7天有效期，否则发送全部失败。PATCH 不生效，必须在 POST 创建时设置。**

```
创建模板必带:
  ticketRewards: [{"ticketType": "RAFFLE", "ticketId": "2659055", "ticketQuantity": 1}]
  defaultValidityHours: 168
  validityPeriod: "7D"

票卷名: 幸运红包 SMS NN33VIP / ID:2659055
```

⚠️ **ticketRewardsJson (JSON string) 在 POST 创建时会被后端静默丢弃为 []！必须用 ticketRewards (array)。**
但 GET 返回的响应里字段名是 `ticketRewardsJson` (string) 和 `ticketRewards` (array) 两者都有。

## 🔴 正确发送流程 — 模版→活动→启动→发送 (2026-04-29)

**`/send-direct` 后端有 DB bug (UserTemplateDirectSendPreference 表不存在)，不可用。正确流程走前端原生三步:**

```
1. POST /api/campaign-templates
   → 创建模板 (ticketRewards array, RAFFLE 2659055, validityPeriod "7D")

2. POST /api/campaigns
   body: {templateId, activityName, smsText, ticketRewards, backendInstanceId,
          campaignType:"activity", shortlinkMappingMode:"recipient", shortlinkMode:"domain",
          customShortlinkDomainConfigIds:[前50个活跃域名...],
          scheduleEnabled:true, smsInstanceId, phonePackIds:[10-15包]}
   → resp: {id, campaignBatchId, batch:{sharedAgentMode:"SINGLE_AGENT_LINE", allocatedLineCount:1, launchState:"draft"}}
   ★ 多包共享1代理线, 无verification session ★

3. POST /api/campaigns/{id}/launch
   → 启动活动, 分配agentLineId

4. POST /api/campaigns/{id}/send  body:{smsInstanceId}
   → TG审批 → 全量发出 (所有包一次性发送)
```

**关键差异 vs test-send:**
- 无 verificationSessions（不需要先测1包再confirm）
- sharedAgentMode: SINGLE_AGENT_LINE（多包=1代理线）
- 创建后是 draft → launch → send 三步
- 每3秒可发1个包的【指定通道发信】(可传 phonePackIds 筛选单包)

## 硬约束: Sensitive Approval

**所有"真发"类 API 都走审批** (`createSensitiveApproval` 硬性检查):

- 没绑 TG → 这些 API 直接返回 400 TELEGRAM_NOT_BOUND
- 绑了 TG → 发 `/send-direct` 或 `/confirm` 返回 202, 真执行要 TG 点按钮
- Approval TTL = 10 分钟 (`APPROVAL_TTL_MS`)
- 执行锁 = 5 分钟 (`EXECUTION_LEASE_MS`)
- **没有"自动批准" API**, 只有 TG 回调 + callback token 校验

Willy 账号 `ec7fbe8c-3a0e-4823-b1da-0afc88c76f89` 的 TG 已绑: telegramId=6694261813。

## 🔴 Session 切分规则 — 实测铁律 (2026-04-24)

**⚠️ 之前 skill 说 "5 × 7 = 35 session 笛卡尔积" 是错的。正确规则:**

```
session 数 = len(phonePackIds)   ← 就是号码包数!
每 session 绑 1 个 (templateId, smsInstanceId, packId) 三元组
  - tpl 从 templateIds round-robin 采样
  - sms 从 smsInstanceIds round-robin 采样  
  - pack 一包一个 session

验证数据:
  1×1×2  → 1 session, allPacks=2 (pack 不足以切 session, 1 session 含 2 pack)
  1×1×20 → 1 session, allPacks=20, tested=1 remaining=19
  1×5×5  → 5 session, 每 1 pack  (sms 轮换, tpl 固定)
  5×5×5  → 5 session, 每 1 pack  (tpl 和 sms 都轮换)
  5×7×20 → 20 session, 每 1 pack (pack 数限制, 不是 35 笛卡尔)
```

### 推论: 要 "测 1 剩 N-1 放量" 必须 1×1×N

```
业务规则 "先测 1 包 + 过了发剩 N-1 包" 的实现:
  配置必须是 1 模板 × 1 通道 × N 包 → 1 session 管 N 包
  
  5×5×20 → 20 session 每 session 1 pack, remaining=[], 不能"放 19 包"
  1×1×20 → 1 session allPacks=20, remaining=19, 可以放
  
要同时测多个 (tpl, sms) 组合的 CTR, 每组合必须独立一轮 1×1×N
```

### 推论: "全量直发" vs "测试发信" 的 session 表现差异

```
POST /send-direct                  (裸, 不带 verificationSessionIds)
  → 直接创 N 个 campaign (等于 phonePackIds 数)
  → 每 campaign 1 pack 全发出去
  → 不创建 verificationSessions
  → 前端叫"一键发送"

POST /send-direct/test-send
  → 创 session (按上述公式切分)
  → 每 session 先测 1 个 pack (100 条), 剩余进 remaining
  → 创建 verificationSessions
  → 前端叫"测试发送"

POST /send-direct  带 verificationSessionIds=[...]
  → 从已有 session 放量
  → 只发 passed session 的 remainingCampaignIds
  → 若 0 个 session passed → 抛 "verificationContinueRequiresPassedCombo"
```

## 🔴 点击监控 — shortlink visits 才是真相

**监控 session.clickCount 有两个信息源**:

```
1) GET /api/send-verification-sessions?ids=   
   session.clickCount = 已过滤 bot 的人类点击  (countVerificationClicks 源码: isBot: false)
   
2) GET /api/shortlinks/{shortlinkId}/visits?pageSize=200
   返回每次访问的完整记录 {visitedAt, ip, userAgent, isBot}
   isBot=true: Google/bot prefetch (无业务价值)
   isBot=false: 真人点击
```

**实测发现 bot 过滤已做对**:
- 第 4 轮 shortlink 总 visits=6, 其中 3 条 isBot=true, session.clickCount=3 → 系统已自动去 bot

**session pollUntil 过期不影响 clickCount 继续累加**:
- pollUntil 只是 UI 的"倒计时窗口", 10 秒后 session 可能进 no_click
- 但 clickCount 每次 GET 都基于 shortLinkVisit 表实时 count, 继续涨
- **业务可以轮询超过 pollUntil**, 只看 clickCount 数字, 忽略 status

### 全局点击查询 (非 session 级)

```
GET /api/dashboard/user-metrics  → {clicks, smsSentCount, registrations, ftdCount} (今日)
GET /api/dashboard/trend?days=N  → 按天
GET /api/shortlinks/{id}/visits  → 流水 (包含 bot)
```

## 🔴 Approval 生命周期细节

```
APPROVAL_TTL_MS    = 10 分钟 (pending 后超时 expired)
EXECUTION_LEASE_MS = 5 分钟  (approved 后 5 分钟没跑完也失效)

状态转换:
  pending → approved (TG 点批) → executing → executed
                  → rejected (TG 点拒绝)
                  → expired (10 分钟没动)

TG 回调 vs approvedAt/rejectedAt 字段: 实测 approvedAt/rejectedAt 经常为 None
即使 status=executed, 也不一定有 approvedAt 时间戳。以 status 为准。
```

## 🔴 成本精算 (实测标定)

```
0.21 PHP / 短信 (smart&TNT 通道)
dedup 率 15-25% (号码包质量越好越低)
每 100 条 cleanCount 实发约 75-85 条

1×1×20 单轮:
  测试阶段 (第 1 包): 75-83 条 ≈ 16-17 PHP ≈ $0.28-0.31
  放量阶段 (剩 19 包): 1425-1577 条 ≈ $5.0-5.5
  
5×7×20 (每 session 1 pack, 不放量场景):
  测试阶段: 20 × 75 ≈ 1500 条 ≈ 315 PHP ≈ $5.6
```

从 `source` 字段反推运营商 (不区分大小写):

```
smart 套 → source 匹配 /smart/i  OR  /tnt/i
globe 套 → source 匹配 /globe/i
跳过     → source 匹配 /yo家黑名单/   (黑名单标识)
全网通   → source 含 "全网通", 两套都可用
```

号码包命名格式:
```
<来源描述> – <运营商> <包号>/<总包数>
示例: "银河0416 0419继续发 (2) – Globe 1094/2906"
```

## 固化的通道白名单 (Willy 指定, 2026-04-24)

**smart/TNT 套 (7 通道)**:
```
VKRealm(三) / VKEmpireWin(十) / VKVictoryX(七) / VKVikingWin(二) / 
VKQuest(六) / VKTechVibe(八) / LuckyPlay S(九)(全网通)
```

**globe/Dito 套 (9 通道)**:
```
LuckyPlay S 变体 (一/四/五/十一/十三/十四/十五/十六) + 菲律宾GG家全网通
```

(用 `/api/adapters/instances` 按 name 模糊匹配拿 uuid)

## 一键发送业务规则 (Willy 2026-04-24 定)

```
站点       : NN33 (ph 地区) backendInstanceId=c7ee7c4c-ce0a-49c9-880a-9315d07c07b6
模板       : 前端列表第一个 active + 追加 4 个 = 5 模板共用
号码包     : 20 包 × 100 条 (系统按 100 条/包 恒定)
节奏       : 每 3 分钟开一轮新窗口
并发       : smart/globe 串行 (先 smart 跑完再 globe, 或反之)
发送窗口   : 00:00-02:00 / 12:00-13:30 / 17:30-21:00 (北京时间)
plannedAt  : 当前 + 3 分钟
标题前缀   : 日期时间 YYYYMMDD-HHMM
短链映射   : pack ("4 位号码包短链")
管理域名   : 30 条

判定规则:
  单个 session clickCount > 3 (严格 > 3, 即 ≥ 4)
    → 该 session 放量 剩 19 包
  单个 session clickCount ∈ [1, 3] (passed 但未达标)
    → 调 /continue 再测下一包 (单 session 单独审批)
  single session no_click
    → 丢弃

成本估算 (每轮 smart):
  35 session × 第1包 100 条 × 0.21 PHP ≈ 735 PHP ≈ 13 USD
  放量按达标率不定, 最大 35 × 19 × 100 × 0.21 = 13,965 PHP ≈ 250 USD (极端全达标)
```

## 常用只读片段 (拷贝即用)
- [ ] shortlinkMappingMode 全部枚举值 (已知 "pack" = 4 位号码包短链)
- [ ] OneClickPack 前端组件的简化流程 (可能是"一键导入号码包"不是"一键发送", chunk 名容易混淆)

## 真实一键发送链路 (从 CampaignCreate + Texts + SendVerificationPanel 源码反推)

⚠️ **不是之前以为的"三步 create-draft / selection / lock"**, 正确链路:

```
[A] GET  /api/campaign-templates?backendInstanceId=X&campaignType=activity&status=active
    → 列该包网站点下的可用模板 (这是按 backend 过滤的, 跟全量列表不同)

[B] (可选) POST /api/campaign-templates/{tid}/create-campaign-draft  body={}
    → resp: {templateId, templateName, backendInstanceId, activityName, smsText,
             ticketRewards:[], plannedAt, validFrom, validTo}
    → 仅返回预填字段, 不创建实体 (之前踩坑以为这是第一步)

[C] GET /api/phone-packs/categories?backendInstanceId=X&page=1&pageSize=50
    GET /api/phone-packs/categories/{key_urlenc}/packs?backendInstanceId=X&page=1&pageSize=50

[D] POST /api/phone-packs/selection  body={ids:[...]}
    → resp: {items:[...]}   失效号码包会被过滤掉
    → 取 items.id 进入下一步

[E] GET /api/adapters/instances/{backendInstanceId}/promotion-tickets
    → activity 类型模板需要 ticket 奖励, 从这里取可选 ticketId + ticketName

[F] POST /api/campaigns   ← **真正创建 + 测试发信的入口**
    activity body = {
      activityName, shortlinkMappingMode, smsText,
      backendInstanceId, smsInstanceId,
      scheduleEnabled, phonePackIds:[...],
      ticketRewards: [{ticketId, ticketQuantity, ticketType, ticketName}],
      templateId,                  // 关联模板溯源, 可选
      plannedAt?, validFrom?, validTo?,
      shortlinkAdapterInstanceId? | customShortlinkDomainConfigId(s)?
    }
    plain body = {
      campaignType:"plain", shortlinkMappingMode, smsText,
      backendInstanceId, smsInstanceId, scheduleEnabled,
      phonePackIds:[...], targetUrl, templateId?, ...
    }
    → resp: {id, campaignBatchId?, itemCount?, verificationSessions:[...], redistributionPreview?}

[G] 轮询: GET /api/send-verification-sessions?ids=<sessionIds>
    每 ~1s 调一次, 前端 UI 显示 10 秒倒计时
    session 字段: {id, templateName, smsInstanceName,
                   status: testing|passed|confirmed|no_click|exhausted,
                   clickCount,
                   testedPhonePackIds, remainingPhonePackIds, lastSelectedPhonePackIds,
                   pollUntil, remainingCampaignIds}

[H] 过了就发: POST /api/campaigns/{campaignId}/send-batch
              body = {smsInstanceId, verificationSessionIds: [...已通过的 id...]}
    没过继续测: POST /api/send-verification-sessions/{sessionId}/continue  body={}
              (仅当 status=no_click && remainingCampaignIds.length>0)

[I] (如果走"锁批次"路径而不是 send-batch, 见另一条)
    POST /api/campaigns/batches/lock  body={batchIds:[...], remark}
```

### session 状态机

```
testing   → 10 秒轮询中, UI 显示 "还剩 N 秒 (pollUntil 倒计时)"
passed    → 点击达标, 可 send-batch 发剩余号码包
confirmed → 已 send-batch, 开始真正发送
no_click  → 10 秒内无点击, UI 按钮变"继续测试"
exhausted → remainingCampaignIds 耗尽, 只能放弃
```

### Willy 的业务规则 (2026-04-24)

- **达标判据**: 单个 `session.clickCount > 3` 即可 (不是所有加总)
- 达标后: 调 `/campaigns/{id}/send-batch` 传该 session id, 把该 session 剩余号码包一次性发出
- 未达标: 放弃, 关窗口, 下一轮开新 campaign
- **不用 verificationMode/测试组**: 直接走正常 `POST /api/campaigns` 流程
- 每 3 分钟节奏: 待定 (见下"未解")

## 业务白名单 (Willy 固化, 不动态选)

### 包网站点

目前只跑 **NN33 (ph 地区)**: `backendInstanceId = c7ee7c4c-ce0a-49c9-880a-9315d07c07b6`

### 模板白名单 (NN33 ph 地区, 按前端默认展示顺序前 5)

```
主  (id=5e9b5281-81a6-4114-bfce-78ca4dbe086b) : 大官人通道 加白模版 3
追加 1: 大官人通道 加白模版 2
追加 2: 大官人通道 加白模版 1
追加 3: NN33 汤丁（高转化文案测试）
追加 4: NN33 到账领取 P333 综合分96.36 →
```

### 通道白名单

**smart/TNT 套 (7 个, 发 smart 号码包时用)**:
```
165b9ca3  九yo家短信 smart&TNT 抬头：LuckyPlay S
e34cb9f7  十yo家短信 smart&TNT 抬头：VKEmpireWin
c40db47c  七yo家短信 smart&TNT 抬头：VKVictoryX
0a30f2d0  二yo家短信 smart&TNT 抬头：VKVikingWin
df51fa52  六yo家短信 smart&TNT 抬头：VKQuest
feca8a41  八yo家短信 smart&TNT 抬头：VKTechVibe
05b39523  三yo家短信 smart&TNT 抬头：VKRealm
```

**globe/Dito 套 (9 个, 发 globe 号码包时用)**:
```
699847d5  一 菲律宾 yo家短信 Globe&Dito:LuckyPlay S
a1e0747e  四 菲律宾 yo家短信 Globe&Dito:Luckyplay S
04596485  五 菲律宾 yo家短信 Globe&Dito:Luckyplay s
e062ada6  十一 菲律宾 yo家短信 Globe&Dito:LUCKYPLAY s (副本)
f49e287b  十三 菲律宾 yo家短信 Globe&Dito:luckyplay s (副本副本)
f61e1f3f  十四 菲律宾 yo家短信 Globe&Dito:LUCKYPLAY S (副本)
dc70d6e8  十五 菲律宾 yo家短信 Globe&Dito:LUCKYplay S (副本副本)
4ecd202f  十六 菲律宾 yo家短信 Globe&Dito:LUCKYplay s (副本副本)
3ab371e1  菲律宾GG家(0.004)全网通
```

### 号码包过滤 (2026-04-28 更新)

- ❌ **source 含 "yo家黑名单"** → 跳过
- ❌ **source 含 "测试"** → 跳过 (机器人不发带"测试"的数据包)
- ❌ **source 含 "黑名单"** (3 个字) → 跳过 (机器人不发)
- ❌ **titlePrefix / 模板名 避免含 "test"** → 可能触发反垃圾规则
- ✅ smart / globe 分流规则 **尚未最终拍板** (Q3 未解)

### 固定配置

- `shortlinkMappingMode = "pack"` (4 位号码包短链, 一活动共用一条)
- 域名数 = 30 (从 `/api/domains` active 列表取前 30 条)
- 每轮选 20 包号码 (每包 100 条)
- 发送时间窗口 (北京时间): `[00:00, 02:00] ∪ [12:00, 13:30] ∪ [17:30, 21:00]`
- 计划时间 `plannedAt = now + 3min`, 不在窗口内则顺延到下一个窗口起点

## 踩坑记录 (增补 2026-04-24 自动化设计)

- **以为 `create-campaign-draft` 是第一步** → 其实不创建实体, 只返回预填值, 真正创建在 `POST /api/campaigns`
- **以为 `phone-packs/selection` 是"提交选中"** → 其实是"验证号码包是否有效", 真正的"选择"在 campaigns body 的 `phonePackIds` 数组
- **以为"测试发信"是一个独立接口** → 其实就是 `POST /api/campaigns` 的响应, 系统自动切分 verificationSessions 让前端轮询, Willy 口语说的"测试发信"不对应任何单独 API
- **用 "111" 模板尝试抓完整链路失败** — 这条模板绑的 backend 下 0 号码包。抓链路必须挑该 backend 有号码包的模板
- **Willy 口说"20 秒内观察点击量", 系统实际是 10 秒轮询窗口** — 以系统 `pollUntil` 为准, 不按用户口述固化
- **成本盲区**: 5 模板 × 7-9 通道 = 35-45 session, 每 session 第 1 包 100 条, 每轮测试就是 3500-4500 条真短信, 每 3 分钟一轮 = 日均 ~$8k USD SMPP 费。写自动化前必须和 Willy 对齐这个数字是否预期

## 已知未解 (下次继续)

- **Q3**: smart / globe 号码包按什么字段规则区分?
  - 候选 A: source 含 "smart"/"TNT" vs "globe"/"Globe"/"Dito"
  - 候选 A+: 按 source 里 "只能发 globe" / "只能发 smart" / "全网通" 精确判断
  - 候选 B: backendInstanceName 或其他字段
  - 双关键词冲突 (source 同时含 globe + smart) 的处理规则
- **Q4**: "每 3 分钟发一次" 语义:
  - (i) 两轮之间隔 3 分钟 (推荐解读, 一轮内 20 包当一个 campaign 一次性发)
  - (ii) 一轮内每包发送间隔 3 分钟
  - smart 套 / globe 套 串行还是并行 (如并行, 冲突号码包怎么避免重复使用)
- **成本**: 日均 $8k 测试费是否 Willy 预期?
- **"过了就发剩 19 包" 精确含义**:
  - (a) 只发那个过的 session 的剩余 phonePackIds
  - (b) 全部 session 的剩余 (包括没过的)
  - (c) 其他

## 常用只读片段 (拷贝即用)

```bash
# 当日概览
curl -sS -H "Authorization: Bearer $JWT" "$BASE/api/dashboard/pending-tasks" | jq
curl -sS -H "Authorization: Bearer $JWT" "$BASE/api/dashboard/trend?days=7" | jq

# 最近 20 个 campaign
curl -sS -H "Authorization: Bearer $JWT" "$BASE/api/campaigns?pageSize=20" | jq '.items[] | {campaignId, displayTitle, phonePackCountryLabel, phonePackCleanCount}'

# 各国号码包余量
curl -sS -H "Authorization: Bearer $JWT" "$BASE/api/phone-packs?pageSize=1000" \
 | jq '.data | group_by(.countryCode)[] | {country:.[0].countryCode, packs:length, total:([.[].cleanCount]|add)}'

# 活跃 SMS adapter + 单价
curl -sS -H "Authorization: Bearer $JWT" "$BASE/api/adapters/instances" \
 | jq '.[] | select(.type=="sms" and .enabled) | {name, driver:(.configJson|fromjson|.driver), unitPrice:(.configJson|fromjson|.unitPrice), currency:(.configJson|fromjson|.currency)}'

# 昨天所有代理线报表
curl -sS -H "Authorization: Bearer $JWT" "$BASE/api/snapshots?pageSize=200" | jq
```

## 踩坑记录

- 2026-04-24 探测发现 `/openapi.json`, `/docs`, `/swagger` 返回 200 但实为 SPA index.html (Vite 的兜底路由)。**本站没有公开 OpenAPI 文档**, API 地图靠抓 bundle.js 反推
- 首页 bundle 只有 7 条 API, 真实 API 在 90 个懒加载 chunk 里, 必须全量下载 `/assets/*.js` 再 grep
- fastify 路由表对 querystring 有时也会 match 进 URL 的一部分 (例如 `/api/phone-packs?pageSize=1000` 被当路径, 是前端代码里拼错的艺术残留, 不影响服务端)
- `configJson` 里的 password/secret 已经被服务端自动替换为 `__OCRM_REDACTED_SECRET__`, 任何渠道都取不出真实密钥 (安全设计合理)
- **2026-04-24 ($7 教训)**: `/send-direct` 和 `/send-direct/test-send` 是**完全不同语义**的两个端点, 差一个子路径。前者=全量直发, 后者=先测再放量。**有源码时**, 前端按钮背后的 API 路径必须从前端组件反查 (`web-app/src/pages/*.tsx` 里的 `handleXxx` + `apiPost`), **不能只看**从 bundle 提取的 API 清单猜语义。相关代码仓库在 GitLab: `http://47.83.26.52/00000/app.git`, 本地 clone `~/bowjwj/app`
- **2026-04-24 IP 白名单**: 启用后所有 `/api/*` 返回 `IP_NOT_WHITELISTED`。Hermes 开跑前必先 `GET /api/me` 自检, 403 就停下告诉 Willy 加白。长期方案: 用固定 IP 跳板机 (如 GitLab 服务器 47.83.26.52) 代调
- 2026-04-24 发现 **站点级 IP 白名单**: bowjwj.cc 有全站 IP 白名单拦截, 触发后所有 /api/* 一律 `IP_NOT_WHITELISTED` 403, 连 /api/me 都读不了。需要 Willy 在前端 `IpWhitelist` 页加白本机 IP `curl ifconfig.me`。开发机 IP 会变, 建议长期走 `47.83.26.52` ECS 跳板。
- 2026-04-24 发现 **`send-direct` vs `send-direct/test-send` 一字之差业务截然不同**, 详见 bowjwj-auto-campaign skill "🔴 核心纪律" 段。光读后端路由不够, 必须 rg 前端组件的 onClick 才知道按钮对应哪个端点

## 通用纪律 (来自实战, 先进此处再决定是否单列)

**⚠️ 有前端源码时, 绝不对着后端路由名字推断业务语义**

具体到 bowjwj:
- 后端路由: `/send-direct/test-send` vs `/send-direct` (字面都是"直接发")
- 前端组件: `web-app/src/pages/TemplateDirectSendModal.tsx`
  - `handleTestSend()` → `/send-direct/test-send` ← 前端叫"测试发送"按钮
  - `handleDirectSend()` → `/send-direct` 但带/不带 `verificationSessionIds` 是两种语义
- 决策流: Willy 说"测试发信" → 必须去 rg `TemplateDirectSendModal.tsx` 里 `handleTestSend` 对应哪条 URL

这条教训属于 **bwnew-architecture skill 里"黑盒 ≠ 白盒"原则的特例** — 但 bwnew 是 Rust/Java, bowjwj 是 TS/Fastify, 两套技术栈都踩了同类坑, 说明这是跨项目通用纪律, 不是 Rust 特有。

## 待补 (下次用到时再摸)
  - 从 chunk 反推链路 = `create-campaign-draft → phone-packs/selection → campaigns/batches/lock` → **全错**
  - 源码真相 (读 `src/core/send-verification-service.ts` + `src/core/send-verification.ts`):
    - `create-campaign-draft` **不是创建 draft**, 只返回模板预填值 (templateId/smsText/activityName/ticketRewards/plannedAt), 无 id 无写入
    - 真正创建入口 = **`POST /api/campaigns`** (一次性带完所有字段), 见 `CampaignCreate-*.js`
    - `POST /api/phone-packs/selection` 是**验证号码包有效性**, body `{ids:[...]}`, 返回剔除失效包后的 items
    - 一键发送真正入口 = `/api/send-verification-sessions/confirm` (发剩余) 或 `/:id/continue` (继续测下一包), 都是 **S1 敏感操作返回 202 需审批**
    - "每轮只测 1 包" 是硬编码: `phonePackCleanCount >= 100 ? [first] : slice(0,2)` (`src/core/send-verification.ts` 第 78 行附近)
    - `passed` 门槛是 `clickCount > 0` (同文件第 104 行), 不是 Willy 业务层要的 `> 3`。业务层想加严格阈值, **Hermes 自己轮询时过滤, 不要改系统**
  - 教训: **Willy 的代码能拿到就一定要拿** (自建 GitLab 有 root, 项目 id=1, 路径 `00000/app`)
  - 先读源码再摸 API — 核心路径在 `src/web/routes/<domain>.ts` + `src/core/<domain>-service.ts`
  - 单个 POST 试探可能创脏数据进前台列表, Willy 看得到; 写前先读代码

## 拿源码的正确姿势 (自建 GitLab)

凭据位置: `op item get sa5eyfnv2tgodqw3lbqtpnc5ti --vault=Personal --fields password --reveal`
GitLab 地址: http://47.83.26.52 (内网/自建, 没 HTTPS, 限内网场景)

流程:
1. 用 root 账号走 `POST /oauth/token` grant_type=password 拿 access_token
2. 用 token 走 `GET /api/v4/projects` 列项目, 找到 `00000/app` (项目 id=1)
3. **分支必须 master**, 不是 main — GitLab 默认 `main` 只有 Initial commit, 真正在开发的是 `master`
4. clone 时 token 走 HTTP basic header (`-c http.extraheader="PRIVATE-TOKEN: ..."`) 或 `GIT_ASKPASS`, 不要把 token 拼在 URL 里 (历史记录会留痕)

## 后端核心文件定位 (`00000/app` 仓库 · master 分支)

- `src/web/routes/<domain>.ts` — HTTP 路由定义 (fastify)
- `src/core/<domain>-service.ts` — 业务逻辑
- `src/core/<domain>-store.ts` — 数据访问
- `src/core/<domain>.ts` — 纯算法/schema 定义 (常有核心硬编码规则)
- `prisma/schema.prisma` — 所有数据模型
- `web-app/src/pages/*.tsx` — 前端页面 (TypeScript 源码, 比 Vite bundle 好读太多)

**规则**: 要摸一个接口行为 → 按顺序读 route → service → core/algo, 三层都扫过再动手。

## send-verification (一键发送) 真实机制

(读自 `src/core/send-verification-service.ts` + `src/core/send-verification.ts`, 2026-04-24)

### Session 状态机

```
testing   → 正在等待 10 秒窗口点击
passed    → clickCount > 0 (系统阈值) 或自定义阈值
no_click  → 10 秒过了还 0 点击, 且 remaining 还有
confirmed → confirmSessions 执行, 剩余包已入队发送
exhausted → no remaining, 结束
```

### "每轮测 1 包" 硬编码

```ts
// src/core/send-verification.ts 第 78 行附近
const selected = first.phonePackCleanCount >= 100
  ? [first]                              // ≥100 条 → 只测 1 包
  : remaining.slice(0, Math.min(2,remaining.length));  // <100 → 凑 2 包
```

### 3 个关键接口

- `GET  /api/send-verification-sessions?ids=<id1>,<id2>` — 轮询查点击, 每个 session 独立
- `POST /api/send-verification-sessions/{id}/continue` — 继续测下一包, 202 审批
- `POST /api/send-verification-sessions/confirm` body `{sessionIds:[]}` — 发剩余, 202 审批

### 写操作全是 S1 敏感审批

`/continue` 和 `/confirm` 都 `registerSensitiveApprovalAction({ riskLevel: "S1" })`:
- 返回 202 Accepted + approval request
- 需要 SUPER_ADMIN 在 SensitiveApprovalCenter 或 TG Bot 批
- Hermes SUPER_ADMIN 发出请求后, 真正执行要等人工批
- **所以"自动化"必须先搞清楚 Willy 的审批流配置**, 否则发出的都卡审批队列

## 🧱 本地基础设施 (2026-04-24 搭, 跨 session 持久化)

所有本地产物在 `~/.hermes/state/bowjwj/`, 组件:

```
~/.hermes/state/bowjwj/
├── stats.db               SQLite (6 表): rounds, sessions, polls, approvals,
│                          combo_stats, policy_events, shortlink_visits
├── events.jsonl           Append-only 事件流 (法医证据, 永不改)
├── policy.json            冻结名单 (channels/templates, D 策略双重确认)
├── bowjwj_log.py          L.event/L.http/L.round_write/L.verdict 日志 API
├── db.py                  log_round/log_session/log_poll/upsert_combo_stats
├── analyze.py             CLI 查询 (毫秒级, 纯本地)
├── sync.py                显式在线同步 (拉线上最新写 DB)
├── export.py              导 dashboard/data.json
├── policy.py              冻结引擎
├── rounds/<round_id>/     每轮完整快照 (request/response/polls/verdict/reflection)
└── dashboard/             静态 HTML + Chart.js, 通过 localhost:8080 看
    ├── index.html
    ├── style.css
    ├── app.js
    └── data.json          (由 export.py 生成)
```

### 查询纪律 (血泪) — 本地 vs 在线严格分离

| 动作 | 命令 | 耗时 | 碰网络? |
|---|---|---|---|
| 查日志 / 看数据 | `python3 analyze.py <cmd>` | <50ms | ❌ |
| 看 web dashboard | `open http://127.0.0.1:8080/` | 即时 | ❌ |
| 在线刷新某 round | `python3 sync.py <round_id>` | 5-30s | ✅ |
| 更新 dashboard 数据 | `python3 export.py` | <100ms | ❌ |

**Willy 说\"查日志\" / \"看数据\" → 只跑 analyze.py**, 不能顺手在线拉。  
**在线要显式触发词**: \"刷新\" / \"同步\" / \"拉最新\" / \"再查一下\".

以前的坑: 一段脚本混入多个 subprocess.run(curl...) + terminal(analyze), 3 分钟超时。根因: 我写日志却不信任它。纪律: **日志落盘那一刻 = 真相**, 查时不再在线验证。

### 查询命令集

```bash
# 本地查询 (毫秒级, 不碰网络)
python3 ~/.hermes/state/bowjwj/analyze.py summary      # 所有轮次汇总
python3 ~/.hermes/state/bowjwj/analyze.py combos       # 组合 CTR 排名
python3 ~/.hermes/state/bowjwj/analyze.py timeline     # 按 BJ 小时
python3 ~/.hermes/state/bowjwj/analyze.py cost         # 成本分布
python3 ~/.hermes/state/bowjwj/analyze.py frozen       # 当前冻结
python3 ~/.hermes/state/bowjwj/analyze.py session <id>  # 单 session 点击曲线
python3 ~/.hermes/state/bowjwj/analyze.py visits <id>   # 人类 vs bot 流水
python3 ~/.hermes/state/bowjwj/analyze.py events 30    # events.jsonl 尾 30 条

# Dashboard 服务 (file:// 协议 fetch 会 CORS, 必须起 http)
cd ~/.hermes/state/bowjwj/dashboard && python3 -m http.server 8080 --bind 127.0.0.1
# 或用 Hermes terminal(background=true) 挂后台
open http://127.0.0.1:8080/

# 在线同步 (显式)
python3 ~/.hermes/state/bowjwj/sync.py <round_id>   # 某轮最新进 DB
python3 ~/.hermes/state/bowjwj/sync.py              # 所有未结束 round

# Policy 管理
python3 ~/.hermes/state/bowjwj/policy.py show
python3 ~/.hermes/state/bowjwj/policy.py unfreeze channels <id_prefix>
```

### 双写模式 (落盘即信任)

每次业务操作两个写入:
1. `events.jsonl` (append) — 原始事件, 永不删
2. `stats.db` — 结构化索引, 可 SQL 查询

`bowjwj_log.py` 的 `verdict()` 已 hook 了双写, **并会同步 refresh `combo_coverage` 那个组合行** (只刷该 round 涉及的 tpl×ch 对, 不全扫).

Hook 实现 (`bowjwj_log.verdict` → `db.refresh_combo_coverage_for_round(round_id)`):
- 查该 round 涉及的所有 `(tpl_id, sms_id)` pair
- 对每 pair 跨全部 sessions 聚合 `SUM(sent_count), SUM(final_click_count), COUNT(DISTINCT round_id)`
- 拿最后一 round 的 verdict 作为 `last_verdict`
- UPDATE `combo_coverage` 对应 `combo_id=tpl[:8]_ch[:8]` 行

失败不阻塞: try/except, 出错只记 `combo_coverage_refresh_error` event, verdict 本身照样落.

新增业务写入应用 `db.py` 的函数而不是直接写 SQL.

## 🔴 批次 ID 体系 (2026-04-24 发现, 查发送记录必用)

系统原生按"一次操作"分批, **不需要自己拼"第一个/最后一个 id 区间"**:

```
campaign 对象字段:
  id                  UUID (无序, 不能做区间键)
  campaignBatchId     "BATCH-b7e39426-..."   ← 批次主键
  campaignBatchLineId "BATCH-xxx-line-N"     ← 同批次内行号
  campaignId          人类可读标识 (如 "20260424-NN33-凯总-100-U782")
  createdAt           ISO 时间戳 (有序)
```

**同一次 `/send-direct` 或 `/send-direct/test-send` 调用产生的所有 campaign 共享同一个 `campaignBatchId`**. 例如:
- 1 tpl × 1 sms × 20 pack test-send → 1 个 batchId 下挂 20 条 campaign (line-1 ~ line-20)
- 查批次: `GET /api/campaigns?campaignBatchId=BATCH-xxx` 或本地 `WHERE campaignBatchId=...`

"查发送记录 / 按批次看" 的正确做法:
1. 以 `campaignBatchId` 为主视图聚合
2. 聚合下属 campaign 的 status/launchStatus 得批次状态:
   - 全 pending + draft → 创建中
   - 全 scheduled → 等发
   - 全 sent → 发完
   - 混合 → 部分放量 (测试过 + 手动拒放量剩余)
3. 本地 `round_id` 降级为"测试闭环单位" (一 round = 1-2 个 batch: test batch + release batch)

## 🔴 资源清单 API (2026-04-24 快速摸底)

查"总共多少通道/模板/号码包" 的三个只读命令:

```bash
# 通道 (裸数组, 无 items 包装)
curl -sS -H "Authorization: Bearer $JWT" "$BASE/api/adapters/instances" \
 | jq 'length, ([.[] | select(.enabled)] | length)'

# 模板 (裸数组)
curl -sS -H "Authorization: Bearer $JWT" "$BASE/api/campaign-templates?pageSize=500" \
 | jq 'length, ([.[] | select(.status=="active")] | length)'

# 号码包 (返回 {data,total,page,pageSize,totalPages}, 注意是 data 不是 items)
curl -sS -H "Authorization: Bearer $JWT" "$BASE/api/phone-packs?pageSize=2" | jq '.total'
```

### adapters/instances 字段 (实测 2026-04-24)

```
字段: id, type, name, enabled, configJson, configInvalidSince,
      balance, createdAt, updatedAt, backendInstanceIds

type 枚举 (只见 5 种):
  sms              短信通道 (发送主力, 54/59)
  gaming_backend   博彩后端 (2 个: NN33, PH05)
  shortlink        短链服务 (1 个: Cutt.ly)
  tg_bot           TG 通知 (1 个)
  ai_copy          AI 文案 (1 个: VAI)

无 status 字段 (旧 skill 说 status=disabled/frozen 是猜的)
判"可用": 以 enabled=true 为准

"黑名单通道" ?  —  系统没有显式 blacklist type
  name 里的 "需加白" (如 "猫王通道 H005 需加白") ≠ 黑名单
  "需加白" 语义 = 通道侧要把我们号段加白后才能发, 是通道运营方限制, 不是系统分类
  系统没有给号码分黑白名单的通道字段
```

### "按站点筛通道/模板" 的正确判据 (2026-04-24 实测)

查 "NN33 ph 这个站点能用哪些通道/模板" 必须按结构化字段, 不能按 name 关键词猜:

```
adapters/instances[].backendInstanceIds  是数组 (复数, 一个通道可挂多个站点)
  NN33 ph 可用通道 = [a for a in adapters
                      if a.enabled and a.type=='sms'
                      and BID in (a.backendInstanceIds or [])]

campaign-templates[].backendInstanceId   是单数 (一个模板绑一个站点)
  NN33 ph 可用模板 = [t for t in templates
                      if t.status=='active'
                      and t.backendInstanceId == BID]
```

实测 NN33 ph (BID=c7ee7c4c-ce0a-49c9-880a-9315d07c07b6):
- 可用 SMS 通道 23 条 (全站 enabled SMS 54 条, 其中 23 关联此站点)
- 可用模板 33 条 (全站 active 75 条, 其中 33 绑此站点)
- 理论组合上限 759 = 33 × 23

**反面教训**: 靠 name 字面匹配 "菲律宾/yo家" 挑通道不可靠 (漏掉"大官人 Globe"等), 上面这个结构化判据才是真相.

## 🔴 组合池 seq 编号体系 (2026-04-24)

561 UUID 组合对话里引用太长, 固定分段 seq# 方便口语引用:

```
seq 分段 (固定不变):
  #1-#231     Smart 侧   (33 tpl × 7 Smart&TNT 通道)
  #232-#528   Globe 侧   (33 tpl × 9 Globe&Dito 通道)
  #529-#561   全网通     (33 tpl × 1 GG家 通道)
```

生成规则: `carrier_rank (Smart=0 < Globe=1 < 全网通=2) → ch 在组内顺序 → tpl 顺序`, 一次性写死到:
- `~/.hermes/state/bowjwj/pool.json` 的每个 combination 加 `"seq": N`
- `stats.db.combo_coverage` 加 `seq INTEGER` 列

**对话引用** (口语优势): "跑 #42" / "看 #67 历史" / "冻结 #120" / "#1-#231 批量测 Smart" 远快于贴 UUID.

**orchestrator 按 seq 执行**: `SELECT tpl_id, ch_id FROM combo_coverage WHERE seq=?` 反查完整 id, 再走 send-direct 流程.

## 🔴 组合池 = 模板 × 通道, 但**必须运营商匹配** (2026-04-24 关键)

**理论组合 ≠ 真可用组合**. 23 通道 × 33 模板 = 759 是毛数, 要扣两层:

### 第 1 层: 通道"能否用我们自己的号码包"

```
✅ 直接用: yo家 Smart&TNT (7) + yo家 Globe&Dito (9) + GG家全网通 (1) = 17 条
⚠️ 要加白: 猫王 H005/H006 (2) — 通道侧加白我们号段才能发
❌ 不能用: 包料通道 (4: 牛排/小新/龙少/大官人 Globe, name 含"包料"或"对方给料") — 这些通道只收对方给的号码
```

判据:
```python
skip = "包料" in name or "对方给料" in name or "大官人Globe通道" in name or "猫王" in name
```

真可扫通道: **17 条** (23 - 4 包料 - 2 猫王)

### 第 2 层: 运营商约束 (通道只能发对应运营商的号段)

```
Smart+TNT 通道 (7):  只能发 Smart 号段包
Globe+DITO 通道 (9):  只能发 Globe / DITO 号段包
全网通 (GG家, 1):     任何号段都能发

号码包 source 字段判运营商:
  "smart" in source (大小写不敏感): Smart 包
  "globe" in source: Globe 包
  "dito" in source:  DITO 包
```

通道运营商分组函数:
```python
def ch_carrier(name):
    n = name.lower()
    if "smart" in n and "tnt" in n: return "Smart"
    if "globe" in n and "dito" in n: return "Globe"
    if "GG家" in name or "全网通" in name: return "全网通"
    return None  # 不属于任何分组 (包料/加白) → 跳过
```

### 真·合法组合数

```
Smart 侧:   33 tpl × 7 Smart&TNT 通道 = 231 (配 Smart 包)
Globe 侧:   33 tpl × 9 Globe&Dito 通道 = 297 (配 Globe/DITO 包)
全网通:      33 tpl × 1 GG 通道       =  33 (任何包)
            ──────────────────────────
合计:                                   561 组合
```

"561 组合" 是 NN33 ph 的**真·可扫池**, 每个组合**绑定了号码包运营商类型**.

### 本地 pool.json + combo_coverage 表

```
~/.hermes/state/bowjwj/pool.json       ← 561 组合定义 (跑 bootstrap 脚本生成)
stats.db: combo_coverage 表
  combo_id (tpl_id[:8]+"_"+ch_id[:8]) PK, tpl_id, ch_id, carrier_group,
  tested_rounds, total_sent, total_click,
  last_tested_at, last_verdict, is_frozen

聚合来源: sessions 表 GROUP BY tpl_id, sms_id
```

Dashboard "组合矩阵" tab 直接从这 2 个文件渲染 561 行, 支持按运营商/状态筛选 + 列排序.

## 🔴 三层"黑名单"混淆 (2026-04-24)

bowjwj 里 "黑名单" 这词在 3 个层级出现, 语义完全不同, 别搞混:

```
1. 号码包层 (有黑名单概念) ✅
   source 含 "yo家黑名单" → 跳过 (sneaky spam 号段, 点击率异常低)
   筛选: "yo家黑名单" not in (pack.source or "")
   实测 NN33 ph 有 347 包黑名单, 占总数 0.8%

2. 模板层 (无黑名单概念)
   模板只有 status: active / disabled
   "禁用"(disabled) 是因为文案过期/被拒, 不是"黑名单"

3. 通道层 (无显式黑名单)
   type=sms + enabled=true 就能用
   name 里的 "需加白" 是通道侧的加白要求 (要联系上游), 跟"黑名单"不是一个概念
   "禁用"通道 enabled=false, 原因各种 (没额度/SMPP 故障), 不叫"黑名单"
```

**Willy 口中"黑名单通道"** 实测指: **号码包 source = "yo家黑名单"** 这层的过滤, 不是通道层.
```
```

### phone-packs 字段 (实测)

```
响应包装: {data:[...], total, page, pageSize, totalPages}
         (不是 items!  这一点踩了坑, 不同模块响应包装不同)

字段: id, backendInstanceId, source, totalCount, cleanCount, fileName,
      packIndex, totalPacks, totalRowsInFile, countryCode, countryLabel,
      remark, uploadedByUserId, reuseUnlockedAt,
      uploadedBy:{email,name},
      reuseLocked, assignmentCampaignDbId, assignmentCampaignId,
      assignmentCampaignBatchId, assignmentStatus, assignmentLaunchStatus,
      backendInstanceName, dataViewLocked, countryCodes

可用判据: cleanCount > 0  (系统里"已解析"就直接 cleanCount 非空, parseStatus 不在此接口返回)

"已用过" 判据: assignmentCampaignId 非空
  ⚠️ 实测 NN33 全 42574 包 assignmentCampaignId 都是 null. 可能:
      (a) 该字段只在"一键发送"流程临时写, 发完清回 null
      (b) 去 campaigns 表反查 phonePackId 才是真相
  结论: "号码包是否已用" 只信 stats.db 本地记录 + campaigns API 反查, 别信 pack 侧

总号码数速算:
  NN33(ph) backendInstanceId=c7ee7c4c-ce0a-49c9-880a-9315d07c07b6 共 42574 包
  单包平均 ~95 条 (cleanCount 经 dedup), 估 ~400 万条
```

### campaign-templates 字段 (实测)

```
响应: 裸数组 (不是 {items})
字段: id, name, status(active/disabled), campaignType, smsText, activityName,
      ticketRewardsJson, backendInstanceId, defaultSendHour, ...

无 countryCode 字段 (旧 skill "按 countryCode 分组" 是错的)
模板通过 backendInstanceId 绑站点, 不直接绑国家; 国家来自站点配置
```

### 一键资源清点 (推荐脚本)

```python
import subprocess, json
from collections import Counter
JWT = subprocess.run(["op","read","op://Personal/Bowjwj/JWT/token"],
                     capture_output=True,text=True).stdout.strip()
BASE = "https://bowjwj.cc"
def call(p):
    r = subprocess.run(["curl","-sS","-H",f"Authorization: Bearer {JWT}",f"{BASE}{p}"],
                       capture_output=True,text=True)
    return json.loads(r.stdout)

adapters = call("/api/adapters/instances")
templates = call("/api/campaign-templates?pageSize=500")
packs_meta = call("/api/phone-packs?pageSize=2")

print(f"通道: {len(adapters)} / enabled {sum(1 for i in adapters if i.get('enabled'))}")
print(f"  types: {Counter(i.get('type') for i in adapters).most_common()}")
print(f"模板: {len(templates)} / active {sum(1 for t in templates if t.get('status')=='active')}")
print(f"号码包 total: {packs_meta['total']}")
```

## 🔴 campaigns 列表 API 的 query 参数陷阱 (2026-04-24)

`GET /api/campaigns` 支持的 **server-side** 过滤参数**非常有限**, 踩坑记录:

| 参数 | 服务端实际认? | 说明 |
|---|---|---|
| `pageSize` | ✅ | 分页大小, 默认 20, 上限未测 (100 OK) |
| `page` | ✅ | 从 1 开始 |
| `launchStatus=scheduled` | ✅ | 真筛选, 只返 scheduled 的 |
| `createdByUserId=<id>` | ❌ | **服务端不认**! 返回全量, 需客户端二次过滤 |
| `campaignBatchId=...` | ? | 未测 (下次用到时验证) |
| `status=pending` | ? | 未测 |

**教训**: 看 `total` vs `items.length` 不匹配就是 query 被忽略了. 必须客户端 filter:

```python
# ❌ 错 (以为服务端帮你筛了, 其实没筛)
curl ".../api/campaigns?createdByUserId=$ME&pageSize=100"
# → total:5382 items:100, 里面全是别人的

# ✅ 对 (翻分页 + 客户端过滤)
for page in 1..N:
    items = GET f"?launchStatus=scheduled&pageSize=100&page={page}"
    mine.extend(i for i in items if i.createdByUserId == ME)
```

**自己的数据可能散在分页深处**, 只拉第 1 页看不到 ≠ 没有数据. wtt689 在全站 1155 条 scheduled 里 0 条是正常的 (因为 Willy 没激活的 scheduled 批次).

## 🔴 反查一个 batch 实际发的短链 (2026-04-24)

需求: "把 #68 那轮发的短链给我" / "那个 batch 具体跳哪个 affiliateCode"

**正解路径**: `GET /api/campaigns/{campaignId}` (单 campaign 详情)

踩过的死路 (别再走):
- ❌ `/api/replay-dashboard/batches/{bid}` 不含短链 URL 字段
- ❌ `/api/send-logs?campaignBatchId=` content 字段是空字符串
- ❌ `/api/campaign-batches/{bid}/...` 所有子路径 404 (此资源没 REST API)
- ❌ `/api/campaigns/{cid}/shortlinks` 404

取数链:
```
round_id → rounds/<rid>/step1_*_response.json
       → verificationSessions[0].testCampaignId 拿 CID (或 allCampaignIds[0])
       → 或 batches 表 SELECT round_id, batch_id WHERE ...
         然后 GET /api/campaigns?campaignBatchId=<BID>&pageSize=100
         items[*].id 就是该 batch 下的 CID 列表
       → GET /api/campaigns/{CID}
       → 从响应抽:
         .shortUrl                             # 发给玩家的短链 (如 https://mpwin.me/wzgf)
         .AgentLine.link                       # 代理线短链 (如 bonus-now.vip/ak77y6)
         .AgentLine.rawLink                    # 真实落地 URL
         .AgentAccount.rawRegisterUrl          # 带 affiliateCode 的注册页
         .AgentAccount.registerBaseUrl         # 主域名
         .agentLine.promotionDomain            # 推广域名
         .batchLines[*].AgentAccount.shortUrl  # 多代理线场景每条短链
```

**sharedBatch 场景**: batch 下多个 campaign (n packs) 时要遍历 batchLines[*] 各自的 AgentAccount, 每个可能不同短链 (系统 round-robin 从 customShortlinkDomainConfigIds 池挑).

**实测 #68 (seq68-20260424-0646)**:
- shortUrl: `https://mpwin.me/wzgf`
- agent shortUrl: `bonus-now.vip/ak77y6`
- 落地: `https://nn33-ph-win.cc/register?affiliateCode=jjbonus152`

## 🎯 发送弹窗 TemplateDirectSendModal 真相 (2026-04-24 源码反查)

前端唯一发送入口: `web-app/src/pages/TemplateDirectSendModal.tsx`

### 2 按钮分工

| 按钮 | handler | API |
|------|---------|-----|
| "测试发送" (绿色) | `handleSubmit` (L385) | `POST /api/campaign-templates/{tid}/send-direct/test-send` |
| "确认发送" (主按钮) | `handleDirectSend` (L447) | `POST /api/campaign-templates/{tid}/send-direct` |

两按钮**共用同一套表单字段** (`buildSendPayload`), 只是调不同 API.

### buildSendPayload 输出字段 (真相)

```ts
{
  templateIds,                    // 一次可多模板
  phonePackIds,                   // ★ 决定能否"同批放量"
  smsInstanceIds,
  shortlinkMappingMode,           // pack | recipient (只 2 值!)
  titlePrefix?,
  plannedAt?,
  verificationSessionIds?,        // ★ 带上就是"从已有 session 放量"
  
  // campaignType=plain 时追加
  targetUrl,
  shortlinkMode,                  // domain | adapter
  shortlinkAdapterInstanceId? | customShortlinkDomainConfigIds?,
  
  // activity 且需要短链域名时追加
  customShortlinkDomainConfigIds,
}
```

### 同批放量的唯一正确姿势

```
L0 测试: phonePackIds = [多个包, 比如 20 个]
         → 系统自动挑 1 个测试, 剩余进 session.remainingCampaignIds
         → 前端 state 存 verificationSession
L1 放量: 不关弹窗, 直接点"确认发送"
         → payload 自动带 verificationSessionIds
         → 系统发剩余 19 包, 同 batchId/agentLine/shortlink
         → FTD 归因连续可追

❌ 错误: 关弹窗重开, 选新包点"测试发送" = 19 个独立新 batch
   (2026-04-24 seq68-release-20260424-0911 就是这么踩的)
```

### 前端自带的 "放量 gate"

```tsx
disabled={hasVerificationFlow && !canContinueSend}
```

session 有了但还没达点击阈值, "确认发送"按钮灰, 不能硬点. 这是系统级防误放量.

## 🎯 域名选择规则 (2026-04-24 血泪)

### 系统自己的排序规则 (`normalizeSelectedDomainIdsByLatest`)

源码: `web-app/src/components/CampaignDomainPicker.tsx`

```ts
sortDomainConfigsByCreatedAtDesc:
  1. createdAt desc (最新添加的最前)
  2. 同 createdAt → host asc (zh-CN locale)

提交时会按上面重排, UI 勾选顺序不影响最终发送顺序
```

系统**不认** CTR / 健康度 / 点击历史, 只认创建时间.

### 发信前必做的 3 检 (系统不做, AI 要做)

```
1. 活性检查 ★ 必做
   for d in domains:
     curl -I -m 3 https://{d.host}/
   → 超时 / 非 200/302 / DNS 失败 ⇒ 本轮排除, 打 WARN

2. 历史表现 (有数据就用)
   查 stats.db.batches 里该域名所在 campaigns 的
     replay_clicks / replay_registrations / replay_ftd_count
   最近 7 天 0 click 或 click_uv < 1% ⇒ 降权

3. 多样性策略
   5 域名轮换 ≠ 风险分散
   5 个里 1 个挂 = 20% 号码废 (seq68-release 踩过)
   稳妥方案: 1 个刚验证过的主域 + 1 备胎
   或每 campaign 单域 (不轮换, 出问题范围最小)
```

### 2026-04-24 血泪案例 seq68-release-20260424-0911

```
19 包用 5 域名轮换 (vipbonus.vip / now.vip / claimbonus.vip / bonusfast.xyz / startbn.xyz)
now.vip 域名连接超时 (DNS 或 CDN 挂)
→ 4/19 campaign 流量打水漂
→ 950 sent 只 1 真点击 (vs 原版 135 sent 3 点击, 差 20 倍)

AI 当时的错: 直接复制 #68 原 request 里的 5 域名, 没做活性检查
```

### customShortlinkDomainConfigIds 的正确填法

```python
# 理想流程
domains_all = GET /api/domains (backendInstanceId=X)
alive = [d for d in domains_all if http_alive(d.host, timeout=3)]
top = rank_by_recent_ctr(alive, db="stats.db")[:3]
payload["customShortlinkDomainConfigIds"] = [d.id for d in top]

# 保底: 至少做 curl -I 预检
```

## 待补 (下次用到时再摸)

- `/api/send-verification-sessions` 具体字段
- `/api/ai-assistant/sessions` 会话结构
- `JobCenter` 背后的任务队列 API
- `SensitiveApprovalCenter` 审批流 API
- `/api/intelligence/*` 的正确路径 (当前 `/api/intelligence/ai-insight` 返回 404)
- `GET /api/campaigns?campaignBatchId=...` 是否认 (用到时验证)

## 🧩 Dashboard 多 tab 扩展踩坑 (2026-04-24)

给 `dashboard/index.html` 加新 tab (如组合矩阵 561 行) 时 3 个陷阱:

### 1. `<script>` 位置决定一切
`app.js` **必须在** 所有新 section HTML 之后, `</body>` 之前. 否则 IIFE 里 `document.getElementById("cb-xxx").addEventListener(...)` 会报 "Cannot read properties of null", 因为元素还没渲染到 DOM.

修复: 把 script 标签移到 `</body>` 紧邻前:
```python
import re
html = open("dashboard/index.html").read()
m = re.search(r'<script[^>]*src=["\']app\.js["\'][^>]*></script>', html)
tag = m.group(0); html = html.replace(tag, "", 1)
html = html.replace("</body>", tag + "\n</body>", 1)
```

### 2. 同名函数会静默覆盖
加新 tab 时若沿用旧函数名 (如 `renderCombos`), 旧版本会覆盖新版本, 新数据渲染不出来. 加新 render 前先:
```bash
grep -n "function renderXxx" dashboard/app.js
```
如有同名, 或改名 (`renderCombinations` vs `renderCombos`), 或删旧版.

### 3. IIFE 初始化顺序
dashboard 的 app.js 是 `(async () => { ... })()` 启动模式, 不是 `DOMContentLoaded` 监听. 新 tab 的 `initXxx()` 得加到 **IIFE 顶部** (loadData 之前), 不是塞 DOMContentLoaded:

```js
(async () => {
  try {
    initTabs();           // ← 先绑事件, 此时 DOM 已就绪 (script 在 </body> 前)
    initCombosTable();    // ← 排序/筛选事件监听
    const data = await loadData();
    renderXxx(data);
    ...
```

### 4. Tab 切换 CSS 最小集
```css
.tabs { display:flex; gap:4px; border-bottom:1px solid #30363d; }
.tab-btn { background:none; border:none; padding:8px 16px; cursor:pointer;
           border-bottom:2px solid transparent; }
.tab-btn.active { color:#58a6ff; border-bottom-color:#58a6ff; }
.tab-panel { display:none; }
.tab-panel.active { display:block; }
```

对应 HTML 结构:
```html
<nav class="tabs">
  <button class="tab-btn active" data-tab="dashboard">📊 仪表盘</button>
  <button class="tab-btn" data-tab="combos">🎯 组合矩阵</button>
</nav>
<div id="tab-dashboard" class="tab-panel active">...</div>
<div id="tab-combos" class="tab-panel">...</div>
```

initTabs 函数:
```js
function initTabs() {
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById("tab-"+btn.dataset.tab).classList.add("active");
    });
  });
}
```
