#!/usr/bin/env python3
"""Auto-send loop: deep-page packs, 9 packs/campaign, 3s interval, Globe+Smart alternating."""
import subprocess, json, os, sys, time, sqlite3, traceback, urllib.parse
from datetime import datetime, timezone, timedelta

JWT = open(os.path.expanduser("~/.hermes/state/bowjwj/.jwt")).read().strip()
BASE = "https://bowjwj.cc"
BID = "c7ee7c4c-ce0a-49c9-880a-9315d07c07b6"
TICKETS = [{"ticketType": "FREE_SPIN", "ticketId": "2804039", "ticketQuantity": 1}]  # 0503ai-auto-J: SMS Super Ace Free CouponX

# yo家通道 (GG全家网全部禁用 2026-05-02)
# Globe/Dito: 一四五十二十三  (十五 BLOCKED)
YO_G1 = "699847d5-83d0-4abe-9c2c-72e5381729c0"   # 一 LuckyPlay S
YO_G4 = "a1e0747e-ced3-4279-8752-5c126b00d61b"   # 四 LuckyPlay S
YO_G5 = "04596485-8dd0-4eae-930b-0ba0f60b11bb"   # 五 Luckyplay s
YO_G11 = "e062ada6-edd9-4e26-a58d-e529712a0d0f"  # 十一 LUCKYPLAY s
YO_G12 = "8b029e9a-5cc1-44b3-92c0-4dd130d37dc2"  # 十二 luckyplay S
YO_G13 = "f49e287b-4d9d-407c-8bd5-81f6f2e05021"  # 十三 luckyplay s
YO_G14 = "f61e1f3f-5978-437e-a3aa-04dc1ce37904"  # 十四 LUCKYPLAY S
YO_G15 = "dc70d6e8-02b6-4531-b89e-6458d0509241"  # 十五 BLOCKED

# Smart/TNT: 二六七六八九 (三 BLOCKED, 十 BLOCKED)
YO_S2 = "0a30f2d0-ac30-4681-b0dc-70626e1e4109"   # 二 VKVikingWin
YO_S6 = "df51fa52-5336-443b-9e8c-194297cbb394"   # 六 VKQuest
YO_S7 = "c40db47c-2080-42fa-b2df-0aa9b77ad5f6"   # 七 VKVikingPro
YO_S8 = "feca8a41-5cc9-434e-be2f-757c4ddb964f"   # 八 VKTechVibe
YO_S9 = "165b9ca3-3220-4383-bcc2-901941ffcfd3"   # 九 LuckyPlay S
YO_S10 = "e34cb9f7-368b-4cda-aad9-acd82f4953cc"  # 十 VKEmpireWin
YO_S3 = "05b39523-544c-4c13-ae7b-08e27cb6dc1c"   # 三 BLOCKED

# GG全家网 UUID (2026-05-04 解除永禁)
GG_AAA = "8e3d4e0e-3661-4de0-a7e5-1dc315534102"
GG_BBB = "a855d266-0066-44af-93e8-478ec2279cd4"

GLOBE_CH = [YO_G1, YO_G4, YO_G5, YO_G11, YO_G12, YO_G13, YO_G14, YO_G15, GG_AAA, GG_BBB]   # 10通道
SMART_CH = [YO_S2, YO_S6, YO_S7, YO_S8, YO_S9, YO_S10, YO_S3, GG_AAA, GG_BBB]             # 9通道

# CTR=0% auto channel switch: blocked channels with recovery timestamp
BLOCKED_CH = {}  # {channel_id: unblock_after_timestamp}

# 永久禁用的通道: (全部解除 2026-05-04)
PERMA_BLOCKED = set()

CH_LABEL = {
    YO_G1: "yo-G1", YO_G4: "yo-G4", YO_G5: "yo-G5",
    YO_G11: "yo-G11", YO_G12: "yo-G12", YO_G13: "yo-G13", YO_G14: "yo-G14",
    YO_G15: "yo-G15",
    YO_S2: "yo-S2", YO_S3: "yo-S3", YO_S6: "yo-S6", YO_S7: "yo-S7",
    YO_S8: "yo-S8", YO_S9: "yo-S9", YO_S10: "yo-S10",
    GG_AAA: "GG-AAA", GG_BBB: "GG-BBB",
}

