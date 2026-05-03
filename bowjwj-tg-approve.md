---
name: bowjwj-tg-approve
description: bowjwj TG 自动批准。Willy 说"全部批准"、"自动批准"、"批一下"、"通过所有审批"、"approve all"时加载。打开 Telegram Web @aicrms_bot，一键点击所有"批准"按钮。
---

# bowjwj-tg-approve (TG 自动批准)

## 何时触发

- "全部批准" / "approve all"
- "批一下" / "通过审批"
- "自动批准" / "批量批准"
- "TG 还有几个待批" (先扫描不点击)

## 两种模式

### 模式 1: 一次性全量批准 (默认)

立即扫描 @aicrms_bot 对话中所有"批准"按钮，全部点击，报告结果后退出。

### 模式 2: 持续监听 (Willy 说"持续批准" / "开着自动批准")

后台持续运行，每 60 秒扫描一次，自动点击新出现的"批准"按钮。Willy 说"停"时停止。

### 模式 3: 先看后批 (Willy 说"看看有几个待批")

只扫描不点击，报告待批准数量，等 Willy 确认再执行。

## 执行脚本

```bash
# 一次性全量批准
python3 ~/.hermes/state/bowjwj/tg_approve_once.py

# 持续监听
python3 ~/.hermes/state/bowjwj/tg_auto_approve.py

# 只看不点
python3 ~/.hermes/state/bowjwj/tg_approve_once.py --dry-run
```

## 前置条件

1. **首次使用需要登录**: `python3 ~/.hermes/state/bowjwj/tg_auto_approve.py --login`
   - 会打开 Chrome 浏览器到 web.telegram.org
   - Willy 扫码或手机号登录
   - Session 保存到 `~/.hermes/state/bowjwj/tg_web_auth.json`
2. Playwright 已安装 (`pip3 install playwright && python3 -m playwright install chromium`)

## Session 过期

TG Web session 有时效。如果脚本报 "Session 过期"，重新登录:
```bash
python3 ~/.hermes/state/bowjwj/tg_auto_approve.py --login
```

## 输出格式

```
📋 TG 自动批准 | 2026-05-03 14:30:00
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 扫描到 5 个"批准"按钮
✅ 已点击 5/5
📊 批准详情:
  1. CAMPAIGN_SEND_VERIFICATION_TEST_APPROVAL — 已批
  2. CAMPAIGN_SEND_BATCH_APPROVAL — 已批
  3. ...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## 与其他 skill 关系

```
bowjwj-auto-campaign → 创建审批请求 → TG 通知
bowjwj-tg-approve    → 点击 TG "批准"按钮 → 审批通过
bowjwj-batch-send    → 批量创建审批 → 需要批量批准
```

## 安全闸门

- 一次性模式: 扫描到的全部点击，执行前显示数量
- 5+ 个待批: 显示数量后等 Willy 确认 (回复"批")
- 持续模式: 不限数量，自动全批

## 已知坑

1. TG Web 可能弹 "session expired" 需要重新登录
2. 网络不稳时按钮可能加载不全，多滚几轮确保全扫
3. @aicrms_bot 对话 URL: `https://web.telegram.org/a/?tgaddr=tg%3A%2F%2Fresolve%3Fdomain%3Daicrms_bot`
4. 不需要 Playwright 有头模式 (headless 即可)
5. 如果 Willy 同时在手机 TG 上点了批准，按钮已消失，脚本会跳过
