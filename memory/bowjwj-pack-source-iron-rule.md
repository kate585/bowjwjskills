---
name: bowjwj-pack-source-iron-rule
description: 铁律: 包源固定凯特ai发送, 不可更换包源, 不可更改包名
type: project
originSessionId: 90be422a-8814-4457-816b-eab01a15d95f
---
## 凯特ai发送 包源铁律 (2026-05-03)

**铁律**: searchQuery=`"凯特ai发送"`, sourceMustStartWith=`"凯特ai发送"`. 包源和包名一律不可更改，须经Willy同意。

**Why**: Willy 指定固定包源。2026-05-03从"小财财ai发送"切换为"凯特ai发送"。实际包源为 `凯特ai发送M0503`，API q=凯特ai发送 匹配，sourceMustStartWith="凯特ai发送" 前缀匹配通过。

**How to apply**:
- 所有12终端 send_rules_ktXX.json 的 packRules.searchQuery="凯特ai发送" 和 packRules.sourceMustStartWith="凯特ai发送" 锁定
- NEVER 修改任何终端的 searchQuery 或 sourceMustStartWith 字段
- NEVER 修改包名过滤条件
- 任何更改须 Willy 明确批准
