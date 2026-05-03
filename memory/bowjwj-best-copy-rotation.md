---
name: bowjwj-best-copy-rotation
description: Iron rule: 14 Willy hand-picked Taglish copies per carrier, round-robin with ${shortUrl}, stored in willy_copies.json + rotation state persisted
type: feedback
originSessionId: 8b053a7b-dcf0-46ea-b268-f0c30158d2dd
---
Iron rule: ONLY use Willy's 14 hand-picked Taglish copies for SMS sending, round-robin rotation, with `${shortUrl}` appended. No other copies/templates allowed.

**Why:** Willy hand-picked these 14 copies as the best-performing Taglish variants (dialogue-style + urgency + specific amounts). Previous AI-generated templates led to unpredictable CTRs. Each carrier (Globe/Smart) has its own independent 14-template pool with separate rotation state.

**How to apply:**
- `~/.hermes/state/bowjwj/willy_copies.json` — 14 template IDs per carrier ("globe" and "smart" keys, lowercase)
- `~/.hermes/state/bowjwj/willy_rotation_state.json` — persistent rotation index per carrier
- `fast_send.py` `get_willy_copy(carrier)` reads willy_copies.json, advances rotation, persists state
- `fetch_prereq` calls `get_willy_copy()` as highest priority (before forceTemplateId fallback)
- All copies end with `${shortUrl}` variable
- send_rules.json `forceTemplateId` set to "" for both carriers
- Never use AI-generated or other templates unless Willy explicitly overrides

14 copies (same for both carriers, separate template IDs):
1. may P5,288 na pumasok sa account mo, check mo na bago mag-midnight
2. uy may naghihintay na P2,888 sa wallet mo, kunin mo na ngayon
3. hindi mo pa ba na-claim yung P4,588? baka bukas wala na
4. update lang: may bagong reward na P3,888 sa profile mo
5. napansin ko lang, may P6,288 ka pala dyan oh, sayang naman
6. kakapasok lang ng P2,588, refresh mo na lang pag may time ka
7. P7,288 mo waiting na lang ma-claim, 1 click na lang yan
8. limited time lang yung P3,588 sa account mo, check mo na
9. may naka-pending na P5,888 sa profile mo, baka ma-expire today
10. paalala lang: P4,188 mo available pa pero malapit na cutoff
11. P1,588 na na-credit sa account mo, wala nang hassle, check mo
12. ready na yung P3,288 mo, pwede mo na i-withdraw ngayon din
13. P6,888 bonus mo malapit na ma-expire, sayang naman kung hindi
14. nakita ko may P2,788 ka pala sa account, baka gusto mo icheck
