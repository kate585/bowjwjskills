#!/usr/bin/env python3
"""
Single campaign sender — 1 template, 1 channel, 10 packs, 3s interval.
Fixed: waits for batch readiness, fetches packs fresh each time.
"""
import subprocess, json, os, sys, time, sqlite3
from datetime import datetime

JWT = open(os.path.expanduser("~/.hermes/state/bowjwj/.jwt")).read().strip()
BASE = "https://bowjwj.cc"
BID = "c7ee7c4c-ce0a-49c9-880a-9315d07c07b6"
OUTDIR = os.path.join(os.path.expanduser("~"), "Desktop", "bowjwj 发送模式更新脚本文件夹2")
DB_PATH = os.path.join(OUTDIR, "campaign_send.db")

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

COPIES = {
    "globe": {
        "G1": ("G1-account-update-curiosity-v1", "{$phone[10]} may bago sa account mo ngayon, tingnan mo na lang pag may time ka ${shortUrl}"),
        "G2": ("G2-balance-available-na-v1", "{$phone[10]} available na pala yung ni-check ko for you, baka gusto mo makita ${shortUrl}"),
        "G3": ("G3-napansin-ko-lang-v1", "{$phone[10]} uy napansin ko lang may nagbago sa profile mo ah, check mo nga ${shortUrl}"),
        "G4": ("G4-quick-update-v1", "{$phone[10]} quick update lang sa account side mo, pa-check na lang pag di ka busy ${shortUrl}"),
        "G5": ("G5-baka-makalimutan-v1", "{$phone[10]} reminder lang baka makalimutan mo, pwede mo na i-view anytime ${shortUrl}"),
        "G6": ("G6-para-sa-yo-v1", "{$phone[10]} may something na para sa yo dito, di ko na sinabi kung ano, check mo na ${shortUrl}"),
    },
    "smart": {
        "S1": ("S1-account-refresh-v1", "{$phone[4]} nag-refresh yung account mo today, check mo lang kung okay na ${shortUrl}"),
        "S1b": ("S1b-baka-nandyan-na-v1", "{$phone[4]} baka nandyan na yung hinihintay mo, di ko sure pero check mo na ${shortUrl}"),
        "S2": ("S2-profile-update-v1", "{$phone[4]} update sa profile mo, may pumasok ata, tingnan mo na lang ${shortUrl}"),
        "S3": ("S3-suspense-open-v1", "{$phone[4]} alam mo ba na may nakaabang sa yo? sige na, tingnan mo na ${shortUrl}"),
        "S4": ("S4-friend-nudge-v1", "{$phone[4]} uy kamusta? naalala lang kita bigla, pa-check naman nito ${shortUrl}"),
        "S5": ("S5-time-sensitive-v1", "{$phone[4]} may window lang ito, pagkakitaan mo na habang available pa ${shortUrl}"),
        "S6": ("S6-convo-style-v1", "{$phone[4]} wait lang, may gusto lang ako ipakita sa yo saglit ${shortUrl}"),
    },
}

def call(method, path, body=None, timeout=60):
    args = ["curl", "-s", "--max-time", str(timeout), "-X", method, f"{BASE}{path}",
            "-H", f"Authorization: Bearer {JWT}", "-H", "Content-Type: application/json"]
    if body:
        args.extend(["-d", json.dumps(body, ensure_ascii=False)])
    r = subprocess.run(args, capture_output=True, text=True, timeout=timeout+5)
    try:
        return json.loads(r.stdout)
    except:
        return {"_raw": r.stdout[:300] if r.stdout else "(empty)"}

def get_domains(count=50):
    data = call("GET", f"/api/domains/shortlink-options?backendInstanceId={BID}")
    items = data if isinstance(data, list) else data.get("list", [])
    return [d["id"] for d in items if d.get("shortlinkStatus") == "ACTIVE"][:count]