def get_active_channel(carrier, idx):
    """Return (channel_id, idx) skipping blocked + perma-blocked channels. Returns None if all blocked."""
    pool = GLOBE_CH if carrier == "globe" else SMART_CH
    now = time.time()
    # Expire old blocks
    for ch in list(BLOCKED_CH.keys()):
        if BLOCKED_CH[ch] < now:
            print(f"  [CH_UNBLOCK:{CH_LABEL.get(ch, ch[:8])}]", end=" ", flush=True)
            del BLOCKED_CH[ch]
    # Try each channel starting from idx, skip perma-blocked
    for offset in range(len(pool)):
        ch = pool[(idx + offset) % len(pool)]
        if ch not in BLOCKED_CH and ch not in PERMA_BLOCKED:
            return ch, (idx + offset) % len(pool)
    # All blocked — unblock oldest and reuse (但永不解禁 perma-blocked)
    candidates = [(k, v) for k, v in BLOCKED_CH.items() if k not in PERMA_BLOCKED]
    if candidates:
        oldest = min(candidates, key=lambda x: x[1])
        print(f"  [ALL_BLOCKED force unblock:{CH_LABEL.get(oldest[0], oldest[0][:8])}]", end=" ", flush=True)
        del BLOCKED_CH[oldest[0]]
        return oldest[0], idx
    print(f"  [NO_ACTIVE_CH:all 15 perma-blocked or blocked]", end=" ", flush=True)
    return pool[idx % len(pool)], idx  # fallback

def block_channel(channel, hours=24):
    """Block a channel for N hours after CTR=0% or failure."""
    unblock_at = time.time() + hours * 3600
    BLOCKED_CH[channel] = unblock_at
    label = CH_LABEL.get(channel, channel[:8])
    print(f"  [BLOCKED:{label} for {hours}h]", end=" ", flush=True)

DB_PATH = os.path.join(os.path.expanduser("~"), "Desktop", "bowjwj 发送模式更新脚本文件夹2", "campaign_send.db")

# 铁律: 只用最近3天转化充值最高的文案 (2026-05-03 Willy拍板)
# 当前最佳: W1 = "may P5,288 na pumasok sa account mo..." (221FTD/229617deposit, 5.8x领先第2名)
TEMPLATE_ID = "7eb6db84-6df3-432e-91df-57bea5aa55d1"  # 0503ai-auto-J (继承RAFFLE票卷)
W1_COPY = "may P5,288 na pumasok sa account mo, check mo na bago mag-midnight ${shortUrl}"

# Globe={$phone[10]} Smart={$phone[4]}, 单文案W1
GLOBE_TPL = [
    (TEMPLATE_ID, "W1", f"{'{$phone[10]}'} {W1_COPY}"),
]
SMART_TPL = [
    (TEMPLATE_ID, "W1", f"{'{$phone[4]}'} {W1_COPY}"),
]

def call(method, path, body=None, timeout=60):
    args = ["curl", "-s", "--max-time", str(timeout), "-X", method, f"{BASE}{path}",
            "-H", f"Authorization: Bearer {JWT}", "-H", "Content-Type: application/json"]
    if body: args.extend(["-d", json.dumps(body, ensure_ascii=False)])
    try:
        r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout+5)
        try: return json.loads(r.stdout)
        except: return {"_raw": r.stdout[:500]}
    except Exception as e:
        return {"error": str(e), "_raw": "call exception"}

domains_cache = None

# Fallback domain IDs (captured from API when server is healthy, 2026-05-01)
FALLBACK_DOMAINS = [
    "5977cef9-2338-4d6e-bd7b-52dbe88da157", "ba42b216-1957-440d-865b-6c31ffa4242b",
    "3bd52f46-1afd-4ca7-9c1e-7959c2ca2221", "cac533a4-42ba-4aea-ad64-42723580ee84",
    "ceccee9c-b90c-4abc-982f-465e61ce3710", "0bac5226-2750-4195-a977-ee7d3baadd17",
    "a6a52352-5919-4f64-a415-1538cd5841b1", "e5150009-05c0-4938-8362-f0727c76a4d9",
    "07b49b8e-7a60-457a-ad8c-a5f8e8db131e", "118c5558-2bf0-4ea1-9007-5cde36c209ff",
]

