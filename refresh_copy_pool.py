#!/usr/bin/env python3
"""Every 20 min: fetch top CTR+FTD copies → AI-generate 20 Globe + 20 Smart → update copy pool."""
import subprocess, json, time, sys, re, urllib.parse
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict

JWT_FILE = Path.home() / ".hermes" / "state" / "bowjwj" / ".jwt"
BASE = "https://bowjwj.cc"
BID = "c7ee7c4c-ce0a-49c9-880a-9315d07c07b6"
AI_INSTANCE_ID = "cmn0neb160001lnd0xdlc4ty1"
CONFIG_DIR = Path.home() / ".hermes" / "state" / "bowjwj"
JWT = JWT_FILE.read_text().strip()

def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def api_get(url):
    r = subprocess.run(
        ["curl", "-sS", "-k", "--connect-timeout", "15", "--max-time", "45",
         "-H", f"Authorization: Bearer {JWT}", url],
        capture_output=True, timeout=50)
    try: return json.loads(r.stdout.decode("utf-8", errors="replace"))
    except: return {}

def api_post(url, body):
    r = subprocess.run(
        ["curl", "-sS", "-k", "--connect-timeout", "10", "--max-time", "30",
         "-H", f"Authorization: Bearer {JWT}", "-H", "Content-Type: application/json",
         "-d", json.dumps(body, ensure_ascii=False), url],
        capture_output=True, timeout=35)
    try: return json.loads(r.stdout.decode("utf-8", errors="replace"))
    except: return {}

# ── Step 1: Fetch recent batch stats from replay-dashboard list ──

def fetch_recent_batch_stats(hours=4):
    """Pull recent batches from replay-dashboard list, group by carrier.
    Returns {globe: {total_ctr, total_ftd, total_deposit, batch_count}, smart: ...}"""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    globe_batches = []
    smart_batches = []

    page = 1
    while page <= 5:  # max 5 pages * 20 = 100 batches
        data = api_get(f"{BASE}/api/replay-dashboard/batches?backendInstanceId={BID}&pageSize=20&page={page}")
        items = data.get("items", data.get("data", []))
        if isinstance(data, list): items = data
        if not items: break

        for b in items:
            name = (b.get("smsChannelName") or "").lower()
            sent_count = b.get("sentCount", 0) or b.get("successCount", 0) or 0
            if sent_count < 50: continue  # skip tiny batches

            ctr = b.get("ctr", 0) or 0
            if isinstance(ctr, (int, float)) and ctr > 1: ctr = ctr / 100.0
            ftd = b.get("ftdCount", 0) or 0
            deposit = b.get("depositAmount", 0) or 0

            entry = {"ctr": ctr, "ftd": ftd, "deposit": deposit, "sent": sent_count}

            if any(k in name for k in ["globe", "dito"]):
                globe_batches.append(entry)
            elif any(k in name for k in ["smart", "tnt"]):
                smart_batches.append(entry)

        page += 1

    def summarize(batches):
        if not batches: return {"total_ctr": 0, "total_ftd": 0, "total_deposit": 0, "batch_count": 0, "top_ctr": 0, "total_sent": 0}
        ctrs = [b["ctr"] for b in batches if b["ctr"] > 0]
        return {
            "total_ctr": sum(ctrs) / len(ctrs) if ctrs else 0,
            "total_ftd": sum(b["ftd"] for b in batches),
            "total_deposit": sum(b["deposit"] for b in batches),
            "batch_count": len(batches),
            "top_ctr": max(b["ctr"] for b in batches) if batches else 0,
            "total_sent": sum(b["sent"] for b in batches),
        }

    gs = summarize(globe_batches)
    ss = summarize(smart_batches)

    log(f"Recent batches (4h): Globe={gs['batch_count']} Smart={ss['batch_count']}")
    log(f"  Globe — avg CTR={gs['total_ctr']:.1%} FTD={gs['total_ftd']} deposit={gs['total_deposit']} topCTR={gs['top_ctr']:.1%}")
    log(f"  Smart — avg CTR={ss['total_ctr']:.1%} FTD={ss['total_ftd']} deposit={ss['total_deposit']} topCTR={ss['top_ctr']:.1%}")

    return gs, ss


# ── Step 2: AI generate copies ──

GAMBLING_BL = ["BET", "BONUS", "DEPOSIT", "CASINO", "FREE", "CLAIM", "REWARD",
               "PROMO", "SPIN", "JACKPOT", "RAFFLE", "PRIZE", "OKBET", "PBAHAY"]
REDLINE_WORDS = ["ACT NOW", "CLAIM NOW", "CLICK NOW", "DEPOSIT NOW", "SIGN UP NOW",
                 "URGENT DEPOSIT", "URGENT OFFER", "FREE SPIN", "FREE BONUS",
                 "LIMITED TIME", "LAST CHANCE", "HURRY UP", "DON'T MISS"]