def get_fresh_packs(carrier, needed=20):
    """Fetch fresh 银河0430 packs for carrier, check assignmentCampaignId on each pack"""
    db = sqlite3.connect(DB_PATH)
    used = set(r[0] for r in db.execute("SELECT pack_id FROM pack_used").fetchall())
    db.close()

    packs = []
    start_page = 22 if carrier == "globe" else 34
    for page in range(start_page, start_page + 50):
        if len(packs) >= needed:
            break
        data = call("GET", f"/api/phone-packs?backendInstanceId={BID}&pageSize=100&page={page}", timeout=90)
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
            if cn < 30:
                continue
            if p.get("assignmentCampaignId"):
                continue
            src = p.get("source", "") or ""
            if any(bad in src for bad in ["测试", "unknown"]):
                continue
            # Only pick Galaxy 0430 packs
            if "银河" not in src or "0430" not in src:
                continue
            src_l = src.lower()
            if carrier == "globe":
                if ("globe" in src_l or "dito" in src_l) and "smart" not in src_l:
                    packs.append({"id": pid, "clean": cn, "source": src})
            else:
                if ("smart" in src_l or "tnt" in src_l) and "globe" not in src_l:
                    packs.append({"id": pid, "clean": cn, "source": src})
    return packs[:needed]

def create_template(carrier, copy_key):
    suffix, sms = COPIES[carrier][copy_key]
    name = f"AI发送-{carrier}-{suffix}"
    body = {
        "name": name, "activityName": "NN33 New Jackpot", "campaignType": "activity",
        "smsText": sms,
        "ticketRewards": TICKETS,
        "backendInstanceId": BID, "defaultSendHour": 20,
        "defaultValidityHours": 168, "validityPeriod": "7D",
    }
    resp = call("POST", "/api/campaign-templates", body)
    tid = resp.get("id", "")
    if tid:
        print(f"  Template OK: {tid[:16]}... | {name}")
        return {"id": tid, "name": name, "carrier": carrier, "sms": sms}
    else:
        err = resp.get("error", "no id")
        print(f"  Template ERR: {err[:100]}")
        return None

def create_and_launch(template, channel, packs, domains):
    total_clean = sum(p["clean"] for p in packs)
    pack_ids = [p["id"] for p in packs]
    print(f"  Packs: {len(pack_ids)}, total clean: {total_clean}")
    for p in packs[:3]:
        print(f"    {p['id'][:20]}... clean={p['clean']} src={p['source'][:60]}")

    body = {
        "templateId": template["id"],
        "activityName": "NN33 New Jackpot",
        "ticketRewards": TICKETS,
        "backendInstanceId": BID,
        "campaignType": "activity",
        "smsText": template["sms"],
        "shortlinkMappingMode": "recipient",
        "shortlinkMode": "domain",
        "customShortlinkDomainConfigIds": domains[:50],
        "scheduleEnabled": True,
        "smsInstanceId": channel,
        "phonePackIds": pack_ids,
    }

    print(f"  Creating campaign...", end=" ", flush=True)
    resp = call("POST", "/api/campaigns", body, timeout=30)
    if not resp or resp.get("error"):
        err = resp.get("error", "no resp") if resp else "no resp"
        print(f"ERR: {err[:150]}")
        return None

    cid = resp.get("id", "")
    batch_id = resp.get("campaignBatchId", "")
    print(f"OK | cid={cid[:16]}... | batch={batch_id[:16] if batch_id else 'N/A'}...")

    # Wait for batch to be ready (up to 3 minutes)
    print(f"  Waiting for batch readiness...", end=" ", flush=True)
    batch_ready = False
    for attempt in range(18):
        time.sleep(10)
        resp2 = call("GET", f"/api/campaigns/{cid}", timeout=15)
        batch = resp2.get("batch", {}) if isinstance(resp2, dict) else {}
        shared_mode = batch.get("sharedAgentMode", "?")
        if shared_mode and shared_mode != "?":
            batch_ready = True
            print(f"OK ({shared_mode})")
            break
        print(f".", end="", flush=True)

    if not batch_ready:
        print(f" TIMEOUT - batch still not ready after 3min")
        return None

    # Launch
    print(f"  Launching...", end=" ", flush=True)
    launch = call("POST", f"/api/campaigns/{cid}/launch", body={}, timeout=15)
    if not launch or launch.get("error"):
        err = launch.get("error", "no resp") if launch else "no resp"
        print(f"ERR: {err[:100]}")
        return None
    print(f"OK | launchStatus={launch.get('launchStatus','?')}")

    # Get sub-campaigns
    print(f"  Getting sub-campaigns...", end=" ", flush=True)
    sub_resp = call("GET", f"/api/replay-dashboard/batches/{batch_id}", timeout=30)
    sub_campaigns = []
    for p in sub_resp.get("packs", []):
        scid = p.get("campaignId", "")
        if scid:
            sub_campaigns.append(scid)
    print(f"{len(sub_campaigns)} sub-campaigns")

    return {
        "campaign_id": cid,
        "batch_id": batch_id,
        "sub_campaigns": sub_campaigns,
        "channel": channel,
        "pack_ids": pack_ids,
        "template_name": template["name"],
        "carrier": template["carrier"],
    }

