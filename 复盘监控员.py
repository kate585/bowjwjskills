#!/usr/bin/env python3
"""复盘监控员 - 铁律: 只抓凯总【巴西】/kitty@gmail.love"""
import os, json, subprocess, sys, time
from datetime import datetime, timezone

STATE = os.path.expanduser("~/.hermes/state/bowjwj")
JWT = open(f"{STATE}/.jwt").read().strip()
BASE = "https://bowjwj.cc"
CREATOR = "750e89c7-e91f-46df-bae5-42109c0deb82"
H = ["-H", f"Authorization: Bearer {JWT}", "-H", "Content-Type: application/json"]
STATE_FILE = f"{STATE}/.replay_monitor_state.json"

# 铁律: 只认凯总
ALLOWED_EMAIL = "kitty@gmail.love"

def fetch_page(page_num):
    ts = int(time.time())
    url = f"{BASE}/api/replay-dashboard/batches?creator={CREATOR}&page={page_num}&pageSize=10&w=24H&_={ts}"
    r = subprocess.run(["curl", "-sS", *H, url], capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None

def extract_key(item):
    cb = item.get("createdBy") or {}
    return {
        "batchId": item.get("batchId"),
        "campaignName": item.get("campaignName", ""),
        "channel": (item.get("smsChannelName") or "")[:70],
        "taskCount": item.get("taskCount", 0),
        "creator": cb.get("name", "?"),
        "email": cb.get("email", "?"),
        "sent": item.get("sentCount", 0),
        "success": item.get("successCount", 0),
        "uv": item.get("uv", 0),
        "uvExUS": item.get("uvExcludingUs", 0),
        "rawClicks": item.get("rawClicks", 0),
        "clicks": item.get("clicks", 0),
        "clicksExUS": item.get("clicksExcludingUs", 0),
        "ctr": item.get("ctr", 0),
        "ctrExUS": item.get("ctrExcludingUs", 0),
        "regRate": item.get("registrationRate", 0),
        "cost": item.get("smsCost", 0),
        "costPerReg": item.get("costPerRegistration", 0),
        "reg": item.get("registrations", 0),
        "ftd": item.get("ftdCount", 0),
        "deposit": item.get("depositAmount", 0),
        "health": item.get("healthSummary", ""),
    }

def load_prev():
    if os.path.exists(STATE_FILE):
        return json.load(open(STATE_FILE))
    return {}

def save_state(state):
    json.dump(state, open(STATE_FILE, "w"), indent=2, default=str)

def run():
    now_utc = datetime.now(timezone.utc)
    now_str = now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
    prev = load_prev()

    all_rows = []
    for pg in [5, 6]:
        data = fetch_page(pg)
        if data is None:
            print(f"[{now_str}] ❌ page {pg} 获取失败")
            return
        for item in data.get("items", []):
            all_rows.append(item)

    # 铁律: 客户端过滤，只留凯总
    raw_count = len(all_rows)
    filtered = [r for r in all_rows if (r.get("createdBy") or {}).get("email") == ALLOWED_EMAIL]
    skipped = raw_count - len(filtered)
    current = {r["batchId"]: extract_key(r) for r in filtered}

    prev_ids = set(prev.keys())
    curr_ids = set(current.keys())
    new_ids = curr_ids - prev_ids
    removed_ids = prev_ids - curr_ids
    kept_ids = curr_ids & prev_ids

    changes = []
    for bid in kept_ids:
        c = current[bid]
        p = prev[bid]
        deltas = []
        if c['ctr'] != p.get('ctr', 0): deltas.append(f"CTR {p.get('ctr',0)}→{c['ctr']}")
        if c['rawClicks'] != p.get('rawClicks', 0): deltas.append(f"点击 {p.get('rawClicks',0)}→{c['rawClicks']}")
        if c['uv'] != p.get('uv', 0): deltas.append(f"UV {p.get('uv',0)}→{c['uv']}")
        if c['reg'] != p.get('reg', 0): deltas.append(f"REG {p.get('reg',0)}→{c['reg']}")
        if c['ftd'] != p.get('ftd', 0): deltas.append(f"FTD {p.get('ftd',0)}→{c['ftd']}")
        if c['deposit'] != p.get('deposit', 0): deltas.append(f"DEP {p.get('deposit',0)}→{c['deposit']}")
        if c['regRate'] != p.get('regRate', 0): deltas.append(f"注册率 {p.get('regRate',0)}→{c['regRate']}")
        if deltas:
            changes.append((bid, c, deltas))

    has_changes = bool(new_ids or removed_ids or changes)

    print(f"\n{'='*60}")
    print(f"[{now_str}] 复盘监控 P5+P6 | 凯总【巴西】专属 | {'⚠️ 变化!' if has_changes else '✅ 无变化'}" + (f" | 过滤{skipped}条非凯总" if skipped else ""))
    print(f"{'='*60}")

    # Card format for each record
    for i, (bid, k) in enumerate(current.items(), 1):
        marker = " 🆕" if bid in new_ids else (" 🔄" if bid in [c[0] for c in changes] else "")
        print(f"\n▸ #{i} {k['campaignName']}{marker}")
        print(f"  {k['channel']} · {k['taskCount']} 个号码包")
        print(f"  {k['creator']} / {k['email']}")
        print(f"  发送 {k['sent']}  /  送达 {k['success']}  |  UV {k['uv']}  |  总点击 {k['rawClicks']}  /  过滤后 {k['clicks']}  |  CTR {k['ctr']}%  /  CTR(排除US) {k['ctrExUS']}%  /  注册率 {k['regRate']}%")
        print(f"  成本 {k['cost']}  /  单注册 {k['costPerReg']}  |  注册 {k['reg']}  /  首充 {k['ftd']}  /  存款 {k['deposit']}")

    if changes:
        print(f"\n📌 变更详情:")
        for bid, k, deltas in changes:
            print(f"  {k['campaignName'][:50]} | {', '.join(deltas)}")

    total_sent = sum(k['sent'] for k in current.values())
    total_cost = sum(k['cost'] for k in current.values())
    total_ftd = sum(k['ftd'] for k in current.values())
    total_dep = sum(k['deposit'] for k in current.values())
    total_reg = sum(k['reg'] for k in current.values())
    ctr_gt0 = sum(1 for k in current.values() if k['ctr'] > 0)
    print(f"\n📊 合计 {len(current)}条 | 发送{total_sent} | 成本₱{total_cost:.0f} | CTR>0:{ctr_gt0} | 注册{total_reg} | 首充{total_ftd} | 存款₱{total_dep}")

    save_state({bid: {kk: v for kk, v in k.items() if kk != 'batchId'} for bid, k in current.items()})

if __name__ == "__main__":
    run()
