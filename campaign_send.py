#!/usr/bin/env python3
"""
bowjwj 活动发送 v2 — 新建模版 → 新建活动 → 启动 → 逐包发送(3秒间隔)
绕过/send-direct的DB bug, 走前端原生流程:
  1. POST /api/campaign-templates       创建模板 (RAFFLE 2659055 + 7D)
  2. POST /api/campaigns                 创建活动 (draft, SINGLE_AGENT_LINE)
  3. POST /api/campaigns/{id}/launch     启动活动
  4. POST /api/campaigns/{id}/send       逐包指定通道发信 (每个包3秒间隔, TG审批)
     body: {smsInstanceId, phonePackId}
特点: 多包共享1代理线, 逐包3秒间隔抗风控, 全量发送
"""
import subprocess, json, os, sys, time, sqlite3, threading
from datetime import datetime

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

JWT = open(os.path.expanduser("~/.hermes/state/bowjwj/.jwt")).read().strip()
BASE = "https://bowjwj.cc"
BID = "c7ee7c4c-ce0a-49c9-880a-9315d07c07b6"

# ★ 票券 RAFFLE 2659055 + 7D (铁律: 创建时必带) ★
TICKETS = [
    {"ticketType": "RAFFLE", "ticketId": "2659055", "ticketQuantity": 1},
]

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
GG_ALL = "3ab371e1-d8dc-4f43-9bbf-b7a18b582b9c"

OUTDIR = os.path.join(os.path.expanduser("~"), "Desktop", "bowjwj 发送模式更新脚本文件夹2")
DB_PATH = os.path.join(OUTDIR, "campaign_send.db")

# 每文案1通道, 10-15包, 目标800+条
PACKS_PER_CAMPAIGN = 10
TARGET_MIN_CLEAN = 30

