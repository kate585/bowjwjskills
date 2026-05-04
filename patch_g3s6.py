#!/usr/bin/env python3
"""Quick retry G3 and S6 with 9 packs."""
import subprocess, json, os, sys, time, sqlite3

JWT = open(os.path.expanduser("~/.hermes/state/bowjwj/.jwt")).read().strip()
BASE = "https://bowjwj.cc"
BID = "c7ee7c4c-ce0a-49c9-880a-9315d07c07b6"
TICKETS = [{"ticketType": "RAFFLE", "ticketId": "2659055", "ticketQuantity": 1}]
GLOBE_CH = ["699847d5-83d0-4abe-9c2c-72e5381729c0","a1e0747e-ced3-4279-8752-5c126b00d61b","04596485-8dd0-4eae-930b-0ba0f60b11bb","e062ada6-edd9-4e26-a58d-e529712a0d0f","f49e287b-4d9d-407c-8bd5-81f6f2e05021","f61e1f3f-5978-437e-a3aa-04dc1ce37904","dc70d6e8-02b6-4531-b89e-6458d0509241","8b029e9a-5cc1-44b3-92c0-4dd130d37dc2"]
SMART_CH = ["05b39523-544c-4c13-ae7b-08e27cb6dc1c","e34cb9f7-368b-4cda-aad9-acd82f4953cc","c40db47c-2080-42fa-b2df-0aa9b77ad5f6","0a30f2d0-ac30-4681-b0dc-70626e1e4109","df51fa52-5336-443b-9e8c-194297cbb394","feca8a41-5cc9-434e-be2f-757c4ddb964f","165b9ca3-3220-4383-bcc2-901941ffcfd3"]

DB_PATH = os.path.join(os.path.expanduser("~"), "Desktop", "bowjwj 发送模式更新脚本文件夹2", "campaign_send.db")

TASKS = [
    ("globe", "G3-napansin-ko-lang-v1", "{$phone[10]} uy napansin ko lang may nagbago sa profile mo ah, check mo nga ${shortUrl}", 2),
    ("smart", "S6-convo-style-v1", "{$phone[4]} wait lang, may gusto lang ako ipakita sa yo saglit ${shortUrl}", 5),
]

def call(method, path, body=None, timeout=60):
    args = ["curl", "-s", "--max-time", str(timeout), "-X", method, f"{BASE}{path}",
            "-H", f"Authorization: Bearer {JWT}", "-H", "Content-Type: application/json"]
    if body: args.extend(["-d", json.dumps(body, ensure_ascii=False)])
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout+5)
    try: return json.loads(r.stdout)
    except: return {"_raw": r.stdout[:500]}

def get_domains():
    for _ in range(5):
        data = call("GET", f"/api/domains/shortlink-options?backendInstanceId={BID}")
        items = data if isinstance(data, list) else data.get("list", [])
        domains = [d["id"] for d in items if d.get("shortlinkStatus") == "ACTIVE"]
        if domains: return domains[:50]
        time.sleep(5)
    return []

def fetch_packs_now(carrier, db):
    used = set(r[0] for r in db.execute("SELECT pack_id FROM pack_used").fetchall())
    packs = []
    for page in range(1, 30):
        if len(packs) >= 30: break
        data = call("GET", f"/api/phone-packs?backendInstanceId={BID}&pageSize=100&page={page}")
        if not data or not isinstance(data, dict): continue
        items = data.get("data", [])
        if not items: break
        for p in items:
            pid = p["id"]
            if pid in used: continue
            cn = p.get("cleanCount", 0) or 0
            if cn < 30: continue
            if p.get("assignmentCampaignId"): continue
            src = (p.get("source", "") or "").lower()
            if any(bad in src for bad in ["测试", "unknown"]): continue
            if carrier == "globe":
                if ("globe" in src or "dito" in src) and "smart" not in src:
                    packs.append({"id": pid, "clean": cn, "source": p.get("source","")})
            else:
                if ("smart" in src or "tnt" in src) and "globe" not in src:
                    packs.append({"id": pid, "clean": cn, "source": p.get("source","")})
    return packs

def select_9(packs):
    galaxy = sorted([p for p in packs if "银河" in p["source"] and p["clean"]<=200], key=lambda x: x["clean"], reverse=True)
    other = sorted([p for p in packs if "银河" not in p["source"] and p["clean"]<=200], key=lambda x: x["clean"], reverse=True)
    sel = galaxy + other
    if len(sel) < 9:
        sel += sorted([p for p in packs if "银河" in p["source"] and p["clean"]>200], key=lambda x: x["clean"])
        sel += sorted([p for p in packs if "银河" not in p["source"] and p["clean"]>200], key=lambda x: x["clean"])
    return sel[:9]

def get_template_id(db, carrier, suffix):
    rows = db.execute("""SELECT t.id FROM templates t LEFT JOIN campaigns c ON t.id=c.template_id AND c.launch_status='launched'
        WHERE t.carrier=? AND t.name LIKE ? ORDER BY c.id IS NULL DESC, t.created_at DESC""", [carrier, f"%{suffix}%"]).fetchall()
    for (tid,) in rows: return tid
    return None

