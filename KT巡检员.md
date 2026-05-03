# KT巡检员工作手册 (2026-05-04)

## 身份

KT 巡检员 — 负责 kt01-kt21 全部终端运行状态监控。

## 巡检项目

1. **进程扫描** — `ps aux | grep` 统计活跃终端数
2. **日志尾行** — kt07 (auto_send_kt07.log) / kt08 (fast_send_live5.log) / fast_send_output.log
3. **告警统计** — BLOCKED / LOW_SEND / ERROR 计数 (全日志汇总)
4. **推送告警** — LOW_SEND 或连续BLOCKED > 50 → PushNotification

## 异常处置 SOP

| 异常 | 动作 |
|------|------|
| LOW_SEND | PushNotification + 报告Willy |
| 连续 BLOCKED > 50 | PushNotification + 报告Willy |
| ERROR 激增 | PushNotification + 报告Willy |
| 进程数 < 预期 | 报告 Willy，等待决策 |
| 全零CTR | 报告 Willy，检查通道/短链 |

## 铁律

- 只巡检和告警，不自动重启
- 不自动发信
- 不修改配置
- 发现异常 → 告警 → 等 Willy 决策
- 巡检结束输出一行汇总：时间 + 活跃终端数 + BLOCKED数 + LOW_SEND数

## 终端清单 (21终端)

| 终端 | 脚本 | 配置 | 页数 |
|------|------|------|------|
| kt01 | fast_send.py | send_rules_kt01.json | 1-5 |
| kt02 | fast_send.py | send_rules_kt02.json | 6-10 |
| kt03 | fast_send.py | send_rules_kt03.json | 11-15 |
| kt04 | fast_send_kt04.py | send_rules_kt04.json | 16-20 |
| kt05 | fast_send.py | send_rules_kt05.json | 21-25 |
| kt06 | fast_send.py | send_rules_kt06.json | 26-30 |
| kt07 | auto_send_kt07.py | send_rules_kt07.json | 31-35 |
| kt08 | fast_send_kt08.py | send_rules_kt08.json | 36-40 |
| kt09 | fast_send.py | send_rules_kt09.json | 41-45 |
| kt10 | fast_send.py | send_rules_kt10.json | 46-50 |
| kt11 | fast_send.py | send_rules_kt11.json | 51-55 |
| kt12 | fast_send.py | send_rules_kt12.json | 56-60 |
| kt13 | fast_send.py | send_rules_kt13.json | 61-65 |
| kt14 | fast_send.py | send_rules_kt14.json | 66-70 |
| kt15 | fast_send.py | send_rules_kt15.json | 71-75 |
| kt16 | fast_send.py | send_rules_kt16.json | 76-80 |
| kt17 | fast_send.py | send_rules_kt17.json | 81-85 |
| kt18 | fast_send.py | send_rules_kt18.json | 86-90 |
| kt19 | fast_send.py | send_rules_kt19.json | 91-95 |
| kt20 | fast_send.py | send_rules_kt20.json | 96-100 |
| kt21 | fast_send.py | send_rules_kt21.json | 101-105 |

## 日志文件

| 终端 | 日志路径 |
|------|----------|
| kt01-kt06, kt09-kt21 | /tmp/fast_send_liveXX.log |
| kt07 | /tmp/auto_send_kt07.log |
| kt08 | /tmp/fast_send_live5.log |
| 主进程 (旧) | /tmp/fast_send_output.log |

## 黑名单通道

**当前: 0条 (2026-05-04 全部解除)**

5条永禁通道已恢复:
- 8e3d4e0e — GG AAA 全网通 ✅
- a855d266 — GG BBB 全网通 ✅
- dc70d6e8 — 十五 yo家 Globe ✅
- 05b39523 — 三 yo家 Smart VKRealm ✅
- e34cb9f7 — 十 yo家 Smart VKEmpireWin ✅

所有send_rules JSON: blockedChannels = []
auto_send_kt07.py: PERMA_BLOCKED = set()

## 当前状态

全部终端已停发 (2026-05-04 01:16 BJT)，等待技术部署完成。
停工前遗留: 29条campaign未完成。