def wait_for_job(job_id, interval=5, timeout=120):
    """Poll job status until completed or failed. Returns (campaign_id, batch_id) or (None, None)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        jr = call("GET", f"/api/jobs/{job_id}", timeout=10)
        if jr and jr.get("status") == "completed":
            result = jr.get("result", {})
            return result.get("id", ""), result.get("campaignBatchId", "")
        elif jr and jr.get("status") == "failed":
            print(f"JOB_FAIL:{jr.get('error','')[:60]}")
            return None, None
        time.sleep(interval)
    return None, None

def get_domains():
    global domains_cache
    if domains_cache: return domains_cache
    for _ in range(2):
        data = call("GET", f"/api/domains/shortlink-options?backendInstanceId={BID}", timeout=12)
        items = data if isinstance(data, list) else data.get("list", [])
        domains = [d["id"] for d in items if d.get("shortlinkStatus") == "ACTIVE"]
        if domains:
            domains_cache = domains[:50]
            return domains_cache
        time.sleep(3)
    # API failed — use fallback
    print(f"  [FALLBACK_DOMAINS]", end=" ", flush=True)
    domains_cache = list(FALLBACK_DOMAINS)
    return domains_cache

PACK_PAGES = [31, 32, 33, 34, 35]  # IRON: kt07固定第31-35页，铁律不可修改 (2026-05-03 Willy)
PACK_PAGE_SIZE = 20

def fetch_packs(carrier, db, count=30):
    """IRON RULE: kt07固定page=31-35, q=凯特ai发送. 0包刷新最多3次, 冷却[5,10,15]=30s总量."""
    used = set(r[0] for r in db.execute("SELECT pack_id FROM pack_used").fetchall())
    packs = []
    Q = urllib.parse.quote("凯特ai发送")
    MAX_RETRIES = 3  # 铁律: 最多重试3次, 冷却[5,10,15]=30s总量
    WAIT = [5, 10, 15]

    for pi, page in enumerate(PACK_PAGES):
        if len(packs) >= count * 2:
            break
        for refresh in range(1 + MAX_RETRIES):  # 1 initial + 3 retries
            if refresh > 0:
                w = WAIT[refresh - 1]
                print(f"┄ p{page}{w}s冷却{refresh}/{MAX_RETRIES}...", end=" ", flush=True)
                time.sleep(w)
                used = set(r[0] for r in db.execute("SELECT pack_id FROM pack_used").fetchall())
            data = call("GET", f"/api/phone-packs?backendInstanceId={BID}&pageSize={PACK_PAGE_SIZE}&page={page}&q={Q}", timeout=10)
            if not data or not isinstance(data, dict): break
            items = data.get("data", [])
            if not items and refresh < MAX_RETRIES:
                continue
            if not items:
                break
            contaminated = fresh = 0
            for p in items:
                pid = p["id"]
                if pid in used or p.get("assignmentCampaignId"):
                    contaminated += 1; continue
                cn = p.get("cleanCount", 0) or 0
                if cn < 30: continue
                src_l = p.get("source", "").lower()
                if carrier == "globe":
                    if ("globe" in src_l or "dito" in src_l) and "smart" not in src_l:
                        packs.append({"id": pid, "clean": cn, "source": p.get("source", "")})
                        fresh += 1
                else:
                    if ("smart" in src_l or "tnt" in src_l) and "globe" not in src_l:
                        packs.append({"id": pid, "clean": cn, "source": p.get("source", "")})
                        fresh += 1
            if fresh == 0 and refresh < MAX_RETRIES:
                continue  # 0包 → 冷却重试
            break  # 有包或重试耗尽 → 下一页

    return packs

def select_9(packs):
    # All packs are 银河数据 0501 — prefer clean≤200 for efficient send, then larger packs as fallback
    small = sorted([p for p in packs if p["clean"]<=200], key=lambda x: x["clean"], reverse=True)
    large = sorted([p for p in packs if p["clean"]>200], key=lambda x: x["clean"])
    sel = small + large
    return sel[:9]

def send_one(carrier, tmpl_id, tpl_name, sms, channel, db, domains):
    try:
        return _send_one(carrier, tmpl_id, tpl_name, sms, channel, db, domains)
    except Exception as e:
        print(f" ERR:{e}", flush=True)
        return None

def _send_one(carrier, tmpl_id, tpl_name, sms, channel, db, domains):
    packs = fetch_packs(carrier, db, 30)
    my_packs = select_9(packs)
    if len(my_packs) < 5:
        print(f"  SKIP: only {len(my_packs)} packs")
        return "empty_page"
    my_total = sum(p["clean"] for p in my_packs)
    print(f"  {len(my_packs)}包/{my_total}条", end=" ", flush=True)

    planned_at = (datetime.now(timezone.utc) + timedelta(seconds=30)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    body = {
        "templateId": tmpl_id, "activityName": "0503ai-auto-J",
        "ticketRewards": TICKETS, "backendInstanceId": BID, "campaignType": "activity",
        "smsText": sms, "shortlinkMappingMode": "recipient", "shortlinkMode": "domain",
        "customShortlinkDomainConfigIds": domains,
        "scheduleEnabled": True, "smsInstanceId": channel,
        "phonePackIds": [p["id"] for p in my_packs],
        "plannedAt": planned_at,
    }

    resp = call("POST", "/api/campaigns", body, timeout=30)
    if not resp or resp.get("error"):
        err = resp.get("error", "no resp") if resp else "no resp"
        if "已分配给计划" in str(err):
            print(f"RACE", end=" ", flush=True)
            for p in my_packs:
                db.execute("INSERT OR IGNORE INTO pack_used (pack_id) VALUES (?)", [p["id"]])
            db.commit()
            return "race"
        if "固定文案" in str(err):
            print(f"BAD_DOMAIN", end=" ", flush=True)
            global domains_cache
            domains_cache = None
            return "bad_domain"
        print(f"CREAT_ERR:{str(err)[:80]}")
        return None

    # Async flow: POST returns {jobId} or {id}, poll job if needed
    cid = resp.get("id", "")
    job_id = resp.get("jobId", "")
    batch_id = resp.get("campaignBatchId", "")
    if not cid and job_id:
        cid, batch_id = wait_for_job(job_id)
    if not cid:
        print(f"NO_ID")
        return None

    for p in my_packs:
        db.execute("INSERT OR IGNORE INTO pack_used (pack_id) VALUES (?)", [p["id"]])
    db.execute("""INSERT OR REPLACE INTO campaigns (id,template_id,template_name,carrier,channel_id,
        pack_ids,pack_count,total_clean,campaign_batch_id,launch_status)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
        [cid, tmpl_id, f"AI发送-{carrier}-{tpl_name}", carrier, channel,
         json.dumps([p["id"] for p in my_packs]), len(my_packs), my_total, batch_id, "draft"])
    db.commit()

    time.sleep(10)
    for va in range(6):
        v = call("GET", f"/api/campaigns/{cid}", timeout=15)
        if v and v.get("id") == cid: break
        time.sleep(3)

    launched = False
    for attempt in range(20):
        lr = call("POST", f"/api/campaigns/{cid}/launch", body={}, timeout=15)
        if lr and not lr.get("error"):
            al = lr.get("agentLineId", "")
            launch_job_id = lr.get("jobId", "")
            if not al and launch_job_id:
                # Launch is async — poll the job
                for _ in range(12):
                    time.sleep(2)
                    jr = call("GET", f"/api/jobs/{launch_job_id}", timeout=10)
                    if jr and jr.get("status") == "completed":
                        result = jr.get("result", {}) if isinstance(jr.get("result"), dict) else {}
                        result_json_str = jr.get("resultJson", "")
                        if not result and result_json_str:
                            try: result = json.loads(result_json_str)
                            except: pass
                        al = result.get("agentLineId", "")
                        break
                    elif jr and jr.get("status") == "failed":
                        break
            if al:
                db.execute("UPDATE campaigns SET agent_line_id=?, launch_status=? WHERE id=?", [al, lr.get("launchStatus","?"), cid])
                db.commit()
                launched = True
                break
            time.sleep(5)
            continue
        err = lr.get("error", "no resp") if lr else "no resp"
        if ("资源不存在" in str(err) or "not found" in str(err).lower()) and attempt < 19:
            time.sleep(min(5 * (attempt + 1), 40))
        else:
            break
    if not launched:
        # Fallback: check if campaign actually launched despite our confusion
        v = call("GET", f"/api/campaigns/{cid}", timeout=15)
        if v and v.get("agentLineId"):
            al = v.get("agentLineId", "")
            db.execute("UPDATE campaigns SET agent_line_id=?, launch_status=? WHERE id=?", [al, v.get("launchStatus","?"), cid])
            db.commit()
            launched = True
    if not launched:
        print("LAUNCH_FAIL")
        return None

    sub_campaigns = []
    for sa in range(5):
        sc = call("GET", f"/api/replay-dashboard/batches/{batch_id}", timeout=30)
        packs_data = sc.get("packs", []) if isinstance(sc, dict) else []
        for pp in packs_data:
            scid = pp.get("campaignId", ""); spid = pp.get("packId", "")
            if scid and spid: sub_campaigns.append({"campaign_id": scid, "pack_id": spid})
        if sub_campaigns: break
        time.sleep(5)

    if not sub_campaigns: return None

    sent = 0
    for pi, sc in enumerate(sub_campaigns):
        if pi > 0:
            time.sleep(3)  # 3s interval between packs
        sr = call("POST", f"/api/campaigns/{sc['campaign_id']}/send", {"smsInstanceId": channel}, timeout=30)
        if sr and (not sr.get("error") or "APPROVAL_ALREADY_PENDING" in str(sr.get("error",""))):
            sent += 1
            print(".", end="", flush=True)
        elif sr and "当前计划不可启动" in str(sr.get("error","")):
            print("_", end="", flush=True)
        else:
            print("x", end="", flush=True)

    print(f" {sent}/{len(sub_campaigns)}", flush=True)
    return {"carrier": carrier, "tpl": tpl_name, "sent": sent, "total": len(sub_campaigns), "batch": batch_id}

