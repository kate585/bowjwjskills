---
name: bowjwj-source-filter-match
description: Iron rule — sourceMustStartWith must match actual pack source prefix, otherwise ALL packs silently filtered to 0
type: feedback
originSessionId: dfcf31d8-ba08-4b1f-86ef-d9e8babcc757
---

## 铁律: sourceMustStartWith 必须匹配实际 pack source (2026-05-03)

**Why:** send_rules.json 中 sourceMustStartWith 设成了 "凯特ai发送：银河v数据4月" 但实际 pack source 是 "凯特ai发送1月全量数据..."，startswith 不匹配导致 20个包全部被客户端过滤掉，Available packs = 0。搜索引擎 q= 参数能正确返回结果，但客户端 source filter 把结果全杀了。

**How to apply:**
- sourceMustStartWith 必须和实际 API 返回的 pack source 字段前缀匹配
- 验证方法: 直接 curl API page，看 pack.source 实际值
- q= 参数负责服务端搜索，sourceMustStartWith 负责客户端二次过滤
- 两者必须独立验证正确
- 如果 sourceMustStartWith 太长不匹配，设回通用前缀如 "凯特ai发送"
