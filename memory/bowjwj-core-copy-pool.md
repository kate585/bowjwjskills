---
name: bowjwj-core-copy-pool
description: Iron rule — use these 14 Taglish copy templates as the core round-robin pool, with ${shortUrl} appended to each
type: feedback
originSessionId: 32761a31-141a-4fa1-be39-d6d98a7bd3c9
---
## 🔴 铁律: 核心文案池轮训发送

以下 14 条 Taglish 文案为固定轮训池，所有文案末尾追加 `${shortUrl}`，Smart 用 `{$phone[4]}`，Globe 用 `{$phone[10]}`。

**Why:** Willy 手选的高转化 Taglish 文案，经过 Round 1 验证的对话式风格（7%+ CTR 方向）。固定池避免 AI 生成质量波动。

**How to apply:** 替换 send_loop 模板选择逻辑，直接按顺序轮训这 14 条文案。每轮取下一个模板，14 条循环。不要 AI 生成，不要评分排序。

## 文案池

```
1. may P5,288 na pumasok sa account mo, check mo na bago mag-midnight ${shortUrl}
2. uy may naghihintay na P2,888 sa wallet mo, kunin mo na ngayon ${shortUrl}
3. hindi mo pa ba na-claim yung P4,588? baka bukas wala na ${shortUrl}
4. update lang: may bagong reward na P3,888 sa profile mo ${shortUrl}
5. napansin ko lang, may P6,288 ka pala dyan oh, sayang naman ${shortUrl}
6. kakapasok lang ng P2,588, refresh mo na lang pag may time ka ${shortUrl}
7. P7,288 mo waiting na lang ma-claim, 1 click na lang yan ${shortUrl}
8. limited time lang yung P3,588 sa account mo, check mo na ${shortUrl}
9. may naka-pending na P5,888 sa profile mo, baka ma-expire today ${shortUrl}
10. paalala lang: P4,188 mo available pa pero malapit na cutoff ${shortUrl}
11. P1,588 na na-credit sa account mo, wala nang hassle, check mo ${shortUrl}
12. ready na yung P3,288 mo, pwede mo na i-withdraw ngayon din ${shortUrl}
13. P6,888 bonus mo malapit na ma-expire, sayang naman kung hindi ${shortUrl}
14. nakita ko may P2,788 ka pala sa account, baka gusto mo icheck ${shortUrl}
```
