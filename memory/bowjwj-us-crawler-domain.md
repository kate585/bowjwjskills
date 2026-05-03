---
name: bowjwj-us-crawler-domain
description: Iron rule — check shortlink domains for US crawler targeting, use non-US Cloudflare domains ONLY
type: feedback
originSessionId: current
---

## 铁律: 检查短链域名是否被US爬虫盯上 (2026-05-02)

每个短链域名必须检查 US 爬虫风险，避免 rawClicks 被 US 安全扫描器污染。

### US爬虫症状
- **rawClicks>0 但 filtered=0** → US 爬虫在点击链接
- 美国安全厂商 (Google Safe Browsing, antivirus, email scanners) 会自动跟踪 SMS 中的链接
- 这些点击来自 US IP → Geo-IP 过滤将其标记为非菲律宾 → filtered=0
- 真实菲律宾用户点击也会被淹没在 US 爬虫噪音中

### 解决方案
- 使用 **非 US Cloudflare 节点**的域名 (如 AMS/Europe)
-  TLD 被 US 安全厂商重点监控 — 考虑混合使用其他 TLD
- 定期检查 replay-dashboard rawClicks vs filtered 比例
- 如 rawClicks>filtered 超过 10:1 → 域名可能被 US 爬虫盯上

### 当前状态
- 293 个短链域名 (全部 .xyz TLD)
- Cloudflare 节点: AMS (Amsterdam, 非US) ✅
- 活跃域名: p1600.xyz, mpupb.xyz, mpupa.xyz 等
- 均有足够剩余配额 (8K-33K)

**Why:** 5月2日凌晨发现 rawClicks=11-20 但 filtered=0-4，均CTR虚高但实际每批CTR接近0%。US爬虫点击被计入 rawClicks 但不计入 filteredClicks，造成数据错觉。

**How to apply:**
- 启动时检查域名 CF 节点位置 (load_domains)
- 优先使用欧洲/亚洲 CF 节点域名
- 避免使用被 US 安全厂商列入黑名单的 TLD
