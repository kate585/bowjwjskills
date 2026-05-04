#!/usr/bin/env python3
"""Send remaining 9 v1 campaigns. Pure sequential, 10s create→launch gap, no interleaving."""
import subprocess, json, os, sys, time, sqlite3
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

JWT = open(os.path.expanduser("~/.hermes/state/bowjwj/.jwt")).read().strip()
BASE = "https://bowjwj.cc"
BID = "c7ee7c4c-ce0a-49c9-880a-9315d07c07b6"

TICKETS = [{"ticketType": "RAFFLE", "ticketId": "2659055", "ticketQuantity": 1}]

GLOBE_CH = [
    "699847d5-83d0-4abe-9c2c-72e5381729c0", "a1e0747e-ced3-4279-8752-5c126b00d61b",
    "04596485-8dd0-4eae-930b-0ba0f60b11bb", "e062ada6-edd9-4e26-a58d-e529712a0d0f",
    "f49e287b-4d9d-407c-8bd5-81f6f2e05021", "f61e1f3f-5978-437e-a3aa-04dc1ce37904",
    "dc70d6e8-02b6-4531-b89e-6458d0509241", "8b029e9a-5cc1-44b3-92c0-4dd130d37dc2",
]
SMART_CH = [
    "05b39523-544c-4c13-ae7b-08e27cb6dc1c", "e34cb9f7-368b-4cda-aad9-acd82f4953cc",
    "c40db47c-2080-42fa-b2df-0aa9b77ad5f6", "0a30f2d0-ac30-4681-b0dc-70626e1e4109",
    "df51fa52-5336-443b-9e8c-194297cbb394", "feca8a41-5cc9-434e-be2f-757c4ddb964f",
    "165b9ca3-3220-4383-bcc2-901941ffcfd3",
]

OUTDIR = os.path.join(os.path.expanduser("~"), "Desktop", "bowjwj 发送模式更新脚本文件夹2")
DB_PATH = os.path.join(OUTDIR, "campaign_send.db")

PACKS_PER_CAMPAIGN = 10
TARGET_MIN_CLEAN = 30

# The 9 failed copies — in order: Globe first, then Smart
TASKS = [
    ("globe", "G2-balance-available-na-v1", "{$phone[10]} available na pala yung ni-check ko for you, baka gusto mo makita ${shortUrl}", 1),
    ("globe", "G3-napansin-ko-lang-v1", "{$phone[10]} uy napansin ko lang may nagbago sa profile mo ah, check mo nga ${shortUrl}", 2),
    ("globe", "G5-baka-makalimutan-v1", "{$phone[10]} reminder lang baka makalimutan mo, pwede mo na i-view anytime ${shortUrl}", 3),
    ("globe", "G6-para-sa-yo-v1", "{$phone[10]} may something na para sa yo dito, di ko na sinabi kung ano, check mo na ${shortUrl}", 4),
    ("smart", "S1b-baka-nandyan-na-v1", "{$phone[4]} baka nandyan na yung hinihintay mo, di ko sure pero check mo na ${shortUrl}", 1),
    ("smart", "S2-profile-update-v1", "{$phone[4]} update sa profile mo, may pumasok ata, tingnan mo na lang ${shortUrl}", 2),
    ("smart", "S4-friend-nudge-v1", "{$phone[4]} uy kamusta? naalala lang kita bigla, pa-check naman nito ${shortUrl}", 3),
    ("smart", "S5-time-sensitive-v1", "{$phone[4]} may window lang ito, pagkakitaan mo na habang available pa ${shortUrl}", 4),
    ("smart", "S6-convo-style-v1", "{$phone[4]} wait lang, may gusto lang ako ipakita sa yo saglit ${shortUrl}", 5),
]