COPIES = [
    # Globe — 零金额, 纯悬念/对话式 Taglish (CTR=0% 全部重写 2026-05-01)
    ("globe", "G1-account-update-curiosity-v1", "{$phone[10]} may bago sa account mo ngayon, tingnan mo na lang pag may time ka ${shortUrl}"),
    ("globe", "G2-balance-available-na-v1", "{$phone[10]} available na pala yung ni-check ko for you, baka gusto mo makita ${shortUrl}"),
    ("globe", "G3-napansin-ko-lang-v1", "{$phone[10]} uy napansin ko lang may nagbago sa profile mo ah, check mo nga ${shortUrl}"),
    ("globe", "G4-quick-update-v1", "{$phone[10]} quick update lang sa account side mo, pa-check na lang pag di ka busy ${shortUrl}"),
    ("globe", "G5-baka-makalimutan-v1", "{$phone[10]} reminder lang baka makalimutan mo, pwede mo na i-view anytime ${shortUrl}"),
    ("globe", "G6-para-sa-yo-v1", "{$phone[10]} may something na para sa yo dito, di ko na sinabi kung ano, check mo na ${shortUrl}"),
    # Smart — 零金额, 纯悬念/对话式 Taglish
    ("smart", "S1-account-refresh-v1", "{$phone[4]} nag-refresh yung account mo today, check mo lang kung okay na ${shortUrl}"),
    ("smart", "S1b-baka-nandyan-na-v1", "{$phone[4]} baka nandyan na yung hinihintay mo, di ko sure pero check mo na ${shortUrl}"),
    ("smart", "S2-profile-update-v1", "{$phone[4]} update sa profile mo, may pumasok ata, tingnan mo na lang ${shortUrl}"),
    ("smart", "S3-suspense-open-v1", "{$phone[4]} alam mo ba na may nakaabang sa yo? sige na, tingnan mo na ${shortUrl}"),
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

def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS templates (
            id TEXT PRIMARY KEY, name TEXT, carrier TEXT, sms_text TEXT,
            tickets_json TEXT, created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS campaigns (
            id TEXT PRIMARY KEY, template_id TEXT, template_name TEXT, carrier TEXT,
            channel_id TEXT, channel_index INTEGER,
            pack_ids TEXT, pack_count INTEGER, total_clean INTEGER,
            campaign_batch_id TEXT, agent_line_id TEXT,
            launch_status TEXT, send_approval_id TEXT, send_status TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS pack_used (pack_id TEXT PRIMARY KEY);
    """)
    db.commit()
    return db

def get_domains(count=50):
    """Get top N active shortlink domains — use shortlink-options (OPS_ADMIN compatible)"""
    domains = []
    data = call("GET", f"/api/domains/shortlink-options?backendInstanceId={BID}")
    items = data if isinstance(data, list) else data.get("list", [])
    for d in items:
        if d.get("shortlinkStatus") == "ACTIVE":
            domains.append(d["id"])
            if len(domains) >= count:
                break
    return domains

def get_fresh_packs(carrier, needed=100):
    """Get fresh packs for carrier, avoid used/blacklisted/test packs"""
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
            # 跳过已分配给其他活动的包(API侧assignmentCampaignId非空)
            if p.get("assignmentCampaignId"):
                continue
            src = p.get("source", "") or ""
            # 规避: 仅过滤测试包和unknown来源, 黑名单/专用不再过滤(走GG全网通即可)
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
    """Select N packs, prefer 银河 source, then medium-sized"""
    # Prioritize 银河 packs
    galaxy = [p for p in packs if "银河" in (p.get("source", "") if isinstance(p, dict) else "")]
    other = [p for p in packs if p not in galaxy]

    # Prefer medium packs (<=200 clean)
    galaxy_med = sorted([p for p in galaxy if p["clean"] <= 200], key=lambda x: x["clean"], reverse=True)
    other_med = sorted([p for p in other if p["clean"] <= 200], key=lambda x: x["clean"], reverse=True)

    selected = galaxy_med + other_med

    # If not enough, add larger packs
    if len(selected) < count:
        galaxy_large = sorted([p for p in galaxy if p["clean"] > 200], key=lambda x: x["clean"])
        other_large = sorted([p for p in other if p["clean"] > 200], key=lambda x: x["clean"])
        selected += galaxy_large + other_large

    return selected[:count], sum(p["clean"] for p in selected[:count])

def create_templates(db):
    templates = []
    for carrier, suffix, sms in COPIES:
        name = f"AI发送-{carrier}-{suffix}"
        body = {
            "name": name, "activityName": "NN33 New Jackpot", "campaignType": "activity",
            "smsText": sms,
            "ticketRewards": TICKETS,  # ★ array, RAFFLE 2659055 ★
            "backendInstanceId": BID, "defaultSendHour": 20,
            "defaultValidityHours": 168, "validityPeriod": "7D",
        }
        resp = call("POST", "/api/campaign-templates", body)
        tid = resp.get("id", "") if resp else ""
        err = resp.get("error", "") if resp else ""
        saved_tickets = resp.get("ticketRewards", [])
        ticket_ok = len(saved_tickets) > 0

        if tid and not err and ticket_ok:
            templates.append({"id": tid, "name": name, "carrier": carrier, "sms": sms})
            db.execute("INSERT OR IGNORE INTO templates (id, name, carrier, sms_text, tickets_json) VALUES (?,?,?,?,?)",
                      [tid, name, carrier, sms, json.dumps(saved_tickets)])
            print(f"  OK {tid[:16]}... | {name} | tickets={len(saved_tickets)}")
        elif tid and not ticket_ok:
            print(f"  WARN {tid[:16]}... | {name} | TICKETS EMPTY!")
        else:
            print(f"  ERR {name}: {err[:100] if err else 'no id'}")
        time.sleep(0.3)
    db.commit()
    return templates

def create_campaign(template, channel, packs, domains, db):
    """POST /api/campaigns → draft, SINGLE_AGENT_LINE"""
    carrier = template["carrier"]
    total_clean = sum(p["clean"] for p in packs)
    pack_ids = [p["id"] for p in packs]

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

    print(f"    创建活动: {len(pack_ids)}包/{total_clean}条/1通道...", end=" ", flush=True)
    resp = call("POST", "/api/campaigns", body, timeout=30)

    if not resp or resp.get("error"):
        err = resp.get("error", "no resp") if resp else "no resp"
        print(f"ERR: {err[:120]}")
        return None

    cid = resp.get("id", "")
    batch_id = resp.get("campaignBatchId", "")
    batch = resp.get("batch", {})
    shared_mode = batch.get("sharedAgentMode", "?")
    allocated = batch.get("allocatedLineCount", "?")
    total_phones = batch.get("totalPhoneCount", "?")

    # 竞态修复: batch 数据不完整时等2秒重试
    if shared_mode == "?" and cid:
        print(f"batch未就绪,等2s...", end=" ", flush=True)
        time.sleep(2)
        resp2 = call("GET", f"/api/campaigns/{cid}", timeout=15)
        batch2 = resp2.get("batch", {}) if isinstance(resp2, dict) else {}
        shared_mode = batch2.get("sharedAgentMode", shared_mode)
        allocated = batch2.get("allocatedLineCount", allocated)
        total_phones = batch2.get("totalPhoneCount", total_phones)
        if shared_mode != "?":
            print(f"OK | {shared_mode} | {allocated}代理线 | {total_phones}条")
        else:
            print(f"仍异常,继续")

    if shared_mode != "?" or not cid:
        pass  # already printed above
    else:
        pass

    db.execute("""
        INSERT OR REPLACE INTO campaigns (id, template_id, template_name, carrier, channel_id,
            pack_ids, pack_count, total_clean, campaign_batch_id, launch_status)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, [cid, template["id"], template["name"], carrier, channel,
          json.dumps(pack_ids), len(pack_ids), total_clean, batch_id, "draft"])

    for pid in pack_ids:
        db.execute("INSERT OR IGNORE INTO pack_used (pack_id) VALUES (?)", [pid])
    db.commit()

    return {"campaign_id": cid, "batch_id": batch_id, "shared_mode": shared_mode,
            "allocated_lines": allocated, "total_phones": total_phones,
            "pack_count": len(pack_ids), "total_clean": total_clean}

def launch_campaign(campaign_id):
    """POST /api/campaigns/{id}/launch — 直接启动, 竞态重试最多120s"""
    for attempt in range(12):
        resp = call("POST", f"/api/campaigns/{campaign_id}/launch", body={}, timeout=15)
        if not resp or resp.get("error"):
            err = resp.get("error", "no resp") if resp else "no resp"
            if ("资源不存在" in str(err) or "not found" in str(err).lower()) and attempt < 11:
                wait = min(3 * (attempt + 1), 30)
                print(f"    未就绪,等{wait}s...", end=" ", flush=True)
                time.sleep(wait)
                continue
            print(f"    启动ERR: {err[:100]}")
            return None
        agent_line = resp.get("agentLineId", "")
        launch_status = resp.get("launchStatus", "?")
        print(f"    启动OK | agentLine={agent_line[:16]}... | launch={launch_status}")
        return {"agent_line_id": agent_line, "launch_status": launch_status}
    return None

def get_batch_pack_campaigns(batch_id):
    """从replay-dashboard获取batch下每个包的子活动ID列表"""
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
    """POST /api/campaigns/{id}/send → TG审批后发出"""
    body = {"smsInstanceId": channel_id}
    resp = call("POST", f"/api/campaigns/{campaign_id}/send", body, timeout=30)

    if not resp:
        return None

    err = resp.get("error", "")
    if err and "APPROVAL_ALREADY_PENDING" not in err:
        return None

    requires = resp.get("requiresApproval", False)
    approval_id = resp.get("approvalId", "")
    status = resp.get("status", "?")

    if requires and approval_id:
        db.execute("UPDATE campaigns SET send_approval_id=?, send_status=? WHERE id=?",
                  [approval_id, "awaiting_approval", campaign_id])
        db.commit()
        return {"approval_id": approval_id, "status": "awaiting_approval"}
    else:
        return {"status": status}

def main():
    print("=" * 60)
    print("bowjwj 活动发送 v2 — 新建模版→活动→启动→逐包发送(3秒间隔)")
    print(f"策略: {PACKS_PER_CAMPAIGN}包×1通道 = SINGLE_AGENT_LINE = 1代理线 = 逐包3秒发送")
    print("=" * 60)

    db = init_db()  # main thread DB for template creation + pack tracking

    # Step 0: Get domains
    print("\n=== 获取短链域名 (前50) ===")
    domains = get_domains(50)
    print(f"可用域名: {len(domains)}")

    # Step 1: Create templates
    print(f"\n=== 创建模板 (RAFFLE 2659055 + 7D) ===")
    templates = create_templates(db)
    globe_tpls = [t for t in templates if t["carrier"] == "globe"]
    smart_tpls = [t for t in templates if t["carrier"] == "smart"]

    # Step 2: Get packs
    print(f"\n=== 获取号码包 ===")
    globe_packs = get_fresh_packs("globe", needed=150)
    smart_packs = get_fresh_packs("smart", needed=150)
    print(f"Globe: {len(globe_packs)} | Smart: {len(smart_packs)}")

    # Step 3: Create → Launch → Send (交替串行: G1→S1→G2→S2..., 10包无间隔连发)
    print(f"\n=== 创建+启动+发送 (交替串行, 10包连发) ===")
    results = []

    # Interleave carriers: [(globe, G1, ch1), (smart, S1, ch1), (globe, G2, ch2), ...]
    tasks = []
    for i in range(max(len(globe_tpls), len(smart_tpls))):
        if i < len(globe_tpls):
            tasks.append(("globe", globe_tpls[i], GLOBE_CH[i % len(GLOBE_CH)]))
        if i < len(smart_tpls):
            tasks.append(("smart", smart_tpls[i], SMART_CH[i % len(SMART_CH)]))

    remaining = {"globe": list(globe_packs), "smart": list(smart_packs)}

    for ti, (carrier, tpl, channel) in enumerate(tasks):
        all_packs = remaining[carrier]
        ch_index = (ti // 2) % (len(GLOBE_CH) if carrier == "globe" else len(SMART_CH)) + 1

        my_packs, my_total = select_packs(all_packs, PACKS_PER_CAMPAIGN)
        if len(my_packs) < 3 or my_total < 200:
            print(f"  [{ti+1}/{len(tasks)}] {carrier} {tpl['name'][:40]} SKIP: 包不足")
            continue

        used_ids = {p["id"] for p in my_packs}
        remaining[carrier] = [p for p in all_packs if p["id"] not in used_ids]

        print(f"  [{ti+1}/{len(tasks)}] {carrier} {tpl['name'][:40]} -> ch{ch_index} ({len(my_packs)}包/{my_total}条)")

        camp = create_campaign(tpl, channel, my_packs, domains, db)
        if not camp:
            continue
        time.sleep(1)

        launch = launch_campaign(camp["campaign_id"])
        if not launch:
            continue

        db.execute("UPDATE campaigns SET agent_line_id=?, launch_status=? WHERE id=?",
                  [launch.get("agent_line_id", ""), launch.get("launch_status", ""), camp["campaign_id"]])
        db.commit()

        sub_campaigns = get_batch_pack_campaigns(camp["batch_id"])
        if not sub_campaigns:
            print(f"    未找到子活动列表")
            continue

        # ★ 逐包3秒间隔发送 ★
        pack_sent = 0
        t0 = time.time()
        for pi, sc in enumerate(sub_campaigns):
            if pi > 0:
                time.sleep(3)
            send_result = send_campaign(sc["campaign_id"], channel, db)
            if send_result:
                pack_sent += 1
                print(f"    包{pi+1}/{len(sub_campaigns)} sent (approval: {send_result.get('approval_id', 'N/A')[:20]}...)")
            else:
                print(f"    包{pi+1}/{len(sub_campaigns)} ERR")

    # Summary
    print(f"\n{'='*60}")
    created = sum(1 for r in results if r.get("campaign_id"))
    launched = sum(1 for r in results if r.get("launch_status") == "launched")
    total_packs_sent = sum(r.get("pack_sent", 0) for r in results)
    total_vol = sum(r["total_clean"] for r in results)
    print(f"活动: {created} | 已启动: {launched} | 包已发送: {total_packs_sent}")
    print(f"总发量: {total_vol}条 | 代理线: {len(results)} (每活动1代理线)")

    for r in results:
        mode = r.get("shared_mode", "?")
        lines = r.get("allocated_lines", "?")
        ps = r.get("pack_sent", "?")
        print(f"  [{r['carrier']}] ch{r['ch']} {r['tpl'][:40]} | {r['total_clean']}条/{r['pack_count']}包 | {mode}/{lines}代理线 | {ps}/{r['pack_count']}包已发")

    print(f"\nDB: {DB_PATH}")
    print("下一步: TG审批 → T+30min → 查replay-dashboard评估CTR")

if __name__ == "__main__":
    main()