def send_sub_campaigns(campaign_data):
    """Send each sub-campaign with 3s interval"""
    sub_ids = campaign_data["sub_campaigns"]
    channel = campaign_data["channel"]
    print(f"\n  === Sending {len(sub_ids)} sub-campaigns (3s interval) ===")

    sent = 0
    approvals = []
    for i, scid in enumerate(sub_ids):
        if i > 0:
            time.sleep(3)

        body = {"smsInstanceId": channel}
        resp = call("POST", f"/api/campaigns/{scid}/send", body, timeout=30)

        if not resp:
            print(f"    [{i+1}/{len(sub_ids)}] ERR: no response")
            continue

        err = resp.get("error", "")
        if err and "APPROVAL_ALREADY_PENDING" not in err:
            print(f"    [{i+1}/{len(sub_ids)}] ERR: {err[:80]}")
            continue

        requires = resp.get("requiresApproval", False)
        approval_id = resp.get("approvalId", "")

        if requires and approval_id:
            sent += 1
            approvals.append(approval_id)
            print(f"    [{i+1}/{len(sub_ids)}] ✅ TG approval: {approval_id[:20]}...")
        else:
            status = resp.get("status", "?")
            print(f"    [{i+1}/{len(sub_ids)}] status={status}")

    print(f"\n  Sent: {sent}/{len(sub_ids)} | Approvals needed: {len(approvals)}")
    return sent

def main():
    if len(sys.argv) < 3:
        print("Usage: send_one_campaign.py <carrier> <copy_key>")
        print("  carrier: globe | smart")
        print("  copy_key: G1-G6 (globe) | S1-S6,S1b (smart)")
        sys.exit(1)

    carrier = sys.argv[1]
    copy_key = sys.argv[2]

    print("=" * 60)
    print(f"Single Campaign Send: {carrier} {copy_key}")
    print("=" * 60)

    # Step 1: Get domains
    print("\n[1/5] Getting domains...")
    domains = get_domains(50)
    print(f"  {len(domains)} active domains")

    # Step 2: Get fresh Galaxy 0430 packs
    print(f"\n[2/5] Getting fresh 银河0430 packs for {carrier}...")
    packs = get_fresh_packs(carrier, needed=10)
    if len(packs) < 3:
        print(f"  FAILED: only {len(packs)} packs found")
        sys.exit(1)
    print(f"  Found {len(packs)} packs")

    # Step 3: Create template
    print(f"\n[3/5] Creating template...")
    tpl = create_template(carrier, copy_key)
    if not tpl:
        print("  FAILED to create template")
        sys.exit(1)

    # Step 4: Create campaign + wait for batch + launch
    print(f"\n[4/5] Creating campaign + launch...")
    channels = GLOBE_CH if carrier == "globe" else SMART_CH
    channel = channels[0]  # Use first channel for simplicity
    result = create_and_launch(tpl, channel, packs[:10], domains)
    if not result:
        print("  FAILED at campaign create/launch")
        sys.exit(1)

    # Step 5: Send sub-campaigns
    print(f"\n[5/5] Sending sub-campaigns...")
    sent = send_sub_campaigns(result)

    # Track in DB
    db = sqlite3.connect(DB_PATH)
    for pid in result["pack_ids"]:
        db.execute("INSERT OR IGNORE INTO pack_used (pack_id) VALUES (?)", [pid])
    db.execute("""
        INSERT OR REPLACE INTO campaigns (id, template_id, template_name, carrier, channel_id,
            pack_ids, pack_count, total_clean, campaign_batch_id, launch_status)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, [result["campaign_id"], tpl["id"], tpl["name"], carrier, channel,
          json.dumps(result["pack_ids"]), len(result["pack_ids"]),
          sum(p["clean"] for p in packs[:10]), result["batch_id"], "launched"])
    db.commit()
    db.close()

    print(f"\n{'='*60}")
    print(f"DONE | {carrier} {copy_key} | {sent} sub-campaigns sent")
    print(f"Campaign ID: {result['campaign_id']}")
    print(f"Check TG for {sent} approval requests")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
