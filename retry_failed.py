#!/usr/bin/env python3
"""Retry the 9 v1 campaigns that failed with 资源不存在 in the last run.
Fixes: pure sequential, 10s create→launch gap, GET-verify before launch, 180s retry.
"""
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

# Only the 9 templates that failed — use one existing template ID per copy
FAILED_COPIES = [
    # Globe: G2, G3, G5, G6
    ("globe", "G2-balance-available-na-v1", "{$phone[10]} available na pala yung ni-check ko for you, baka gusto mo makita ${shortUrl}"),
    ("globe", "G3-napansin-ko-lang-v1", "{$phone[10]} uy napansin ko lang may nagbago sa profile mo ah, check mo nga ${shortUrl}"),
    ("globe", "G5-baka-makalimutan-v1", "{$phone[10]} reminder lang baka makalimutan mo, pwede mo na i-view anytime ${shortUrl}"),
    ("globe", "G6-para-sa-yo-v1", "{$phone[10]} may something na para sa yo dito, di ko na sinabi kung ano, check mo na ${shortUrl}"),
    # Smart: S1b, S2, S4, S5, S6
    ("smart", "S1b-baka-nandyan-na-v1", "{$phone[4]} baka nandyan na yung hinihintay mo, di ko sure pero check mo na ${shortUrl}"),
    ("smart", "S2-profile-update-v1", "{$phone[4]} update sa profile mo, may pumasok ata, tingnan mo na lang ${shortUrl}"),
    ("smart", "S4-friend-nudge-v1", "{$phone[4]} uy kamusta? naalala lang kita bigla, pa-check naman nito ${shortUrl}"),
    ("smart", "S5-time-sensitive-v1", "{$phone[4]} may window lang ito, pagkakitaan mo na habang available pa ${shortUrl}"),
    ("smart", "S6-convo-style-v1", "{$phone[4]} wait lang, may gusto lang ako ipakita sa yo saglit ${shortUrl}"),
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
        return {"_raw": r.stdout[:300]}

def get_domains(count=50):
    domains = []
    data = call("GET", f"/api/domains/shortlink-options?backendInstanceId={BID}")
    items = data if isinstance(data, list) else data.get("list", [])
    for d in items:
        if d.get("shortlinkStatus") == "ACTIVE":
            domains.append(d["id"])
            if len(domains) >= count:
                break
    return domains

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
                    packs.append({"id": pid, "clean": cn})
            else:
                if ("smart" in src_l or "tnt" in src_l) and "globe" not in src_l:
                    packs.append({"id": pid, "clean": cn})
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

def get_existing_template_id(carrier, suffix_part):
    """Get an existing v1 template ID from DB (the one without a campaign, or the newest)."""
    db = sqlite3.connect(DB_PATH)
    rows = db.execute("""
        SELECT t.id, c.id as cid FROM templates t
        LEFT JOIN campaigns c ON t.id = c.template_id
        WHERE t.carrier=? AND t.name LIKE ?
        ORDER BY c.id IS NULL DESC, t.created_at DESC
    """, [carrier, f"%{suffix_part}%"]).fetchall()
    db.close()
    # Prefer template with no campaign
    for tid, cid in rows:
        if not cid:
            return tid
    # Fallback: any template
    if rows:
        return rows[0][0]
    return None

def create_campaign(template_id, template_name, carrier, sms_text, channel, packs, domains, db):
    total_clean = sum(p["clean"] for p in packs)
    pack_ids = [p["id"] for p in packs]

    body = {
        "templateId": template_id,
        "activityName": "NN33 New Jackpot",
        "ticketRewards": TICKETS,
        "backendInstanceId": BID,
        "campaignType": "activity",
        "smsText": sms_text,
        "shortlinkMappingMode": "recipient",
        "shortlinkMode": "domain",
        "customShortlinkDomainConfigIds": domains[:50],
        "scheduleEnabled": True,
        "smsInstanceId": channel,
        "phonePackIds": pack_ids,
    }

    print(f"    创建活动: {len(pack_ids)}包/{total_clean}条...", end=" ", flush=True)
    resp = call("POST", "/api/campaigns", body, timeout=30)

    if not resp or resp.get("error"):
        err = resp.get("error", "no resp") if resp else "no resp"
        print(f"ERR: {err[:120]}")
        return None

    cid = resp.get("id", "")
    batch_id = resp.get("campaignBatchId", "")
    if not cid:
        print("ERR: no campaign id in response")
        return None

    # GET-verify campaign exists before returning
    print(f"OK cid={cid[:16]}...", end=" ", flush=True)
    for verify_attempt in range(10):
        v = call("GET", f"/api/campaigns/{cid}", timeout=15)
        if v and v.get("id") == cid:
            batch = v.get("batch", {})
            mode = batch.get("sharedAgentMode", "?")
            allocated = batch.get("allocatedLineCount", "?")
            total_phones = batch.get("totalPhoneCount", "?")
            print(f"verified | {mode} | {allocated}线 | {total_phones}条")
            break
        wait = 2 * (verify_attempt + 1)
        print(f"verify-retry{verify_attempt+1}...", end=" ", flush=True)
        time.sleep(wait)
    else:
        print(f"verify-timeout, proceeding anyway")

    db.execute("""
        INSERT OR REPLACE INTO campaigns (id, template_id, template_name, carrier, channel_id,
            pack_ids, pack_count, total_clean, campaign_batch_id, launch_status)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, [cid, template_id, template_name, carrier, channel,
          json.dumps(pack_ids), len(pack_ids), total_clean, batch_id, "draft"])

    for pid in pack_ids:
        db.execute("INSERT OR IGNORE INTO pack_used (pack_id) VALUES (?)", [pid])
    db.commit()

    return {"campaign_id": cid, "batch_id": batch_id, "pack_count": len(pack_ids), "total_clean": total_clean}

def launch_campaign(campaign_id):
    """Launch with 180s retry window."""
    for attempt in range(20):
        resp = call("POST", f"/api/campaigns/{campaign_id}/launch", body={}, timeout=15)
        if not resp or resp.get("error"):
            err = resp.get("error", "no resp") if resp else "no resp"
            if ("资源不存在" in str(err) or "not found" in str(err).lower()) and attempt < 19:
                wait = min(5 * (attempt + 1), 45)
                print(f"未就绪,等{wait}s...", end=" ", flush=True)
                time.sleep(wait)
                continue
            print(f"启动ERR: {err[:100]}")
            return None
        agent_line = resp.get("agentLineId", "")
        launch_status = resp.get("launchStatus", "?")
        print(f"启动OK | agentLine={agent_line[:16]}... | launch={launch_status}")
        return {"agent_line_id": agent_line, "launch_status": launch_status}
    return None

def get_batch_pack_campaigns(batch_id):
    resp = call("GET", f"/api/replay-dashboard/batches/{batch_id}", timeout=30)
    packs = resp.get("packs", [])
    result = []
    for p in packs:
        cid = p.get("campaignId", "")
        pid = p.get("packId", "")
        if cid and pid:
            result.append({"campaign_id": cid, "pack_id": pid})
    return result

def send_campaign(campaign_id, channel_id, db):
    body = {"smsInstanceId": channel_id}
    resp = call("POST", f"/api/campaigns/{campaign_id}/send", body, timeout=30)
    if not resp:
        return None
    err = resp.get("error", "")
    if err and "APPROVAL_ALREADY_PENDING" not in err:
        return None
    requires = resp.get("requiresApproval", False)
    approval_id = resp.get("approvalId", "")
    if requires and approval_id:
        db.execute("UPDATE campaigns SET send_approval_id=?, send_status=? WHERE id=?",
                  [approval_id, "awaiting_approval", campaign_id])
        db.commit()
        return {"approval_id": approval_id, "status": "awaiting_approval"}
    return {"status": resp.get("status", "?")}

def main():
    print("=" * 60)
    print("retry_failed: 重试9个失败的v1模板 (纯串行, 10s launch间隔)")
    print("=" * 60)

    db = sqlite3.connect(DB_PATH)
    domains = get_domains(50)
    print(f"域名: {len(domains)}")

    # Get fresh packs
    print(f"\n=== 获取号码包 ===")
    globe_packs = get_fresh_packs("globe", needed=100)
    smart_packs = get_fresh_packs("smart", needed=100)
    print(f"Globe: {len(globe_packs)} | Smart: {len(smart_packs)}")

    remaining = {"globe": list(globe_packs), "smart": list(smart_packs)}
    results = []

    gi = 0  # globe channel index
    si = 0  # smart channel index

    for ti, (carrier, suffix, sms) in enumerate(FAILED_COPIES):
        all_packs = remaining[carrier]
        my_packs, my_total = select_packs(all_packs, PACKS_PER_CAMPAIGN)
        if len(my_packs) < 3 or my_total < 200:
            print(f"\n[{ti+1}/9] {carrier}/{suffix} SKIP: 包不足 ({len(my_packs)}包/{my_total}条)")
            continue

        used_ids = {p["id"] for p in my_packs}
        remaining[carrier] = [p for p in all_packs if p["id"] not in used_ids]

        channel = GLOBE_CH[gi % len(GLOBE_CH)] if carrier == "globe" else SMART_CH[si % len(SMART_CH)]
        if carrier == "globe":
            gi += 1
        else:
            si += 1

        tmpl_name = f"AI发送-{carrier}-{suffix}"
        tmpl_id = get_existing_template_id(carrier, suffix)
        if not tmpl_id:
            print(f"\n[{ti+1}/9] {carrier}/{suffix} SKIP: no template in DB")
            continue

        print(f"\n[{ti+1}/9] {carrier}/{suffix} | ch={channel[:12]}... | {len(my_packs)}包/{my_total}条")
        print(f"    模板: {tmpl_id[:16]}...")

        # Step 1: Create campaign
        camp = create_campaign(tmpl_id, tmpl_name, carrier, sms, channel, my_packs, domains, db)
        if not camp:
            print(f"    FAILED at create, continuing to next")
            continue

        # Step 2: Wait 10s for backend consistency, then launch
        print(f"    等待10s后端就绪...", end=" ", flush=True)
        time.sleep(10)

        launch = launch_campaign(camp["campaign_id"])
        if not launch:
            print(f"    FAILED at launch, continuing to next")
            # Still track in results
            results.append({"carrier": carrier, "tpl": suffix, "status": "launch_failed",
                          "total_clean": my_total, "pack_count": len(my_packs), "pack_sent": 0})
            continue

        db.execute("UPDATE campaigns SET agent_line_id=?, launch_status=? WHERE id=?",
                  [launch.get("agent_line_id", ""), launch.get("launch_status", ""), camp["campaign_id"]])
        db.commit()

        # Step 3: Get sub-campaigns and send
        sub_campaigns = get_batch_pack_campaigns(camp["batch_id"])
        if not sub_campaigns:
            print(f"    未找到子活动列表, skip sending")
            results.append({"carrier": carrier, "tpl": suffix, "status": "no_subs",
                          "total_clean": my_total, "pack_count": len(my_packs), "pack_sent": 0})
            continue

        pack_sent = 0
        for pi, sc in enumerate(sub_campaigns):
            send_result = send_campaign(sc["campaign_id"], channel, db)
            if send_result:
                pack_sent += 1
                print(f"    包{pi+1}/{len(sub_campaigns)} OK | approval={send_result.get('approval_id','')[:16]}...")
            else:
                print(f"    包{pi+1}/{len(sub_campaigns)} ERR")

        results.append({"carrier": carrier, "tpl": suffix, "status": "sent",
                       "total_clean": my_total, "pack_count": len(my_packs), "pack_sent": pack_sent})

        # Wait 5s before next campaign (let backend breathe)
        time.sleep(5)

    # Summary
    print(f"\n{'='*60}")
    print(f"RETRY RESULTS:")
    total_sent = sum(r["pack_sent"] for r in results)
    total_vol = sum(r["total_clean"] for r in results)
    print(f"Campaigns attempted: {len(results)}")
    print(f"Packs sent: {total_sent}")
    print(f"Total volume: {total_vol}条")
    for r in results:
        print(f"  [{r['carrier']}] {r['tpl'][:40]} | {r['status']} | {r['pack_sent']}/{r['pack_count']}包 | {r['total_clean']}条")

    db.close()
    print(f"\nDB: {DB_PATH}")

if __name__ == "__main__":
    main()
