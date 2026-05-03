---
name: bowjwj-pack-source-binding
description: Iron rule: kt01-kt07→凯特ai发送, kt08-kt15→小财财ai发送, kt16-kt21→威龙ai发送, 包源固定绑定
type: project
originSessionId: 8b81172c-bd1f-4c06-8024-e4fcf2c9b3b8
---
# 包源绑定铁律 (2026-05-04)

**铁律 #13**: 终端包源固定绑定，不可跨组使用其他包源。

| 组 | 终端 | 包源 | 总量 |
|----|------|------|------|
| 凯特组 | kt01-kt07 | 凯特ai发送 | 22,744包 (2,275页) |
| 小财财组 | kt08-kt15 | 小财财ai发送 | 16,351包 (1,636页) |
| 威龙组 | kt16-kt21 | 威龙ai发送 | 76,780包 (7,678页) |

**Why**: 凯特组页面充足但单包源不可全矩阵, 小财财+威龙有独立库存, 分三组可并行跑不同包源互不抢包。

**How to apply**: 每个终端的 send_rules JSON 中 `packRules.searchQuery` 和 `packRules.sourceMustStartWith` 必须等于所在组包源, `_packSourceGroup` 字段标识所属组。任何跨组换包源必须Willy同意。