def call(method, path, body=None, timeout=60):
    args = ["curl", "-s", "--max-time", str(timeout), "-X", method, f"{BASE}{path}",
            "-H", f"Authorization: Bearer {JWT}", "-H", "Content-Type: application/json"]
    if body:
        args.extend(["-d", json.dumps(body, ensure_ascii=False)])
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout+5)
    try:
        return json.loads(r.stdout)
    except:
        return {"_raw": r.stdout[:500]}

def get_domains(count=50):
    for attempt in range(5):
        data = call("GET", f"/api/domains/shortlink-options?backendInstanceId={BID}")
        items = data if isinstance(data, list) else data.get("list", [])
        domains = []
        for d in items:
            if d.get("shortlinkStatus") == "ACTIVE":
                domains.append(d["id"])
                if len(domains) >= count:
                    break
        if domains:
            return domains
        print(f"    domains retry {attempt+1}...", end=" ", flush=True)
        time.sleep(5)
    return []

def get_fresh_packs(carrier, needed=150):
    db = sqlite3.connect(DB_PATH)
    used = set(r[0] for r in db.execute("SELECT pack_id FROM pack_used").fetchall())
    db.close()

    packs = []
    for page in range(1, 80):
        if len(packs) >= needed:
            break
        data = call("GET", f"/api/phone-packs?backendInstanceId={BID}&pageSize=100&page={page}")
        if not data or not isinstance(data, dict):
            continue
        items = data.get("data", [])
        if not items:
            break
        for p in items:
            pid = p["id"]
            if pid in used:
                continue
            cn = p.get("cleanCount", 0) or 0
            if cn < TARGET_MIN_CLEAN:
                continue
            if p.get("assignmentCampaignId"):
                continue
            src = p.get("source", "") or ""
            if any(bad in src for bad in ["测试", "unknown"]):
                continue
            src_l = src.lower()
            if carrier == "globe":
                if ("globe" in src_l or "dito" in src_l) and "smart" not in src_l:
                    packs.append({"id": pid, "clean": cn, "source": src})
            else:
                if ("smart" in src_l or "tnt" in src_l) and "globe" not in src_l:
                    packs.append({"id": pid, "clean": cn, "source": src})
    return packs

def select_packs(packs, count=PACKS_PER_CAMPAIGN):
    galaxy = [p for p in packs if "银河" in p.get("source", "")]
    other = [p for p in packs if "银河" not in p.get("source", "")]
    galaxy_med = sorted([p for p in galaxy if p["clean"] <= 200], key=lambda x: x["clean"], reverse=True)
    other_med = sorted([p for p in other if p["clean"] <= 200], key=lambda x: x["clean"], reverse=True)
    selected = galaxy_med + other_med
    if len(selected) < count:
        galaxy_large = sorted([p for p in galaxy if p["clean"] > 200], key=lambda x: x["clean"])
        other_large = sorted([p for p in other if p["clean"] > 200], key=lambda x: x["clean"])
        selected += galaxy_large + other_large
    return selected[:count], sum(p["clean"] for p in selected[:count])

def get_template_id(db, carrier, suffix):
    rows = db.execute("""
        SELECT t.id FROM templates t
        LEFT JOIN campaigns c ON t.id = c.template_id AND c.launch_status = 'launched'
        WHERE t.carrier=? AND t.name LIKE ?
        ORDER BY c.id IS NULL DESC, t.created_at DESC
    """, [carrier, f"%{suffix}%"]).fetchall()
    for (tid,) in rows:
        return tid
    return None

