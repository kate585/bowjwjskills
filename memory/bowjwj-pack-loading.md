---
name: bowjwj-pack-loading
description: Phone pack loading rules — avoid "黑名单" filter bug, supplement from direct API when categories insufficient
type: feedback
originSessionId: b149b5b1-a52c-4e6e-8e90-16821de31e00
---
## 号码包加载规则

**Why:** 2026-05-01 晚上发现所有包被 `_load_packs_direct` 的 `src_blacklist = ["黑名单"]` 误杀，导致 Smart=0 Globe=0 可用包。实际有 Smart=263, Globe=133 可用包。

**How to apply:**

1. **`_load_packs_direct` 黑名单只保留真正的垃圾源** (`["银河数据0430日", "测试"]`)，不能无脑过滤 "黑名单"——很多正规包的文件名包含此关键词。

2. **categories API 不够时自动补充 direct API:** `load_packs_for_carrier()` 末尾加了补充逻辑：当 categories 返回 < limit 包时，调用 `_load_packs_direct` 补充，去重后合并。

3. **包可用性验证:** 发送前手动验证包数:
```python
pack_count = len(load_packs_for_carrier("Smart", limit=200))
# 期望 ≥ 30, 如果 = 0 则检查 src_blacklist
```

4. **categories API packCount=0 不等于没包:** categories 的 packCount 可能为 0（包已被分配），但 direct API 仍有未分配包。categories 只是导航，不是真相源。