LEET_PATTERNS = [r'R4FFL', r'B0NU', r'SP1N', r'D3POS', r'CL4IM', r'FR33', r'J4CKP']
TAGLISH_WORDS = ["NA", "MO", "LANG", "PA", "BA", "KA", "MAY", "CHECK NA", "PWEDE"]
IMPERATIVE = ["CLAIM NOW", "CLICK NOW", "ACT NOW", "DEPOSIT NOW",
              "SIGN UP NOW", "REGISTER NOW", "HURRY UP", "CLICK HERE", "GO NOW"]

def redline_ok(sms_text):
    upper = sms_text.upper()
    for rw in REDLINE_WORDS:
        if rw in upper: return False
    for gw in GAMBLING_BL:
        if gw in upper: return False
    for lp in LEET_PATTERNS:
        if re.search(lp, upper): return False
    if upper.count("!") > 3: return False
    return True

def score_suggestion(sms_text):
    upper = sms_text.upper()
    if not redline_ok(sms_text): return -999
    score = 50
    for tw in TAGLISH_WORDS:
        if f" {tw} " in f" {upper} " or upper.startswith(f"{tw} "): score += 20
    if re.match(r'^[A-Z]{2,}:', upper): score -= 40
    excl = upper.count("!")
    if excl > 1: score -= (excl - 1) * 15
    for imp in IMPERATIVE:
        if imp in upper: score -= 25
    non_ascii = sum(1 for c in sms_text if ord(c) > 127)
    if non_ascii > 0: score -= 50
    if len(sms_text) > 145: score -= 50
    return score