def main():
    print("=" * 50)
    print("补发 G3 + S6 (9包/活动)")
    print("=" * 50)
    db = sqlite3.connect(DB_PATH)
    domains = get_domains()
    print(f"域名: {len(domains)}")

    for ti, (carrier, suffix, sms, ch_idx) in enumerate(TASKS):
        channel = GLOBE_CH[ch_idx % len(GLOBE_CH)] if carrier == "globe" else SMART_CH[ch_idx % len(SMART_CH)]
        tmpl_name = f"AI发送-{carrier}-{suffix}"
        tmpl_id = get_template_id(db, carrier, suffix)

        print(f"\n{'='*50}")
        print(f"[{ti+1}/2] {carrier}/{suffix}")
        print(f"  模板: {tmpl_id[:16]}...  通道: {channel[:16]}...")
        print(f"  取包中...", end=" ", flush=True)

        all_packs = fetch_packs_now(carrier, db)
        my_packs = select_9(all_packs)
        if len(my_packs) < 5:
            print(f"SKIP: only {len(my_packs)} packs")
            continue
        my_total = sum(p["clean"] for p in my_packs)
        print(f"OK {len(my_packs)}包/{my_total}条")

        body = {
            "templateId": tmpl_id, "activityName": "NN33 New Jackpot",
            "ticketRewards": TICKETS, "backendInstanceId": BID, "campaignType": "activity",
            "smsText": sms, "shortlinkMappingMode": "recipient", "shortlinkMode": "domain",
            "customShortlinkDomainConfigIds": domains,
            "scheduleEnabled": True, "smsInstanceId": channel,
            "phonePackIds": [p["id"] for p in my_packs],
        }

        print(f"  创建...", end=" ", flush=True)
        resp = call("POST", "/api/campaigns", body, timeout=30)
        if not resp or resp.get("error"):
            err = resp.get("error", "no resp") if resp else "no resp"
            print(f"ERR: {err[:150]}")
            if resp and resp.get("_raw"): print(f"  raw: {resp['_raw'][:200]}")
            for p in my_packs:
                db.execute("INSERT OR IGNORE INTO pack_used (pack_id) VALUES (?)", [p["id"]])
            db.commit()
            continue

        cid = resp.get("id", "")
        batch_id = resp.get("campaignBatchId", "")
        if not cid:
            print(f"ERR: no id. keys={list(resp.keys())[:10]}")
            continue

        print(f"OK {cid[:16]}...")

        for p in my_packs:
            db.execute("INSERT OR IGNORE INTO pack_used (pack_id) VALUES (?)", [p["id"]])
        db.execute("""INSERT OR REPLACE INTO campaigns (id,template_id,template_name,carrier,channel_id,
            pack_ids,pack_count,total_clean,campaign_batch_id,launch_status)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            [cid, tmpl_id, tmpl_name, carrier, channel,
             json.dumps([p["id"] for p in my_packs]), len(my_packs), my_total, batch_id, "draft"])
        db.commit()

        print(f"  等10s...", end=" ", flush=True)
        time.sleep(10)
        for va in range(6):
            v = call("GET", f"/api/campaigns/{cid}", timeout=15)
            if v and v.get("id") == cid:
                print("verified", end=" ", flush=True)
                break
            print(f"v{va+1}...", end=" ", flush=True)
            time.sleep(3)

        print(f"\n  启动...", end=" ", flush=True)
        launched = False
        for attempt in range(15):
            lr = call("POST", f"/api/campaigns/{cid}/launch", body={}, timeout=15)
            if lr and not lr.get("error"):
                al = lr.get("agentLineId", "")
                ls = lr.get("launchStatus", "?")
                print(f"OK | {al[:16]}... | {ls}")
                db.execute("UPDATE campaigns SET agent_line_id=?, launch_status=? WHERE id=?", [al, ls, cid])
                db.commit()
                launched = True
                break
            err = lr.get("error", "no resp") if lr else "no resp"
            if ("资源不存在" in str(err) or "not found" in str(err).lower()) and attempt < 14:
                wait = min(5 * (attempt + 1), 40)
                print(f"等{wait}s...", end=" ", flush=True)
                time.sleep(wait)
            else:
                print(f"ERR: {err[:100]}")
                break

        if not launched:
            print(f"  FAILED at launch")
            continue

        sub_campaigns = []
        for sa in range(3):
            sc = call("GET", f"/api/replay-dashboard/batches/{batch_id}", timeout=30)
            packs = sc.get("packs", []) if isinstance(sc, dict) else []
            for p in packs:
                scid = p.get("campaignId", ""); spid = p.get("packId", "")
                if scid and spid: sub_campaigns.append({"campaign_id": scid, "pack_id": spid})
            if sub_campaigns: break
            print(f"  子活动未就绪...", end=" ", flush=True)
            time.sleep(3)

        if not sub_campaigns:
            print("未找到子活动")
            continue

        pack_sent = 0
        for pi, sc in enumerate(sub_campaigns):
            sr = call("POST", f"/api/campaigns/{sc['campaign_id']}/send", {"smsInstanceId": channel}, timeout=30)
            if sr and not sr.get("error"):
                pack_sent += 1
                print(f"  包{pi+1}/{len(sub_campaigns)} OK")
            elif sr and "APPROVAL_ALREADY_PENDING" in str(sr.get("error", "")):
                pack_sent += 1
                print(f"  包{pi+1}/{len(sub_campaigns)} OK(pending)")
            elif sr and "当前计划不可启动" in str(sr.get("error", "")):
                print(f"  包{pi+1}/{len(sub_campaigns)} SKIP")
            else:
                err = sr.get("error", "no resp") if sr else "no resp"
                print(f"  包{pi+1}/{len(sub_campaigns)} ERR: {str(err)[:80]}")

        print(f"  完成 {pack_sent}/{len(sub_campaigns)} 包")
        time.sleep(3)

    print(f"\nDone. DB: {DB_PATH}")
    db.close()

if __name__ == "__main__":
    main()