def main():
    print("=" * 50)
    print("auto_send: 深页取包 | 9包/活动 | 3秒间隔 | Globe<>Smart交替")
    print("=" * 50)
    db = sqlite3.connect(DB_PATH)
    domains = get_domains()
    print(f"域名: {len(domains)}")
    print()

    gi = si = 0
    round_num = 0
    consecutive_race = 0
    consecutive_fail = {"globe": 0, "smart": 0}  # per-carrier fail counter for channel switch

    while True:
        round_num += 1
        # Alternate Globe/Smart with carrier-specific templates
        if round_num % 2 == 1:
            ci = gi % len(GLOBE_TPL)
            tmpl_id, tpl_name, sms = GLOBE_TPL[ci]
            carrier = "globe"
            channel, actual_ch_idx = get_active_channel(carrier, gi % len(GLOBE_CH))
            gi += 1
        else:
            ci = si % len(SMART_TPL)
            tmpl_id, tpl_name, sms = SMART_TPL[ci]
            carrier = "smart"
            channel, actual_ch_idx = get_active_channel(carrier, si % len(SMART_CH))
            si += 1

        ch_label = CH_LABEL.get(channel, channel[:8])
        print(f"[R{round_num}] {carrier}/{tpl_name}/{ch_label}", end="", flush=True)

        # Retry loop: on NO_ID/LAUNCH_FAIL, auto-switch channel and retry (max 2 retries)
        for retry in range(3):
            try:
                result = send_one(carrier, tmpl_id, tpl_name, sms, channel, db, domains)
            except Exception as e:
                print(f" EXC:{e}", flush=True)
                traceback.print_exc(file=sys.stdout)
                result = None

            if result == "race":
                consecutive_race += 1
                consecutive_fail[carrier] = 0
                if consecutive_race >= 3:
                    print("  (3 consecutive races, refresh+wait 30s)", end=" ", flush=True)
                    time.sleep(30)
                    consecutive_race = 0
                    continue  # 铁律: 刷新当前页, 不跳轮不抢包
                else:
                    print(f"  [REFRESH:{retry+1}]", end="", flush=True)
                    time.sleep(3)
                    continue  # refresh current page, re-fetch fresh packs, same channel

            if result == "bad_domain":
                # Domain issue, not channel issue — refresh domains and retry same channel
                print(f"  [DOMAIN_RETRY:{retry+1}]", end="", flush=True)
                domains = get_domains()
                time.sleep(2)
                continue

            if result == "empty_page":
                # Page has no packs after 3 refreshes — 30s cooldown, don't block channel
                print(f"  [COOLDOWN:30s page empty]", end=" ", flush=True)
                time.sleep(30)
                break

            if result is None:
                # FAIL: NO_ID / LAUNCH_FAIL / CREAT_ERR → auto switch channel
                consecutive_fail[carrier] += 1
                if retry < 2:
                    block_channel(channel, hours=1)  # block 1h for immediate fail
                    channel, _ = get_active_channel(carrier, ci % len(GLOBE_CH if carrier == "globe" else SMART_CH))
                    ch_label = CH_LABEL.get(channel, channel[:8])
                    print(f"  [RETRY:{retry+1} → {ch_label}]", end="", flush=True)
                    time.sleep(2)
                    continue
                else:
                    consecutive_race = 0
                    time.sleep(5)
                    break

            # Success
            if not isinstance(result, dict):
                print(f" BAD_RESULT:{type(result).__name__}", end="", flush=True)
                break
            consecutive_race = 0
            consecutive_fail[carrier] = 0
            sent_ratio = result["sent"] / max(result["total"], 1)
            if sent_ratio < 0.5:
                # Low send rate — likely channel issue, block 24h
                print(f"  [LOW_SEND:{result['sent']}/{result['total']}]", end=" ", flush=True)
                block_channel(channel, hours=24)
            time.sleep(3)
            break

if __name__ == "__main__":
    main()