def main():
    print("=" * 60)
    print("send_9: 纯串行发送9个剩余v1模板")
    print("=" * 60)

    db = sqlite3.connect(DB_PATH)

    # Step 0: Get domains
    print("\n=== 获取域名 ===")
    domains = get_domains(50)
    print(f"域名: {len(domains)}")

    # Step 1: Get fresh packs
    print(f"\n=== 获取号码包 ===")
    globe_packs = get_fresh_packs("globe", needed=100)
    smart_packs = get_fresh_packs("smart", needed=100)
    print(f"Globe: {len(globe_packs)} | Smart: {len(smart_packs)}")

    remaining = {"globe": list(globe_packs), "smart": list(smart_packs)}
    results = []

    for ti, (carrier, suffix, sms, ch_idx) in enumerate(TASKS):
        all_packs = remaining[carrier]
        my_packs, my_total = select_packs(all_packs, PACKS_PER_CAMPAIGN)
        if len(my_packs) < 3 or my_total < 200:
            print(f"\n[{ti+1}/9] {carrier}/{suffix} SKIP: 包不足 ({len(my_packs)}包/{my_total}条)")
            continue

        used_ids = {p["id"] for p in my_packs}
        remaining[carrier] = [p for p in all_packs if p["id"] not in used_ids]

        channel = GLOBE_CH[ch_idx % len(GLOBE_CH)] if carrier == "globe" else SMART_CH[ch_idx % len(SMART_CH)]
        tmpl_name = f"AI发送-{carrier}-{suffix}"
        tmpl_id = get_template_id(db, carrier, suffix)

        if not tmpl_id:
            print(f"\n[{ti+1}/9] {carrier}/{suffix} SKIP: no template")
            continue

        print(f"\n{'='*50}")
        print(f"[{ti+1}/9] {carrier}/{suffix}")
        print(f"  模板: {tmpl_id[:16]}...  通道: {channel[:16]}...")
        print(f"  包数: {len(my_packs)}  预估: {my_total}条")
        print(f"{'='*50}")

        # Step 2: Create campaign
        body = {
            "templateId": tmpl_id,
            "activityName": "NN33 New Jackpot",
            "ticketRewards": TICKETS,
            "backendInstanceId": BID,
            "campaignType": "activity",
            "smsText": sms,
            "shortlinkMappingMode": "recipient",
            "shortlinkMode": "domain",
            "customShortlinkDomainConfigIds": domains[:50],
            "scheduleEnabled": True,
            "smsInstanceId": channel,
            "phonePackIds": [p["id"] for p in my_packs],
        }

        print(f"  创建活动...", end=" ", flush=True)
        resp = call("POST", "/api/campaigns", body, timeout=30)

        if not resp or resp.get("error"):
            err = resp.get("error", "no resp") if resp else "no resp"
            raw = resp.get("_raw", "") if resp else ""
            print(f"ERR: {err[:150]}")
            if raw:
                print(f"  Raw: {raw[:200]}")
            results.append({"carrier": carrier, "tpl": suffix, "status": "create_failed", "pack_sent": 0})
            continue

        cid = resp.get("id", "")
        batch_id = resp.get("campaignBatchId", "")
        if not cid:
            print(f"ERR: no id. keys={list(resp.keys())[:10]}")
            results.append({"carrier": carrier, "tpl": suffix, "status": "no_id", "pack_sent": 0})
            continue

        print(f"OK {cid[:16]}...")

        # Track in DB
        for pid in [p["id"] for p in my_packs]:
            db.execute("INSERT OR IGNORE INTO pack_used (pack_id) VALUES (?)", [pid])
        db.execute("""INSERT OR REPLACE INTO campaigns (id, template_id, template_name, carrier, channel_id,
            pack_ids, pack_count, total_clean, campaign_batch_id, launch_status)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            [cid, tmpl_id, tmpl_name, carrier, channel,
             json.dumps([p["id"] for p in my_packs]), len(my_packs), my_total, batch_id, "draft"])
        db.commit()

        # Step 3: Wait for backend consistency, then launch
        print(f"  等待10s...", end=" ", flush=True)
        time.sleep(10)

        # Verify campaign exists
        for va in range(6):
            v = call("GET", f"/api/campaigns/{cid}", timeout=15)
            if v and v.get("id") == cid:
                print(f"verified", end=" ", flush=True)
                break
            print(f"v{va+1}...", end=" ", flush=True)
            time.sleep(3)

        print(f"\n  启动...", end=" ", flush=True)
        launched = False
        for attempt in range(15):
            lr = call("POST", f"/api/campaigns/{cid}/launch", body={}, timeout=15)
            if lr and not lr.get("error"):
                agent_line = lr.get("agentLineId", "")
                launch_status = lr.get("launchStatus", "?")
                print(f"OK | agentLine={agent_line[:16]}... | launch={launch_status}")
                db.execute("UPDATE campaigns SET agent_line_id=?, launch_status=? WHERE id=?",
                          [agent_line, launch_status, cid])
                db.commit()
                launched = True
                break
            err = lr.get("error", "no resp") if lr else "no resp"
            if ("资源不存在" in str(err) or "not found" in str(err).lower()) and attempt < 14:
                wait = min(5 * (attempt + 1), 40)
                print(f"等待{wait}s...", end=" ", flush=True)
                time.sleep(wait)
            else:
                print(f"ERR: {err[:100]}")
                break

        if not launched:
            results.append({"carrier": carrier, "tpl": suffix, "status": "launch_failed",
                          "total_clean": my_total, "pack_count": len(my_packs), "pack_sent": 0})
            continue

        # Step 4: Get sub-campaigns and send
        sub_campaigns = []
        for sa in range(3):
            sc_resp = call("GET", f"/api/replay-dashboard/batches/{batch_id}", timeout=30)
            packs = sc_resp.get("packs", []) if isinstance(sc_resp, dict) else []
            if packs:
                for p in packs:
                    scid = p.get("campaignId", "")
                    spid = p.get("packId", "")
                    if scid and spid:
                        sub_campaigns.append({"campaign_id": scid, "pack_id": spid})
                break
            print(f"  子活动未就绪,等3s...", end=" ", flush=True)
            time.sleep(3)

        if not sub_campaigns:
            print(f"  未找到子活动")
            results.append({"carrier": carrier, "tpl": suffix, "status": "no_subs",
                          "total_clean": my_total, "pack_count": len(my_packs), "pack_sent": 0})
            continue

        pack_sent = 0
        for pi, sc in enumerate(sub_campaigns):
            sr = call("POST", f"/api/campaigns/{sc['campaign_id']}/send",
                     {"smsInstanceId": channel}, timeout=30)
            if sr and not sr.get("error"):
                pack_sent += 1
                print(f"  包{pi+1}/{len(sub_campaigns)} OK")
            elif sr and "APPROVAL_ALREADY_PENDING" in str(sr.get("error", "")):
                pack_sent += 1
                print(f"  包{pi+1}/{len(sub_campaigns)} OK (already pending)")
            else:
                err = sr.get("error", "no resp") if sr else "no resp"
                print(f"  包{pi+1}/{len(sub_campaigns)} ERR: {str(err)[:80]}")

        results.append({"carrier": carrier, "tpl": suffix, "status": "sent",
                       "total_clean": my_total, "pack_count": len(my_packs), "pack_sent": pack_sent})

        # Short breather between campaigns
        print(f"  完成 {pack_sent}/{len(sub_campaigns)} 包, 等5s...")
        time.sleep(5)

    # Summary
    print(f"\n{'='*60}")
    print(f"结果汇总:")
    print(f"{'='*60}")
    total_sent = sum(r.get("pack_sent", 0) for r in results)
    total_vol = sum(r.get("total_clean", 0) for r in results)
    for r in results:
        ps = r.get("pack_sent", 0)
        pc = r.get("pack_count", 0)
        tc = r.get("total_clean", 0)
        print(f"  [{r['carrier']}] {r['tpl'][:40]:40s} | {r['status']:12s} | {ps}/{pc}包 | {tc}条")
    print(f"\n总计: {len(results)} 活动, {total_sent} 包已发送, {total_vol} 条")
    db.close()

if __name__ == "__main__":
    main()