def ai_generate_copies(carrier, count=20):
    """Generate count Taglish copies via AI, return (smsText, activityName) that pass quality."""
    tone = (
        "conversational Taglish (English + Filipino mixed). "
        "HARD RULES: 1) Never start with brand name in caps + colon. "
        "2) Must include 1-2 Filipino words (na/mo/lang/pa/ba/ka) mixed into English. "
        "3) Maximum 1 exclamation mark. "
        "4) Use conversational tone (use 'pwede mo na' instead of 'Claim now'). "
        "5) NEVER use emoji or any non-ASCII characters. ASCII only. "
        "6) Maximum 145 characters total. "
        "NEVER use: bet, bonus, deposit, casino, free, claim, reward, promo, spin, jackpot, raffle, prize. "
        "Use specific PHP amounts (P1,588 to P7,888 range) to create urgency. "
        "Make it sound like a friend texting about money/account update, not an ad. "
        "End every message with ${shortUrl}."
    )

    pack_id = None
    cat_data = api_get(f"{BASE}/api/phone-packs/categories?backendInstanceId={BID}&pageSize=1")
    cats = cat_data.get("data", [])
    if cats:
        enc_key = cats[0].get("key", "")
        encoded = urllib.parse.quote(enc_key, safe="")
        pdata = api_get(f"{BASE}/api/phone-packs/categories/{encoded}/packs?backendInstanceId={BID}&page=1&pageSize=1")
        packs = pdata.get("data", [])
        if packs: pack_id = packs[0]["id"]

    if not pack_id:
        log("ERROR: No pack ID for AI generate")
        return []

    all_suggestions = []
    # API typically returns 3-5 per call, so request more batches
    batches = max(count // 3, 7)  # ~7 calls to get enough after filtering
    for b in range(batches):
        body = {
            "backendInstanceId": BID,
            "aiInstanceId": AI_INSTANCE_ID,
            "phonePackIds": [pack_id],
            "targetSiteName": "NN33",
            "activityName": "Friendly Account Update Reminder",
            "theme": "account update notification from a friend",
            "objective": "drive user to check their account via shortlink, without sounding like marketing",
            "tone": tone,
            "count": 5,
        }
        resp = api_post(f"{BASE}/api/campaign-templates/ai-generate", body)
        suggestions = resp.get("suggestions", [])
        if suggestions:
            all_suggestions.extend(suggestions)
            log(f"  AI batch {b+1}/{batches}: {len(suggestions)} suggestions")
        else:
            err = str(resp)[:150]
            log(f"  AI batch {b+1}/{batches}: 0 suggestions, resp={err}")
        time.sleep(1.5)

    # Score, filter, deduplicate
    passed = []
    seen = set()
    for s in all_suggestions:
        sms = s.get("smsText", "")
        key = sms[:60].upper().strip()
        if key in seen: continue
        seen.add(key)
        score = score_suggestion(sms)
        if score >= 60:
            passed.append((score, s))
        else:
            log(f"  REJECT (score={score}): {sms[:60]}...")

    passed.sort(key=lambda x: -x[0])
    return [p[1] for p in passed[:count]]


# ── Step 3: Create templates via API ──

def create_templates(suggestions, carrier):
    ids = []
    coupon_id = "2804039"
    for i, s in enumerate(suggestions):
        sms_text = s["smsText"]
        sms_text = "".join(c for c in sms_text if ord(c) <= 127)
        if len(sms_text) > 145: sms_text = sms_text[:145]
        ts = time.strftime("%m%d%H%M")
        body = {
            "backendInstanceId": BID,
            "name": f"ai模版自动发送-Taglish-{carrier}-{ts}-{i+1:02d}",
            "smsText": sms_text,
            "activityName": s.get("activityName", "Friendly Account Update Reminder"),
            "campaignType": "activity",
            "validityPeriod": "7D",
            "defaultSendHour": 20,
            "defaultValidityHours": 168,
            "ticketRewards": [{"ticketType": "FREE_SPIN", "ticketId": coupon_id, "ticketQuantity": 1}],
        }
        resp = api_post(f"{BASE}/api/campaign-templates", body)
        new_id = resp.get("id")
        if new_id:
            ids.append(new_id)
            log(f"  #{i+1}: {new_id}")
        else:
            log(f"  FAIL #{i+1}: {str(resp)[:120]}")
        time.sleep(0.3)
    return ids


# ── Step 4: Update all 21 config files ──

def update_config_pools(globe_ids, smart_ids):
    updated = 0
    for i in range(1, 22):
        name = f"kt{i:02d}"
        path = CONFIG_DIR / f"send_rules_{name}.json"
        if not path.exists(): continue
        with open(path) as f:
            cfg = json.load(f)
        cfg["carriers"]["globe"]["copyPoolTemplateIds"] = globe_ids
        cfg["carriers"]["globe"]["_copyPoolIndex"] = 0
        cfg["carriers"]["smart"]["copyPoolTemplateIds"] = smart_ids
        cfg["carriers"]["smart"]["_copyPoolIndex"] = 0
        # Update note
        cfg["carriers"]["globe"]["_copyPoolNote"] = f"20-copy pool refreshed {time.strftime('%m%d%H%M')}"
        cfg["carriers"]["smart"]["_copyPoolNote"] = f"20-copy pool refreshed {time.strftime('%m%d%H%M')}"
        with open(path, "w") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        updated += 1
    log(f"Updated copy pool in {updated} config files")


# ── Main ──

def main():
    log("=" * 50)
    log("=== Copy Pool Refresh ===")

    # Step 1: Check recent performance
    gs, ss = fetch_recent_batch_stats(hours=4)

    # Only refresh if there's recent activity
    total_batches = gs["batch_count"] + ss["batch_count"]
    if total_batches < 5:
        log(f"Only {total_batches} recent batches (<5), skipping refresh.")
        return

    # Step 2: AI generate 20 Globe + 20 Smart
    log("Generating 20 Globe Taglish copies...")
    globe_suggestions = ai_generate_copies("globe", count=20)
    log(f"Globe passed filter: {len(globe_suggestions)}")

    log("Generating 20 Smart Taglish copies...")
    smart_suggestions = ai_generate_copies("smart", count=20)
    log(f"Smart passed filter: {len(smart_suggestions)}")

    if len(globe_suggestions) < 6 or len(smart_suggestions) < 6:
        log(f"Not enough quality copies (Globe={len(globe_suggestions)}, Smart={len(smart_suggestions)}), keeping existing pool.")
        return

    # Step 3: Create templates
    log("Creating Globe templates...")
    new_globe_ids = create_templates(globe_suggestions, "globe")

    log("Creating Smart templates...")
    new_smart_ids = create_templates(smart_suggestions, "smart")

    if len(new_globe_ids) < 6 or len(new_smart_ids) < 6:
        log(f"Template creation partial — only updating if >=6 per carrier (Globe={len(new_globe_ids)}, Smart={len(new_smart_ids)})")
        # Fallback: merge new with old pool to maintain at least 6
        sample_cfg_path = CONFIG_DIR / "send_rules_kt01.json"
        with open(sample_cfg_path) as f:
            sample = json.load(f)
        if len(new_globe_ids) >= 6:
            pass  # good
        else:
            old_g = sample["carriers"]["globe"].get("copyPoolTemplateIds", [])
            new_globe_ids = (new_globe_ids + old_g)[:20]
            log(f"Globe pool supplemented from old: {len(new_globe_ids)} total")
        if len(new_smart_ids) >= 6:
            pass
        else:
            old_s = sample["carriers"]["smart"].get("copyPoolTemplateIds", [])
            new_smart_ids = (new_smart_ids + old_s)[:20]
            log(f"Smart pool supplemented from old: {len(new_smart_ids)} total")
        if len(new_globe_ids) < 6 or len(new_smart_ids) < 6:
            log("Still insufficient copies, skipping update.")
            return

    # Step 4: Update config files
    update_config_pools(new_globe_ids, new_smart_ids)

    log(f"=== Done: Globe={len(new_globe_ids)} Smart={len(new_smart_ids)} copies in pool ===")


if __name__ == "__main__":
    main()
