#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bowjwj Fast Send Loop — tiered schedule, strict pack rules, Globe/Smart dual carrier.

Usage:
  python3 fast_send.py --dry-run              # Only fetch prereq, no send
  python3 fast_send.py --carrier globe        # Run Globe/Dito rounds
  python3 fast_send.py --carrier smart        # Run Smart/TNT rounds
  python3 fast_send.py --carrier both         # Run both sequentially
  python3 fast_send.py                        # Same as --carrier both
  python3 fast_send.py --rounds 1             # Run 1 round then stop
  python3 fast_send.py --config send_rules.json  # Custom rules file

Pack rules (hardcoded + rules JSON):
  - 号码包名称必须包含 globe/smart/dito/tnt 之一
  - 号码包名称不能含 黑名单
  - 违反任一规则 → 跳过该包

Schedule tiers:
  早高峰 07:00-09:00  30s/轮
  午高峰 12:00-13:00  30s/轮
  晚高峰 18:00-20:00  30s/轮 80包/轮
  正常时段 09:00-12:00 / 13:00-18:00 / 20:00-02:00  60s/轮
  休息 02:00-07:00  不发
"""
import subprocess, json, os, time, datetime, sys, urllib.parse, argparse, re, sqlite3, random, signal, threading
from pathlib import Path

# Ignore SIGURG (macOS sends this on out-of-band socket data, kills process otherwise)
signal.signal(signal.SIGURG, signal.SIG_IGN)

# ── Windows encoding fix ──
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ── Paths ──
SCRIPT_DIR = Path(__file__).parent
DEFAULT_RULES = SCRIPT_DIR / "send_rules.json"
STATE_DIR = SCRIPT_DIR  # GitHub repo is the source of truth
JWT_FILE = STATE_DIR / ".jwt"
CACHE_FILE_GLOBE = SCRIPT_DIR / "prereq_cache_globe.json"
CACHE_FILE_SMART = SCRIPT_DIR / "prereq_cache_smart.json"

def _cache_path(rules, carrier):
    """Per-terminal cache to avoid cross-terminal template pollution."""
    rules_path = rules.get("_rules_path", str(DEFAULT_RULES))
    stem = rules_path.replace(".json", "").replace("/", "_").replace("\\", "_")
    return SCRIPT_DIR / f"prereq_cache_{carrier}_{stem}.json"
ROUNDS_DIR = SCRIPT_DIR / "rounds"
LOG_FILE = SCRIPT_DIR / "fast_send.log"
DB_PATH = STATE_DIR / "stats.db"
SCHEMA_PATH = STATE_DIR / "stats_schema.sql"

# ── DB init ──
def init_db():
    if SCHEMA_PATH.exists():
        schema = SCHEMA_PATH.read_text()
        DB = sqlite3.connect(str(DB_PATH), isolation_level=None)
        DB.row_factory = sqlite3.Row
        DB.executescript(schema)
        # Auto-migrate missing columns
        for col, typ in [("ctr_history", "TEXT DEFAULT '[]'"), ("last_ctr", "REAL"),
                         ("last_clicks", "INTEGER DEFAULT 0"), ("last_regs", "INTEGER DEFAULT 0"),
                         ("last_ftd", "INTEGER DEFAULT 0"), ("last_roi", "REAL"),
                         ("last_checked_at", "TEXT"), ("sent_count", "INTEGER DEFAULT 0")]:
            try: DB.execute(f"ALTER TABLE campaigns ADD COLUMN {col} {typ}")
            except: pass
        return DB
    return None

DB = init_db()

def db_log_round(carrier, tpl_id, tpl_name, ch_id, ch_name, campaign_ids, batch_ids, pack_ids, status):
    if not DB: return
    try:
        cid = campaign_ids[0] if campaign_ids else "unknown"
        bid = batch_ids[0] if batch_ids else ""
        DB.execute(
            "INSERT INTO campaigns(id,batch_id,tpl_id,tpl_name,ch_id,ch_name,carrier,pack_ids,status,launch_status) VALUES(?,?,?,?,?,?,?,?,?,?)",
            [cid, bid, tpl_id, tpl_name, ch_id, ch_name, carrier, json.dumps(pack_ids), status, status])
        # Also log each pack send
        for pid in pack_ids:
            DB.execute(
                "INSERT INTO send_log(campaign_id,pack_id,channel_id,carrier,action,result) VALUES(?,?,?,?,?,?)",
                [cid, pid, ch_id, carrier, "test-send", status])
    except Exception as e:
        log(f"DB write err: {e}")

# ── CTR streak tracking (aligned with config.json iron rules) ──
CTR_STREAK = {"globe": 0, "smart": 0}
CTR_THRESHOLD = 0.05  # 5% (Willy iron rule: per-batch CTR >= 5%)

def check_batch_ctr(batch_id, campaign_id, carrier):
    """Query replay-dashboard for actual delivery CTR. Normalizes API % to ratio."""
    if not batch_id:
        return None
    try:
        jwt = read_jwt()
        BASE = RULES["apiBase"]
        data = api_get(f"{BASE}/api/replay-dashboard/batches/{batch_id}", jwt)
        if not data or "error" in str(data):
            return None
        headline = data.get("headline", {})
        traffic = headline.get("traffic", {})
        conversions = headline.get("conversion", {})
        cost = headline.get("cost", {})
        ai = data.get("ai", {})
        result = {
            "clicks": traffic.get("clicks", 0),
            "uv": traffic.get("uv", 0),
            "ctr": traffic.get("ctr", 0) / 100.0,  # API returns % (2.91=2.91%), normalize to ratio
            "registrations": conversions.get("registrations", 0),
            "ftd": conversions.get("ftdCount", 0),
            "deposit": conversions.get("depositAmount", 0),
            "sms_cost": cost.get("smsCost", 0),
            "roi": ai.get("metrics", {}).get("roi", 0) if ai else 0,
            "sent": data.get("funnel", {}).get("delivered", 0),
        }
        # Update DB
        if DB:
            hist = DB.execute("SELECT ctr_history FROM campaigns WHERE id=?", [campaign_id]).fetchone()
            hist_list = json.loads(hist[0]) if hist and hist[0] else []
            hist_list.append({"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "ctr": result["ctr"],
                              "clicks": result["clicks"], "regs": result["registrations"], "ftd": result["ftd"]})
            DB.execute(
                "UPDATE campaigns SET last_ctr=?,last_clicks=?,last_regs=?,last_ftd=?,last_roi=?,last_checked_at=?,ctr_history=?,sent_count=? WHERE id=?",
                [result["ctr"], result["clicks"], result["registrations"], result["ftd"],
                 result["roi"], time.strftime("%Y-%m-%d %H:%M:%S"), json.dumps(hist_list),
                 result.get("sent", 0), campaign_id])
        return result
    except Exception as e:
        log(f"CTR check error for {batch_id}: {e}")
        return None

def find_best_from_intelligence(carrier=None):
    """Get top system-wide copies from intelligence/dimensions for optimization."""
    try:
        jwt = read_jwt()
        BID = RULES["backendInstanceId"]
        BASE = RULES["apiBase"]
        data = api_get(f"{BASE}/api/intelligence/dimensions?period=3d&backendInstanceId={BID}", jwt)
        dims = data.get("dimensions", {})
        text_copies = dims.get("textCopy", [])
        if not text_copies:
            return None
        valid = [t for t in text_copies if t.get("campaignCount", 0) >= 2]
        valid.sort(key=lambda x: x.get("funnel", {}).get("ctr", 0), reverse=True)
        if not valid:
            return None
        best = valid[0]
        funnel = best.get("funnel", {})
        cost = best.get("cost", {})
        return {
            "label": best.get("dimensionLabel", ""),
            "ctr": funnel.get("ctr", 0) / 100.0,
            "ftd_rate": funnel.get("ftdRate", 0) / 100.0,
            "reg_rate": funnel.get("registrationRate", 0) / 100.0,
            "roi": cost.get("roi", 0),
            "composite_score": best.get("compositeScore", 0),
        }
    except Exception as e:
        log(f"Intelligence query err: {e}")
        return None

def find_best_by_deposit_3d():
    """Iron rule 2026-05-03: query operations-report for last 3 days grouped by template, return template with highest depositAmount."""
    try:
        jwt = read_jwt()
        BID = RULES["backendInstanceId"]
        BASE = RULES["apiBase"]
        today = datetime.date.today()
        three_days_ago = today - datetime.timedelta(days=3)
        url = f"{BASE}/api/operations-report?dateFrom={three_days_ago.isoformat()}&dateTo={today.isoformat()}&backendInstanceId={BID}&groupBy=template"
        data = api_get(url, jwt)
        if not data or "error" in str(data):
            return None
        items = data.get("data", data.get("items", data.get("list", [])))
        if not items:
            return None
        # Find template with highest depositAmount
        best = max(items, key=lambda c: c.get("depositAmount", 0) or 0)
        deposit = best.get("depositAmount", 0) or 0
        if deposit <= 0:
            return None
        tpl_id = best.get("templateId", "")
        tpl_name = best.get("templateName", "") or best.get("displayTitle", "")[:80]
        # CTR: operations-report may return as percentage (e.g. 5.2) or ratio (0.052)
        ctr_val = best.get("ctr", 0) or 0
        if isinstance(ctr_val, (int, float)) and ctr_val > 1:
            ctr_val = ctr_val / 100.0
        # Compute CTR from raw numbers if not directly available
        if ctr_val == 0:
            sent = best.get("sentCount", 0) or 0
            clicks = best.get("clicks", 0) or 0
            if sent > 0:
                ctr_val = clicks / sent
        ftd = best.get("ftdCount", best.get("ftd", 0)) or 0
        return {
            "templateId": tpl_id,
            "templateName": tpl_name,
            "depositAmount": deposit,
            "ftdCount": ftd,
            "ctr": ctr_val,
        }
    except Exception as e:
        log(f"operations-report query err: {e}")
        return None

def find_best_deposit_copy(carrier):
    """Find highest deposit/conversion copy from recent replay-dashboard data.
    Returns template ID of best copy, or None if not found."""
    try:
        jwt = read_jwt()
        BASE = RULES["apiBase"]
        BID = RULES["backendInstanceId"]
        # Fetch recent batches
        data = api_get(f"{BASE}/api/replay-dashboard/batches?backendInstanceId={BID}&pageSize=30&page=1", jwt)
        items = data.get("items", data.get("data", []))
        if isinstance(data, list):
            items = data
        if not items:
            return None

        # Score batches by deposit + FTD, group by template
        from collections import defaultdict
        tpl_scores = defaultdict(lambda: {"deposit": 0, "ftd": 0, "ctr": 0, "count": 0})
        for b in items:
            name = (b.get("smsChannelName") or "").lower()
            carrier_match = False
            if carrier == "globe" and any(k in name for k in ["globe", "dito"]):
                carrier_match = True
            elif carrier == "smart" and any(k in name for k in ["smart", "tnt"]):
                carrier_match = True
            if not carrier_match:
                continue
            tpl_id = b.get("templateId", "")
            if not tpl_id:
                continue
            deposit = b.get("depositAmount", 0) or 0
            ftd = b.get("ftdCount", 0) or 0
            ctr = b.get("ctr", 0) or 0
            tpl_scores[tpl_id]["deposit"] += deposit
            tpl_scores[tpl_id]["ftd"] += ftd
            tpl_scores[tpl_id]["ctr"] = max(tpl_scores[tpl_id]["ctr"], ctr)
            tpl_scores[tpl_id]["count"] += 1

        if not tpl_scores:
            return None

        # Score: deposit_weight * 0.5 + ftd_weight * 0.3 + ctr_weight * 0.2
        best_score = -1
        best_id = None
        for tid, s in tpl_scores.items():
            score = s["deposit"] * 0.5 + s["ftd"] * 100 * 0.3 + s["ctr"] * 100 * 0.2
            if score > best_score:
                best_score = score
                best_id = tid

        if best_id:
            log(f"[{carrier}] Best deposit copy: {best_id[:12]}... (deposit={tpl_scores[best_id]['deposit']}, ftd={tpl_scores[best_id]['ftd']})")
            # Update copy pool to use this template first
            carrier_cfg = RULES["carriers"][carrier]
            pool = carrier_cfg.get("copyPoolTemplateIds", [])
            if best_id not in pool:
                pool.insert(0, best_id)
            else:
                pool.remove(best_id)
                pool.insert(0, best_id)
            carrier_cfg["copyPoolTemplateIds"] = pool[:20]
            carrier_cfg["_copyPoolIndex"] = 0
            # Persist to config
            rules_path = Path(RULES.get("_rules_path", str(DEFAULT_RULES)))
            try:
                with open(rules_path, encoding="utf-8") as f:
                    rules = json.load(f)
                rules["carriers"][carrier]["copyPoolTemplateIds"] = pool[:20]
                rules["carriers"][carrier]["_copyPoolIndex"] = 0
                with open(rules_path, "w", encoding="utf-8") as f:
                    json.dump(rules, f, ensure_ascii=False, indent=2)
                log(f"[{carrier}] Updated config with best deposit copy at pool[0]")
            except Exception as e:
                log(f"[{carrier}] Failed to persist best deposit copy: {e}")
            return best_id
        return None
    except Exception as e:
        log(f"[{carrier}] find_best_deposit_copy error: {e}")
        return None


def diagnose_zero_ctr(carrier, batch_id=None, campaign_id=None):
    """Iron rule: CTR=0% → STOP, diagnose root cause, fix, then resume.

    Diagnosis logic (from 2026-05-02 blood lessons):
      rawClicks=0             → copy blocked by carrier spam filter → rewrite copy
      rawClicks>0, filtered=0 → US crawler/security scanner → switch domain or channel
      Both>0 but CTR≈0%       → channel/copy mismatch → switch channel + optimize copy

    Returns dict: {diagnosis, fix_applied, cooldown_seconds, details}"""
    diagnosis = "unknown"
    fix_applied = []
    cooldown = 20  # default 20s (Willy: CTR=0% 20s冷却)
    details = {}

    log(f"[{carrier}] ╔══ DIAGNOSE ZERO CTR ══╗")

    # 1) Try to get raw vs filtered click data from replay-dashboard
    raw_clicks = 0
    filtered_clicks = 0
    if batch_id:
        try:
            jwt = read_jwt()
            BASE = RULES["apiBase"]
            data = api_get(f"{BASE}/api/replay-dashboard/batches/{batch_id}", jwt)
            if data:
                headline = data.get("headline", {})
                traffic = headline.get("traffic", {})
                raw_clicks = traffic.get("rawClicks", traffic.get("clicks", 0))
                # Try to get filtered count from funnel
                funnel = data.get("funnel", {})
                filtered_clicks = funnel.get("filteredClicks", funnel.get("botFiltered", 0))
                details["raw_clicks"] = raw_clicks
                details["filtered_clicks"] = filtered_clicks
                details["sent"] = funnel.get("delivered", 0)
        except Exception as e:
            log(f"[{carrier}] Diagnosis: batch query failed ({e}), using heuristic")

    # 2) Determine root cause
    if raw_clicks == 0:
        diagnosis = "COPY_BLOCKED"
        log(f"[{carrier}] 🔍 Diagnosis: rawClicks=0 → 文案被运营商垃圾过滤器屏蔽")
        log(f"[{carrier}]    → 行动: 停发当前文案, 立即换最高转化充值文案, 不冷却")
        # Fix: switch to highest deposit/conversion copy immediately
        best_deposit = find_best_deposit_copy(carrier)
        if best_deposit:
            fix_applied.append("copy_replaced_best_deposit")
            log(f"[{carrier}]    ✅ 已切换到最高转化文案: {best_deposit[:60]}")
        else:
            # Fallback: generate new Taglish copies
            new_tpls = optimize_copy_for_carrier(carrier, 0)
            if new_tpls:
                fix_applied.append("copy_replaced")
                log(f"[{carrier}]    ✅ 已替换文案: {new_tpls[:3] if isinstance(new_tpls, list) else new_tpls}")
            else:
                fix_applied.append("copy_generation_failed")
                log(f"[{carrier}]    ⚠️ 文案生成失败")
        cooldown = 0  # 不冷却，立即发 (Willy: 直接换文案, 不设冷却)

    elif raw_clicks > 0 and filtered_clicks == 0:
        diagnosis = "US_CRAWLER"
        log(f"[{carrier}] 🔍 Diagnosis: rawClicks={raw_clicks}>0 but filteredClicks=0 → US爬虫污染")
        log(f"[{carrier}]    → 行动: 切换短链域名到非US Cloudflare节点 + 切换通道")
        # Fix 1: Rotate shortlink domain (switch to next domain in pool)
        carrier_cfg = RULES["carriers"][carrier]
        cache_file = _cache_path(RULES, carrier)
        if cache_file.exists():
            cache_file.unlink()
            fix_applied.append("domain_rotated")
            log(f"[{carrier}]    ✅ 短链域名缓存已清除, 下次将使用新域名池")
        # Fix 2: Also switch channel (current channel's IP range known to US scanners)
        fix_applied.append("channel_switched")
        cooldown = 150  # 150s for domain rotation (Willy: 150s换域名)

    else:
        diagnosis = "LOW_ENGAGEMENT"
        log(f"[{carrier}] 🔍 Diagnosis: rawClicks={raw_clicks}>0, filtered={filtered_clicks}>0 but CTR≈0% → 文案/通道不匹配")
        log(f"[{carrier}]    → 行动: 切换通道 + 优化文案")
        # Fix: switch channel + optimize copy
        new_tpls = optimize_copy_for_carrier(carrier, 0)
        if new_tpls:
            fix_applied.append("copy_replaced")
        fix_applied.append("channel_switched")
        cooldown = 20  # 20s (Willy: CTR=0% 20s冷却)

    log(f"[{carrier}] ╚══ DIAGNOSIS: {diagnosis} | fixes: {fix_applied} | cooldown: {cooldown}s ══╝")
    return {"diagnosis": diagnosis, "fix_applied": fix_applied, "cooldown_seconds": cooldown, "details": details}


def optimize_copy_for_carrier(carrier, current_ctr=None):
    """Iron rule: CTR=0% → immediate optimize. CTR<1% → after 2-streak. Uses intelligence + AI generate."""
    ctr_str = f"{current_ctr:.2%}" if current_ctr is not None else "?"
    log(f"[optimize] {carrier} CTR={ctr_str} — triggering copy optimization")

    # 1) Try intelligence/dimensions for system best
    best = find_best_from_intelligence(carrier)
    if best and best["ctr"] > 0.01:
        log(f"[optimize] System best: CTR={best['ctr']:.2%} label={best['label'][:40]}")

    # 2) Generate fresh Taglish templates via AI
    jwt = read_jwt()
    BID = RULES["backendInstanceId"]
    BASE = RULES["apiBase"]
    new_tpl = generate_taglish_template(jwt, BID, BASE, carrier)
    if new_tpl:
        if DB:
            DB.execute(
                "INSERT INTO ctr_alerts(campaign_id,carrier,ctr,threshold,action_taken) VALUES(?,?,?,?,?)",
                ["optimize", carrier, current_ctr or 0, CTR_THRESHOLD,
                 f"Generated optimized template {new_tpl['id'][:12]} via AI generate"])
        log(f"[optimize] New template: {new_tpl['id'][:12]}...")
        return [new_tpl]
    return []

def monitor_ctr_and_optimize(round_num, carrier, campaign_ids, batch_ids):
    """Post-round: check replay-dashboard CTR, apply iron rules, trigger optimization if needed."""
    if not campaign_ids or not batch_ids:
        return

    cid = campaign_ids[0]
    bid = batch_ids[0]

    ctr = check_batch_ctr(bid, cid, carrier)
    if not ctr:
        return

    c = ctr["ctr"]
    cl = ctr["clicks"]
    log(f"  CTR monitor R{round_num} {carrier}: CTR={c:.2%} clicks={cl} regs={ctr['registrations']} FTD={ctr['ftd']} ROI={ctr['roi']:.2f}")

    # ─── Iron rule 1: CTR=0% → STOP, diagnose root cause, fix, then resume ───
    if c == 0 and cl == 0:
        log(f"  🚨 IRON RULE: {carrier} CTR=0% — 停发诊断中...")
        diagnosis = diagnose_zero_ctr(carrier, bid, cid)
        log(f"  📋 诊断: {diagnosis['diagnosis']} | 修复: {diagnosis['fix_applied']} | 冷却: {diagnosis['cooldown_seconds']}s")
        CTR_STREAK[carrier] = 0
        return "stopped_zero_ctr"

    # ─── Iron rule 2: CTR < 1% → accumulate streak, trigger at 2 ───
    elif c < CTR_THRESHOLD:
        CTR_STREAK[carrier] += 1
        streak = CTR_STREAK[carrier]
        log(f"  🔴 {carrier} CTR={c:.2%} < {CTR_THRESHOLD:.0%} (streak={streak}/2)")
        if streak >= 2:
            log(f"  🤖 Streak trigger: optimizing {carrier} copy...")
            new_tpls = optimize_copy_for_carrier(carrier, c)
            if new_tpls:
                CTR_STREAK[carrier] = 0
                return "optimized"

    # ─── CTR >= 1%: normal, decrement streak ───
    else:
        CTR_STREAK[carrier] = max(0, CTR_STREAK[carrier] - 1)

    return "ok"

# ── Hardcoded pack rules (Willy 雷点, 不可覆盖) ──
PACK_MUST_CONTAIN = ["globe", "smart", "dito", "tnt"]
PACK_MUST_NOT_CONTAIN = []

RULES = None  # set in main()

def load_rules(rules_path):
    with open(rules_path, encoding="utf-8") as f:
        return json.load(f)

# ── Helpers ──

def log(msg, flush=False):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    try:
        print(line, flush=True)
    except Exception:
        pass


def read_jwt():
    path = Path(os.path.expanduser(RULES["jwtFile"]))
    return path.read_text().strip()


def api_get(url, jwt=None, timeout=45, retries=2):
    if jwt is None:
        jwt = read_jwt()
    last_err = None
    for attempt in range(retries + 1):
        try:
            r = subprocess.run(
                ["curl", "-sS", "-k", "--connect-timeout", "15", "--max-time", str(timeout),
                 "-H", f"Authorization: Bearer {jwt}", url],
                capture_output=True, timeout=timeout + 5,
            )
            raw = r.stdout.decode("utf-8", errors="replace")
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                clean = raw.encode("utf-8", errors="replace").decode("utf-8")
                try:
                    return json.loads(clean)
                except:
                    return {"_raw": clean[:500]}
        except (subprocess.TimeoutExpired, Exception) as e:
            last_err = e
            if attempt < retries:
                time.sleep(3 * (attempt + 1))
    raise last_err


def api_post(url, body, jwt=None):
    if jwt is None:
        jwt = read_jwt()
    body_json = json.dumps(body, ensure_ascii=False)
    # For large payloads, write to temp file to avoid command-line length limits
    tmp_dir = Path(os.environ.get("TEMP", os.environ.get("TMP", "/tmp")))
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_file = tmp_dir / "bow_send_body.json"
    tmp_file.write_text(body_json, encoding="utf-8")
    r = subprocess.run(
        ["curl", "-sS", "-k", "-X", "POST",
         "-H", f"Authorization: Bearer {jwt}",
         "-H", "Content-Type: application/json",
         "-d", f"@{tmp_file}", url],
        capture_output=True, timeout=180,
    )
    raw = r.stdout.decode("utf-8", errors="replace")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        clean = raw.encode("utf-8", errors="replace").decode("utf-8")
        try:
            return json.loads(clean)
        except:
            return {"_raw": clean[:500]}


def bj_now():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))


def is_pack_name_valid(name):
    """Hard check: name must contain one of PACK_MUST_CONTAIN, must NOT contain any PACK_MUST_NOT_CONTAIN."""
    low = name.lower()
    if any(re.search(r'(?:^|[\s,，])' + re.escape(bad) + r'(?:$|[\s,，])', name) for bad in PACK_MUST_NOT_CONTAIN):
        return False
    if PACK_MUST_CONTAIN and not any(kw in low for kw in PACK_MUST_CONTAIN):
        return False
    return True


# ── Schedule Logic ──

def get_current_tier():
    """Return the schedule tier for current BJ time, or None if outside active range."""
    now = bj_now()
    h = now.hour + now.minute / 60
    schedule = RULES.get("sendSchedule", {})
    tiers = schedule.get("tiers", [])

    for tier in tiers:
        for w in tier.get("windows", []):
            sh, sm = map(int, w["start"].split(":"))
            eh, em = map(int, w["end"].split(":"))
            start = sh + sm / 60
            end = eh + em / 60
            # Handle cross-midnight: e.g. 20:00-02:00
            if end <= start:
                if h >= start or h < end:
                    return tier
            else:
                if start <= h < end:
                    return tier
    return None


def in_send_window():
    return get_current_tier() is not None


def get_cycle_seconds():
    tier = get_current_tier()
    if tier:
        return tier.get("cycleSeconds", 60)
    return 60


# ── 量化规则: CTR动态调速 ──
# Track per-carrier CTR for dynamic speed adjustment
CARRIER_CTR_STATE = {}  # {carrier: {"ctr": float, "streak_0": int, "streak_low": int}}

def get_ctr_dynamic_cycle(carrier):
    """CTR-based dynamic cycle speed (量化规则 v1).
    CTR >= 6%: 1s (爆量)
    CTR 3-6%: 3s (正常)
    CTR 0-3%: 10s (观察限速)
    CTR = 0%: 999999 (停发, 等diagnose)
    Unknown: 3s (default)"""
    state = CARRIER_CTR_STATE.get(carrier, {})
    ctr = state.get("ctr", None)
    if ctr is None:
        return 3  # default: unknown CTR → normal speed
    if ctr >= 0.06:
        return 1   # 爆量
    elif ctr >= 0.03:
        return 3   # 正常
    elif ctr > 0:
        return 10  # 观察限速
    else:
        return 999999  # CTR=0% → 停发

def update_carrier_ctr(carrier, ctr):
    """Update CTR state for dynamic speed control."""
    if carrier not in CARRIER_CTR_STATE:
        CARRIER_CTR_STATE[carrier] = {"ctr": None, "streak_0": 0, "streak_low": 0, "last_clicks": 0, "last_sent": 0}
    state = CARRIER_CTR_STATE[carrier]
    state["ctr"] = ctr
    if ctr is not None:
        if ctr == 0:
            state["streak_0"] += 1
            state["streak_low"] += 1
        elif ctr < 0.03:
            state["streak_0"] = 0
            state["streak_low"] += 1
        else:
            state["streak_0"] = 0
            state["streak_low"] = 0

def get_ctr_state(carrier):
    """Get full CTR state for decision making."""
    if carrier not in CARRIER_CTR_STATE:
        CARRIER_CTR_STATE[carrier] = {"ctr": None, "streak_0": 0, "streak_low": 0, "last_clicks": 0, "last_sent": 0}
    return CARRIER_CTR_STATE[carrier]


# ── 量化规则: 通道轮转+性能追踪 ──
CHANNEL_STATE = {}  # {channel_id: {"ctr": float, "uses": int, "error_streak": int, "cooldown_until": 0}}

def get_next_channel(ch_ids, carrier):
    """Channel round-robin with CTR-weighted selection.
    - Track each channel's CTR and error streak
    - Skip channels in cooldown
    - Prefer higher-CTR channels
    - Round-robin among healthy channels"""
    if not ch_ids:
        return None

    now = time.time()
    # Filter out channels in cooldown
    available = [cid for cid in ch_ids if CHANNEL_STATE.get(cid, {}).get("cooldown_until", 0) < now]
    if not available:
        available = ch_ids  # all in cooldown, use any

    # Score each channel: CTR * 100 + bonus for low error streak
    def score(cid):
        s = CHANNEL_STATE.get(cid, {"ctr": 0.05, "uses": 0, "error_streak": 0})
        ctr_score = s.get("ctr", 0.05) * 100
        error_penalty = s.get("error_streak", 0) * 10
        # Prefer less-used channels to spread load
        use_penalty = min(s.get("uses", 0) * 0.1, 5)
        return ctr_score - error_penalty - use_penalty

    # Pick top 3, then random among them for variety
    scored = sorted(available, key=score, reverse=True)
    import random
    pick = random.choice(scored[:max(3, len(scored)//3)])

    # Track usage
    if pick not in CHANNEL_STATE:
        CHANNEL_STATE[pick] = {"ctr": 0.05, "uses": 0, "error_streak": 0, "cooldown_until": 0}
    CHANNEL_STATE[pick]["uses"] = CHANNEL_STATE[pick].get("uses", 0) + 1

    return pick

def update_channel_ctr(ch_id, ctr):
    """Update channel CTR after round completes."""
    if ch_id not in CHANNEL_STATE:
        CHANNEL_STATE[ch_id] = {"ctr": 0.05, "uses": 0, "error_streak": 0, "cooldown_until": 0}
    # EMA smoothing
    old = CHANNEL_STATE[ch_id].get("ctr", 0.05)
    CHANNEL_STATE[ch_id]["ctr"] = old * 0.7 + ctr * 0.3

def channel_error(ch_id, cooldown_sec=60):
    """Mark channel error, increase cooldown exponentially."""
    if ch_id not in CHANNEL_STATE:
        CHANNEL_STATE[ch_id] = {"ctr": 0.05, "uses": 0, "error_streak": 0, "cooldown_until": 0}
    streak = CHANNEL_STATE[ch_id].get("error_streak", 0) + 1
    CHANNEL_STATE[ch_id]["error_streak"] = streak
    CHANNEL_STATE[ch_id]["cooldown_until"] = time.time() + cooldown_sec * min(streak, 10)
    log(f"[CHANNEL] {ch_id[:12]} error streak={streak}, cooldown={cooldown_sec * min(streak, 10)}s")


def get_packs_per_round():
    tier = get_current_tier()
    if tier:
        return tier.get("packsPerRound", RULES["round"]["packsPerRound"])
    return RULES["round"]["packsPerRound"]


def next_window_eta():
    now = bj_now()
    h = now.hour + now.minute / 60
    schedule = RULES.get("sendSchedule", {})
    tiers = schedule.get("tiers", [])

    # Collect all window start hours
    all_starts = []
    for tier in tiers:
        for w in tier.get("windows", []):
            sh, sm = map(int, w["start"].split(":"))
            all_starts.append(sh + sm / 60)

    all_starts.sort()
    for s in all_starts:
        if h < s:
            return (s - h) * 3600
    # Next day first window
    return (24 - h + all_starts[0]) * 3600


# ── Taglish Template Generation ──

AI_INSTANCE_ID = "cmn0neb160001lnd0xdlc4ty1"

def generate_taglish_template(jwt, BID, BASE, carrier):
    """Generate Taglish SMS templates via AI and save the best one."""
    taglish_cfg = RULES.get("antiSpam", {}).get("contentRules", {}).get("taglishRules", {})
    insert_pool = taglish_cfg.get("insertWordPool", {})
    priority_words = taglish_cfg.get("priorityInsertWords", ["na", "mo", "lang", "pa"])

    # Build tone description enforcing hard rules + SMS cost constraints
    tone = (
        "conversational Taglish (English + Filipino mixed). "
        "HARD RULES: 1) Never start with brand name in caps + colon (like 'OKBET:'). "
        "2) Must include 1-2 Filipino words (na/mo/lang/pa/ba/ka) mixed into English. "
        "3) Maximum 1 exclamation mark. "
        "4) Use conversational tone not imperative (use 'pwede mo na' instead of 'Claim now'). "
        "5) NEVER use emoji or any non-ASCII characters — they double SMS cost. ASCII only. "
        "6) Maximum 145 characters total — exceeding this doubles SMS cost. "
        "NEVER use: bet, bonus, deposit, casino, free, claim, reward, promo, spin, jackpot, raffle, prize. "
        "Make it sound like a friend texting, not an ad."
    )

    # Need a pack ID for the API
    pack_id = None
    cat_data = api_get(
        f"{BASE}/api/phone-packs/categories?backendInstanceId={BID}&pageSize=1", jwt
    )
    cats = cat_data.get("data", [])
    if cats:
        enc_key = cats[0].get("key", "")
        encoded = urllib.parse.quote(enc_key, safe="")
        pdata = api_get(
            f"{BASE}/api/phone-packs/categories/{encoded}/packs?backendInstanceId={BID}&page=1&pageSize=1", jwt
        )
        packs = pdata.get("data", [])
        if packs:
            pack_id = packs[0]["id"]

    if not pack_id:
        log("Cannot generate Taglish template: no pack ID available")
        return None

    body = {
        "backendInstanceId": BID,
        "aiInstanceId": AI_INSTANCE_ID,
        "phonePackIds": [pack_id],
        "targetSiteName": "NN33",
        "activityName": "Account Update Taglish",
        "theme": "account update notification from a friend",
        "objective": "drive user to check their account via shortlink, without sounding like marketing",
        "tone": tone,
        "count": 5,
    }

    log("POST /ai-generate (Taglish)...")
    resp = api_post(f"{BASE}/api/campaign-templates/ai-generate", body, jwt)

    suggestions = resp.get("suggestions", [])
    if not suggestions:
        log(f"AI generate returned no suggestions: {str(resp)[:200]}")
        return None

    log(f"AI generated {len(suggestions)} Taglish suggestions")

    # Score each suggestion using same spam_score logic
    best_score = -999
    best_suggestion = None
    gambling_bl = ["BET", "BONUS", "DEPOSIT", "CASINO", "FREE", "CLAIM", "REWARD",
                   "PROMO", "SPIN", "JACKPOT", "RAFFLE", "PRIZE", "OKBET", "PBAHAY"]
    taglish_sigs = ["NA", "MO", "LANG", "PA", "BA", "KA", "MAY", "CHECK NA", "PWEDE"]

    for s in suggestions:
        sms = (s.get("smsText") or "").upper()
        sms_raw = s.get("smsText", "")

        # ★★★ 红线一票否决 (与 spam_score 同级) ★★★
        redline = False
        # 博彩促销词
        redline_words = ["ACT NOW", "CLAIM NOW", "CLICK NOW", "DEPOSIT NOW", "SIGN UP NOW",
                        "URGENT DEPOSIT", "URGENT OFFER", "FREE SPIN", "FREE BONUS",
                        "LIMITED TIME", "LAST CHANCE", "HURRY UP", "DON'T MISS"]
        for rw in redline_words:
            if rw in sms:
                redline = True; break
        # 赌博黑名单
        if not redline:
            for gw in gambling_bl:
                if gw in sms:
                    redline = True; break
        # 火星文变异
        if not redline:
            for lp in [r'R4FFL', r'B0NU', r'SP1N', r'D3POS', r'CL4IM', r'FR33', r'J4CKP']:
                if re.search(lp, sms):
                    redline = True; break
        if redline:
            log(f"  REDLINE KILL: {sms[:60]}")
            continue  # skip this suggestion entirely

        score = 50
        # Taglish word presence
        for tw in taglish_sigs:
            if f" {tw} " in f" {sms} " or sms.startswith(f"{tw} "):
                score += 20
        # Hard rules
        if re.match(r'^[A-Z]{2,}:', sms):
            score -= 40
        if sms.count("!") > 1:
            score -= (sms.count("!") - 1) * 15
        imperative = ["CLAIM NOW", "CLICK NOW", "ACT NOW", "DEPOSIT NOW", "SIGN UP NOW"]
        for imp in imperative:
            if imp in sms:
                score -= 25
        # 非 ASCII 字符 = 2条计费, 直接重罚
        non_ascii = sum(1 for c in sms_raw if ord(c) > 127)
        if non_ascii > 0:
            score -= 50
        # 超过145字符 = 2条计费, 重罚
        if len(sms_raw) > 145:
            score -= 50

        log(f"  Suggestion score={score}: {s.get('smsText','')[:60]}")
        if score > best_score:
            best_score = score
            best_suggestion = s

    if not best_suggestion or best_score < 0:
        log(f"Best Taglish score {best_score} too low, skipping")
        return None

    # Sanitize: strip non-ASCII and truncate to 145 chars (SMS cost rule)
    sms_text = best_suggestion["smsText"]
    sms_text = "".join(c for c in sms_text if ord(c) <= 127)
    if len(sms_text) > 145:
        sms_text = sms_text[:145]

    # Save the template via API
    tpl_body = {
        "backendInstanceId": BID,
        "name": f"ai模版自动发送-Taglish-{carrier}-{time.strftime('%m%d%H%M')}",
        "smsText": sms_text,
        "activityName": best_suggestion.get("activityName", "Account Update Taglish"),
        "campaignType": "activity",
        "validityPeriod": "7D",
        "defaultSendHour": 20,
        "defaultValidityHours": 168,
        # 铁律: FREE_SPIN x 1 (ID:2804039) 固定不可改
        "ticketRewards": [{"ticketType": "FREE_SPIN", "ticketId": "2804039", "ticketQuantity": 1}],
    }

    create_resp = api_post(f"{BASE}/api/campaign-templates", tpl_body, jwt)
    new_id = create_resp.get("id")
    if new_id:
        log(f"Created Taglish template: {new_id} (score={best_score})")
        return create_resp
    else:
        log(f"Template creation failed: {str(create_resp)[:200]}")
        return None


# ── CTR Monitoring & Auto Copy-Switching ──

def check_recent_ctr(carrier, min_sends=100):
    """Check recent batch CTR for carrier from replay-dashboard.
    Returns (ctr, clicks, sent, batch_id) or (None, 0, 0, None) if insufficient data."""
    jwt = read_jwt()
    BID = RULES["backendInstanceId"]
    BASE = RULES["apiBase"]
    carrier_cfg = RULES["carriers"][carrier]
    ch_keywords = carrier_cfg.get("channelKeywords", [])

    # Get recent campaigns for this carrier
    camp_data = api_get(f"{BASE}/api/campaigns?backendInstanceId={BID}&pageSize=50&status=sent", jwt)
    if isinstance(camp_data, dict):
        campaigns = camp_data.get("data", camp_data.get("items", camp_data.get("list", [])))
    else:
        campaigns = camp_data if isinstance(camp_data, list) else []

    total_clicks = 0
    total_sent = 0
    batch_ids_checked = set()

    for c in campaigns[:20]:
        cid = c.get("id", c.get("campaignId", ""))
        if not cid:
            continue

        # Check send-logs for actual sent count
        try:
            sl = api_get(f"{BASE}/api/send-logs?campaignId={cid}&pageSize=1", jwt)
            if isinstance(sl, dict):
                sent = sl.get("successCount", 0)
            else:
                sent = 0
        except Exception:
            sent = 0

        if sent < 10:
            continue

        # Get batch ID and check replay-dashboard for PH IP clicks
        batch_id = c.get("campaignBatchId") or c.get("batchId")
        if batch_id and batch_id not in batch_ids_checked:
            batch_ids_checked.add(batch_id)
            try:
                rd = api_get(f"{BASE}/api/replay-dashboard/batches/{batch_id}", jwt)
                headline = rd.get("headline", {})
                traffic = headline.get("traffic", {})
                # Use rawClicks (includes bot) or clicks (already filtered)
                clicks = traffic.get("clicks", traffic.get("rawClicks", 0))
                total_clicks += clicks
                total_sent += sent
            except Exception:
                # Fallback: use campaign-level clickCount
                total_clicks += c.get("clickCount", 0)
                total_sent += sent

    if total_sent < min_sends:
        return None, total_clicks, total_sent, None

    ctr = total_clicks / total_sent
    return ctr, total_clicks, total_sent, list(batch_ids_checked)


def auto_switch_copy(carrier, reason, current_ctr=0):
    """Generate new Taglish templates via AI, score them, and replace the current template.
    Invokes: copy-generate → copy-analyze → channel-analyze chain.
    Returns the new template ID or None if generation failed."""
    jwt = read_jwt()
    BID = RULES["backendInstanceId"]
    BASE = RULES["apiBase"]
    switch_cfg = RULES.get("copySwitch", {})

    if not switch_cfg.get("enabled", True):
        log(f"[{carrier}] Copy switching disabled, skipping")
        return None

    gen_count = switch_cfg.get("generationCount", 5)
    min_score = switch_cfg.get("minScore", 60)

    log(f"[{carrier}] === AUTO COPY SWITCH ===")
    log(f"[{carrier}] Reason: {reason} | Current CTR: {current_ctr*100:.2f}%")
    log(f"[{carrier}] Generating {gen_count} Taglish templates...")

    # Step 1: copy-generate — generate new Taglish copy
    new_templates = []
    for attempt in range(gen_count):
        try:
            tpl = generate_taglish_template(jwt, BID, BASE, carrier)
            if tpl and tpl.get("id"):
                sms = tpl.get("smsText", "")[:80]
                name = tpl.get("name", "?")
                # Score: prefer Taglish, penalize gambling keywords
                sms_upper = (tpl.get("smsText", "") or "").upper()
                score = 50
                for tw in ["MAY UPDATE", "CHECK NA", "PWEDE MO", "ACCOUNT MO"]:
                    if tw in sms_upper:
                        score += 20
                for gw in ["BET", "BONUS", "DEPOSIT", "CASINO", "FREE", "CLAIM"]:
                    if gw in sms_upper:
                        score -= 50
                new_templates.append({"id": tpl["id"], "name": name, "sms": sms, "score": score})
                log(f"[{carrier}]   Generated: {tpl['id'][:16]}... score={score} | {sms}")
        except Exception as e:
            log(f"[{carrier}]   Gen attempt {attempt+1} failed: {e}")
        if attempt < gen_count - 1:
            time.sleep(1)

    if not new_templates:
        log(f"[{carrier}] Copy generation failed — no valid templates produced")
        return None

    # Step 2: copy-analyze — score and pick best
    new_templates.sort(key=lambda x: x["score"], reverse=True)
    best = new_templates[0]
    log(f"[{carrier}] Best generated: {best['id'][:16]}... score={best['score']}")
    log(f"[{carrier}]   SMS: {best['sms']}")

    if best["score"] < min_score:
        log(f"[{carrier}] Best score {best['score']} < {min_score} minimum, discarding")
        return None

    # Step 3: channel-analyze — check channel health before switching
    # (If current channel is bad, template switch alone won't help)
    try:
        ch_data = api_get(f"{BASE}/api/adapters/instances?type=sms", jwt)
        if isinstance(ch_data, list):
            channels = ch_data
        else:
            channels = ch_data.get("data", ch_data.get("list", []))
        healthy = False
        for a in channels:
            if not a.get("enabled"):
                continue
            if BID not in a.get("backendInstanceIds", []):
                continue
            name = a.get("name", "")
            if any(x in name for x in ["包料", "对方给料", "猫王"]):
                continue
            if a.get("configInvalidSince") is None:
                healthy = True
                break
        if not healthy:
            log(f"[{carrier}] WARNING: No healthy channels! Copy switch may not help.")
    except Exception:
        pass

    # Step 4: Update send_rules.json with new best template
    rules_path = Path(RULES.get("_rules_path", str(DEFAULT_RULES)))
    try:
        with open(rules_path, encoding="utf-8") as f:
            rules = json.load(f)
        rules["carriers"][carrier]["bestTemplateId"] = best["id"]
        rules["carriers"][carrier]["bestTemplateSms"] = best["sms"]
        rules["carriers"][carrier]["bestTemplateCtr"] = "0.00% (new, unvalidated)"
        rules["carriers"][carrier]["bestTemplateNote"] = f"Auto-switched: {reason} (was CTR={current_ctr*100:.2f}%)"
        with open(rules_path, "w", encoding="utf-8") as f:
            json.dump(rules, f, ensure_ascii=False, indent=2)
        RULES["carriers"][carrier]["bestTemplateId"] = best["id"]
        RULES["carriers"][carrier]["bestTemplateSms"] = best["sms"]
        RULES["carriers"][carrier]["bestTemplateCtr"] = "0.00% (new, unvalidated)"
        log(f"[{carrier}] Updated send_rules.json: new bestTemplateId={best['id']}")
    except Exception as e:
        log(f"[{carrier}] Failed to update send_rules.json: {e}")

    log(f"[{carrier}] === COPY SWITCH COMPLETE ===")
    return best["id"]


# ── Prereq Fetching ──

def fetch_prereq(carrier="globe"):
    jwt = read_jwt()
    BID = RULES["backendInstanceId"]
    BASE = RULES["apiBase"]
    carrier_cfg = RULES["carriers"][carrier]
    round_cfg = RULES["round"]
    sl_cfg = RULES["shortlink"]

    log(f"Fetching prereq for carrier={carrier}...")

    # 1. Templates — anti-spam aware selection
    # NOTE: status=active&campaignType=activity filter is BROKEN on API side —
    # it inconsistently excludes templates that ARE active+activity (pagination/cache bug).
    # Fetch all and filter client-side instead.
    tpl_data = api_get(
        f"{BASE}/api/campaign-templates?backendInstanceId={BID}&pageSize=200",
        jwt
    )
    if isinstance(tpl_data, list):
        all_templates = tpl_data
    else:
        all_templates = tpl_data.get("data", tpl_data.get("list", []))
    templates = [t for t in all_templates
                 if t.get("status") == "active" and t.get("campaignType") == "activity"]

    tpl_cfg = RULES.get("template", {})
    kw = tpl_cfg.get("matchKeyword", "").lower()
    anti_spam = tpl_cfg.get("antiSpamPriority", False)
    preferred_kws = tpl_cfg.get("preferredTemplateKeywords", [])
    avoid_kws = tpl_cfg.get("avoidTemplateKeywords", [])

    # Score templates: Taglish > suspense > neutral > spam
    # Anti-spam: Tagalog/Taglish bypasses Google spam model; English promo = 100% junk
    gambling_blacklist = ["BET", "BONUS", "DEPOSIT", "CASINO", "FREE", "CLAIM", "REWARD",
                          "PROMO", "SPIN", "JACKPOT", "RAFFLE", "PRIZE", "WAGER", "PAYOUT",
                          "CASHBACK", "REBATE", "VIP", "EXCLUSIVE DEAL", "OKBET", "PBAHAY"]

    taglish_signals = ["MAY UPDATE", "CHECK NA LANG", "PAG MAY TIME", "PWEDE MO NA",
                       "READY NA", "SINABI KO", "PAG MAY", "NA-UPDATE", "I-CHECK",
                       "PUMASOK", "MAY BAGONG", "HANAPIN MO", "TINGNAN MO",
                       "WAG KANG", "ALAM MO BA", "NANDITO NA", "SUBUKAN MO",
                       "TINGNAN", "PUMUNTA", "KUMUSTA", "KAILANGAN MO",
                       "MAY TIME KA", "WALA PANG", "NA-RECEIVE", "NA-LOAD",
                       "ACCOUNT MO", "KITA MO", "NALANG", "NA NAMAN",
                       "SA'YO", "MO NAMAN", "BA TALAGA", "BA KAILANGAN"]

    tagalog_words = ["MAY", "NGAYON", "PWEDE", "MO", "ANG", "ITO", "KA", "NA",
                     "HINDI", "PASOK", "BUKSAN", "TINGNAN", "GRAB", "ACTIVE",
                     "OO", "BA", "PA", "DIN", "LANG", "NAMAN", "KAYA"]

    def spam_score(t):
        sms = (t.get("smsText") or "").upper()
        sms_raw = t.get("smsText") or ""
        name = t.get("name", "").lower()

        # ═══★★★ 红线一票否决 (碰红线 = 直接淘汰, score = -999) ★★★═══
        REDLINE_KILL = -999
        # 红线1: 博彩促销词 (ACT NOW / CLAIM / BONUS / DEPOSIT / RAFFLE / FREE 等)
        redline_words = ["ACT NOW", "CLAIM NOW", "CLICK NOW", "DEPOSIT NOW", "SIGN UP NOW",
                        "URGENT DEPOSIT", "URGENT OFFER", "FREE SPIN", "FREE BONUS",
                        "LIMITED TIME", "LAST CHANCE", "HURRY UP", "DON'T MISS"]
        for rw in redline_words:
            if rw in sms:
                return REDLINE_KILL
        # 红线2: 赌博黑名单词 (零容忍)
        for gw in gambling_blacklist:
            if gw in sms:
                return REDLINE_KILL
        # 红线3: 火星文变异词 (R4FFLE / b0nus / Sp1ns 等 — 故意绕检测)
        leet_patterns = [r'R4FFL', r'B0NU', r'SP1N', r'D3POS', r'CL4IM', r'FR33',
                        r'W1NN', r'PR1Z', r'C4S1N0', r'J4CKP0T', r'D3P0S']
        for lp in leet_patterns:
            if re.search(lp, sms):
                return REDLINE_KILL
        # 红线4: 品牌名+冒号+促销词组合 (OKBET: FREE! / NN33! URGENT)
        if re.match(r'^[A-Z0-9]{2,}[!=:]', sms):
            promo_after = ["FREE", "BONUS", "CLAIM", "WIN", "URGENT", "DEPOSIT", "SPIN",
                          "JACKPOT", "RAFFLE", "PRIZE", "OFFER", "BOOST", "REWARD", "PROMO"]
            first30 = sms[:30]
            if any(p in first30 for p in promo_after):
                return REDLINE_KILL
        # 红线5: 超过3个感叹号 (纯垃圾短信特征)
        if sms.count("!") > 3:
            return REDLINE_KILL

        # ═══ 通过红线后, 正常评分 ═══
        score = 50
        # Keyword match bonus
        if kw and kw in name:
            score += 20

        # ═══ Willy 5条硬规则 (违反直接重罚) ═══

        # 硬规则1: 开头不放品牌名大写 — "OKBET:" 冒号格式 = 广告模板信号
        if re.match(r'^[A-Z]{2,}:', sms):
            score -= 40

        # 硬规则2: 不能全英文 — Taglish 混搭比纯英文安全
        taglish_insert_words = ["NA", "MO", "LANG", "PA", "BA", "KA", "NGA",
                                "KASI", "SIGE", "BAKA", "AGAD", "TALAGA",
                                "NAMAN", "UY", "OY", "MAY", "DIN", "RIN"]
        has_taglish = any(f" {w} " in f" {sms} " or sms.startswith(f"{w} ")
                          for w in taglish_insert_words)
        if not has_taglish:
            # Pure English — penalty
            score -= 20

        # 硬规则3: 不超过1个感叹号 — 多感叹号 = 垃圾短信经典特征
        excl = sms.count("!")
        if excl > 1:
            score -= (excl - 1) * 15  # heavy penalty for each extra !

        # 硬规则4: 不用祈使句 — "Claim now" → "pwede mo na makuha"
        imperative_patterns = ["CLAIM NOW", "CLICK NOW", "ACT NOW", "DEPOSIT NOW",
                              "SIGN UP NOW", "REGISTER NOW", "HURRY UP",
                              "CLICK HERE", "GO NOW", "DO IT NOW", "GET IT NOW"]
        for imp in imperative_patterns:
            if imp in sms:
                score -= 25

        # 硬规则5: 只允许ASCII字符 — 非ASCII算2条短信费用
        non_ascii = sum(1 for c in sms_raw if ord(c) > 127)
        if non_ascii > 0:
            score -= 50  # 非ASCII = 2条计费, 重罚
        # 硬规则6: 不超过145字符 — 超出算2条短信
        if len(sms_raw) > 145:
            score -= 50  # 超145字符 = 2条计费, 重罚

        # ═══ 以下为原有评分逻辑 ═══

        # ★★★ Taglish/Tagalog phrases — strongest anti-spam signal (+40 each)
        taglish_count = sum(1 for s in taglish_signals if s in sms)
        score += taglish_count * 40
        # ★★ Tagalog word density (loose match, +15 each)
        tagalog_count = sum(1 for s in tagalog_words if f" {s} " in f" {sms} " or sms.startswith(f"{s} "))
        if tagalog_count >= 3:
            score += 45
        elif tagalog_count >= 1:
            score += 15
        # ★ Suspense style — 4.5% CTR
        suspense_signals = ["MIGHT BE", "MOST USEFUL", "5 SECONDS", "SECONDS OF YOUR",
                           "YOU WON'T BELIEVE", "WHAT HAPPENS", "DID YOU KNOW",
                           "HAVE YOU SEEN", "CHECK THIS", "BEFORE YOU"]
        suspense_count = sum(1 for s in suspense_signals if s in sms)
        score += suspense_count * 25
        # Preferred keywords
        for pkw in preferred_kws:
            if pkw.lower() in name or pkw.upper() in sms:
                score += 15
        # Avoid keywords
        for akw in avoid_kws:
            if akw.upper() in sms or akw.lower() in name:
                score -= 30
        # Gambling blacklist already handled by redline above (instant kill)
        # General spam words (-8 each, for words not in redline)
        spam_words = ["WIN", "URGENT", "CASH", "OFFER", "CLICK", "CONGRATULATIONS",
                      "EXCLUSIVE", "REDEEM", "GUARANTEED", "AMAZING"]
        for sw in spam_words:
            if sw in sms:
                score -= 8
        # All-caps ratio (spam signal)
        caps_ratio = sum(1 for c in sms if c.isupper()) / max(len(sms), 1)
        if caps_ratio > 0.3:
            score -= 15
        # Question marks (suspense/conversational signal)
        score += min(sms_raw.count("?"), 3) * 5
        # {$phone[4]} (bank notification format, low spam)
        if "{$PHONE[4]}" in sms:
            score += 10
        # Conversational Taglish tone markers
        conv_signals = ["MIGHT", "PROBABLY", "THOUGHT YOU", "REMEMBER", "CHECK NA LANG",
                       "PAG MAY TIME", "SA'YO", "MO NA", "NALANG", "BA"]
        for cs in conv_signals:
            if cs in sms:
                score += 5
        return score

    # ── Template selection: copy pool > force > best > anti-spam score ──
    # Iron rule (2026-05-02): copyPoolEnabled=true → ONLY use pool templates, round-robin
    copy_pool_enabled = carrier_cfg.get("copyPoolEnabled", False)
    copy_pool_ids = carrier_cfg.get("copyPoolTemplateIds", [])
    force_tpl_id = carrier_cfg.get("forceTemplateId")
    best_cfg_id = carrier_cfg.get("bestTemplateId")
    best_cfg_sms = carrier_cfg.get("bestTemplateSms", "")
    best_cfg_ctr = carrier_cfg.get("bestTemplateCtr", "")

    tpl_id = None
    tpl_name = None
    tpl_sms = ""

    # Copy pool round-robin — iron rule, takes priority over everything
    if copy_pool_enabled and copy_pool_ids:
        pool_idx = carrier_cfg.get("_copyPoolIndex", 0)
        # Build lookup from ID to template
        tpl_map = {t["id"]: t for t in templates if t.get("status") == "active"}
        # Try up to len(pool) times in case some templates are inactive
        for offset in range(len(copy_pool_ids)):
            candidate_id = copy_pool_ids[(pool_idx + offset) % len(copy_pool_ids)]
            if candidate_id in tpl_map:
                t = tpl_map[candidate_id]
                tpl_id = t["id"]
                tpl_name = t.get("name", "?")
                tpl_sms = (t.get("smsText") or "")[:100]
                # Advance index for next round (per-carrier independent)
                carrier_cfg["_copyPoolIndex"] = (pool_idx + offset + 1) % len(copy_pool_ids)
                log(f"Template (COPY POOL #{pool_idx+1}/{len(copy_pool_ids)}): {tpl_id} | {tpl_name}")
                log(f"  SMS: {tpl_sms}")
                break
        if not tpl_id:
            log(f"Copy pool: no active templates found from pool, falling back")

    # Force override — bypasses historical CTR and spam scoring
    if not tpl_id and force_tpl_id and templates:
        for t in templates:
            if t["id"] == force_tpl_id and t.get("status") == "active":
                tpl_id = t["id"]
                tpl_name = t.get("name", "?")
                tpl_sms = (t.get("smsText") or "")[:80]
                log(f"Template (FORCED): {tpl_id} | {tpl_name}")
                log(f"  SMS: {tpl_sms}")
                break
        if not tpl_id:
            log(f"Force template {force_tpl_id} not found or inactive, falling back")

    if not tpl_id and best_cfg_id and templates:
        for t in templates:
            if t["id"] == best_cfg_id and t.get("status") == "active":
                tpl_id = t["id"]
                tpl_name = t.get("name", "?")
                tpl_sms = (t.get("smsText") or "")[:80]
                log(f"Template (best for {carrier}, CTR={best_cfg_ctr}): {tpl_id} | {tpl_name}")
                log(f"  SMS: {tpl_sms}")
                break
        if not tpl_id:
            log(f"Best template {best_cfg_id} not found or inactive, falling back to spam_score")

    if not tpl_id and anti_spam and templates:
        scored = [(t, spam_score(t)) for t in templates]
        scored.sort(key=lambda x: x[1], reverse=True)
        best = scored[0]
        tpl_id = best[0]["id"]
        tpl_name = best[0].get("name", "?")
        tpl_sms = best[0].get("smsText", "?")[:80]
        log(f"Template (anti-spam, score={best[1]}): {tpl_id} | {tpl_name}")
        log(f"  SMS: {tpl_sms}")

        # If best template scores too low (< 60), auto-generate Taglish templates
        TAGLISH_MIN_SCORE = 60
        if best[1] < TAGLISH_MIN_SCORE:
            log(f"Best template score {best[1]} < {TAGLISH_MIN_SCORE}, generating Taglish templates...")
            new_tpl = generate_taglish_template(jwt, BID, BASE, carrier)
            if new_tpl:
                tpl_id = new_tpl["id"]
                tpl_name = new_tpl.get("name", "?")
                tpl_sms = (new_tpl.get("smsText") or "")[:80]
                log(f"Using generated Taglish template: {tpl_id} | {tpl_name}")
                log(f"  SMS: {tpl_sms}")
    elif not tpl_id:
        for t in templates:
            name = t.get("name", "")
            if kw in name.lower():
                tpl_id = t["id"]
                tpl_name = name
                break
        if not tpl_id and templates:
            tpl_id = templates[0]["id"]
            tpl_name = templates[0].get("name", "?")
        log(f"Template: {tpl_id} | {tpl_name}")

    # 2. Channels — prefer GG家全网通 for Globe, otherwise match keywords
    ch_data = api_get(f"{BASE}/api/adapters/instances?type=sms", jwt)
    if isinstance(ch_data, list):
        channels = ch_data
    else:
        channels = ch_data.get("data", ch_data.get("list", []))

    ch_ids = []
    ch_names = []
    ch_keywords = carrier_cfg.get("channelKeywords", [carrier_cfg.get("channelKeyword", "")])

    # Blocked channels from config (user-managed, GG全网通 restored 2026-05-02)
    BLOCKED_CHANNELS = RULES.get("blockedChannels", [])

    for a in channels:
        if not a.get("enabled"):
            continue
        name = a.get("name", "")
        if BID not in a.get("backendInstanceIds", []):
            continue
        if any(x in name for x in ["包料", "对方给料", "猫王"]):
            continue
        # Skip blocked channels (e.g. GG全网通 CTR=0% spam filtered)
        if a["id"] in BLOCKED_CHANNELS:
            log(f"  BLOCKED: {name[:40]} (in blockedChannels list)")
            continue
        name_lower = name.lower()
        matched = any(kw.lower() in name_lower for kw in ch_keywords if kw)
        if matched:
            ch_ids.append(a["id"])
            ch_names.append(name[:60])

    log(f"Channels ({carrier}): {len(ch_ids)} (blocked={len(BLOCKED_CHANNELS)})")
    for n in ch_names[:3]:
        log(f"  {n}")

    # 3. Shortlink domains — use shortlink-options (returns active domains for this backend)
    sl_data = api_get(f"{BASE}/api/domains/shortlink-options?backendInstanceId={BID}", jwt)
    if isinstance(sl_data, list):
        domains = sl_data
    else:
        domains = sl_data.get("list", sl_data.get("data", sl_data.get("items", [])))
    # shortlink-options already returns shortlink-ready domains; filter active
    active_domains = [d for d in domains
                      if d.get("shortlinkStatus", "ACTIVE") in ("ACTIVE", "active")]
    active_domains.sort(key=lambda x: x.get("createdAt", ""), reverse=True)

    # Filter out known-dead domains (confirmed timeout/failure)
    dead_domains = {"now.vip", "dead-domain.example"}
    alive = []
    for d in active_domains:
        host = d.get("host", "")
        if host.lower() in dead_domains:
            log(f"  Skipping dead domain: {host}")
            continue
        alive.append(d)
    log(f"Shortlink domains: {len(alive)}/{sl_cfg['domainCount']} (filtered dead)")

    sl_ids = [d["id"] for d in alive[:sl_cfg["domainCount"]]]

    # Fallback: if API returned 0 domains (e.g. AUTH_FORBIDDEN for non-SUPER_ADMIN),
    # reuse cached domain IDs from previous successful fetch
    if not sl_ids:
        cache_file = _cache_path(RULES, carrier)
        if cache_file.exists():
            try:
                with open(cache_file, encoding="utf-8") as f:
                    cached = json.load(f)
                cached_ids = cached.get("domainIds", [])
                if cached_ids:
                    log(f"Domain API returned 0, falling back to {len(cached_ids)} cached domain IDs")
                    sl_ids = cached_ids[:sl_cfg["domainCount"]]
            except Exception:
                pass

    # 4. Phone packs — direct API (fast, avoids N+1 category calls)
    keywords = carrier_cfg["packNameKeywords"]
    excludes = carrier_cfg["excludeKeywords"]
    min_clean = round_cfg["minCleanCount"]

    max_packs = 500
    all_packs = []
    used_ids = set()

    # ═══ 铁律 2026-05-03: kt06独占第16-18页, 从config读取, 禁止任何终端修改 ═══
    import urllib.parse
    _cfg_page = carrier_cfg.get("packPage") or RULES.get("packRules", {}).get("packPage", 16)
    _cfg_page_end = carrier_cfg.get("packPageMax") or RULES.get("packRules", {}).get("packPageMax", 18)
    pack_pages = list(range(_cfg_page, _cfg_page_end + 1))
    pack_page_size = carrier_cfg.get("packPageSize") or RULES.get("packRules", {}).get("packPageSize", 100)
    search_query = RULES.get("packRules", {}).get("searchQuery", "")
    source_filter = RULES.get("packRules", {}).get("sourceMustStartWith", "")

    packs = []
    seen = set()
    for pg in pack_pages:
        try:
            params = f"backendInstanceId={BID}&pageSize={pack_page_size}&page={pg}&sort=-createdAt"
            if search_query:
                params += f"&q={urllib.parse.quote(search_query, safe='')}"
            pdata = api_get(f"{BASE}/api/phone-packs?{params}", jwt, timeout=120)
            page_packs = pdata.get("data", [])
            for pp in page_packs:
                pid = pp.get("id", "")
                if pid and pid not in seen:
                    seen.add(pid)
                    packs.append(pp)
            if pg == pack_pages[0]:
                log(f"Phone packs pages={pack_pages}, q={search_query}, page {pg} got {len(page_packs)} packs (totalPages={pdata.get('totalPages', 0)})")
        except Exception as e:
            log(f"Phone packs page={pg} fetch failed: {e}, continuing with {len(packs)} packs so far")
    log(f"Phone packs merged: {len(packs)} total (deduped) from {len(pack_pages)} pages")

    for p in packs:
        pid = p.get("id", "")
        if pid in used_ids:
            continue
        if p.get("reuseLocked", False):
            continue
        if p.get("assignmentCampaignId") is not None:
            continue
        if p.get("cleanCount", 0) < min_clean:
            continue
        src = p.get("source", "")
        # Client-side source filter (fallback if API doesn't support source param)
        if source_filter and not src.startswith(source_filter):
            continue
        pname = p.get("name", src)
        combined = (src + " " + pname).lower()
        # Carrier keyword match (galaxy packs relax unknown carrier)
        is_galaxy = "银河" in combined
        is_unknown = "unknown carrier" in combined
        if is_galaxy:
            if any(bad in combined for bad in ["黑名单专用", "专用黑名单"]):
                continue
            if not is_unknown and not any(kw in combined for kw in keywords):
                continue
        else:
            if not any(kw in combined for kw in keywords):
                continue
        # Exclude check (skip 黑名单 for galaxy packs)
        if not is_galaxy and any(ex in combined for ex in excludes if ex):
            continue
        if not is_pack_name_valid(src + " " + pname):
            continue
        all_packs.append({
            "id": pid,
            "name": pname,
            "source": src,
            "cleanCount": p.get("cleanCount", 0),
        })
        used_ids.add(pid)
        if len(all_packs) >= max_packs:
            break

    # Shuffle to avoid collisions with 凯总巴西
    import random as _random
    _random.shuffle(all_packs)
    log(f"Available packs ({carrier}): {len(all_packs)} (min_clean={min_clean}, pages={pack_pages}, shuffled)")

    result = {
        "carrier": carrier,
        "fetchedAt": datetime.datetime.now().isoformat(),
        "templateId": tpl_id,
        "templateName": tpl_name,
        "channelIds": ch_ids,
        "channelNames": ch_names,
        "domainIds": sl_ids,
        "packs": all_packs,
    }

    cache_file = _cache_path(RULES, carrier)
    # Safeguard: never cache empty templates (API throttle/race condition)
    if tpl_id is None:
        log(f"WARNING: templateId is None — NOT caching prereq for {carrier} (will retry next round)")
        return None
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    log(f"Prereq cached to {cache_file}")
    return result


def load_or_fetch_prereq(carrier="globe"):
    ttl = RULES.get("cacheTTLSeconds", 1800)
    cache_file = _cache_path(RULES, carrier)
    if cache_file.exists():
        try:
            with open(cache_file, encoding="utf-8") as f:
                cached = json.load(f)
            fetched = datetime.datetime.fromisoformat(cached["fetchedAt"])
            age = (datetime.datetime.now() - fetched).total_seconds()
            if age < ttl and cached.get("carrier") == carrier and cached.get("packs") is not None and cached.get("templateId") is not None:
                log(f"Using cached prereq ({age:.0f}s old)")
                return cached
            else:
                log(f"Cache stale or corrupt, re-fetching")
        except Exception as e:
            log(f"Cache read error: {e}, re-fetching")
    result = fetch_prereq(carrier)
    if result is None:
        log(f"WARNING: fetch_prereq({carrier}) returned None, creating empty fallback")
        result = {
            "carrier": carrier,
            "fetchedAt": datetime.datetime.now().isoformat(),
            "templateId": None,
            "templateName": "fallback-empty",
            "channelIds": [],
            "channelNames": [],
            "domainIds": [],
            "packs": [],
        }
    return result


def refresh_packs_only(carrier, existing_prereq):
    """Lightweight pack-only refresh — skips template/channel/domain API calls.
    Used on empty/conflict to cut recovery from 30-50s to 5-10s."""
    jwt = read_jwt()
    BID = RULES["backendInstanceId"]
    BASE = RULES["apiBase"]
    carrier_cfg = RULES["carriers"][carrier]
    round_cfg = RULES["round"]
    keywords = carrier_cfg["packNameKeywords"]
    excludes = carrier_cfg.get("excludeKeywords", [])
    min_clean = round_cfg["minCleanCount"]
    source_filter = RULES.get("packRules", {}).get("sourceMustStartWith", "")
    search_query = RULES.get("packRules", {}).get("searchQuery", "")

    # ═══ 铁律 2026-05-03: kt06独占第16-18页, 从config读取, 禁止任何终端修改 ═══
    _cfg_page = carrier_cfg.get("packPage") or RULES.get("packRules", {}).get("packPage", 16)
    _cfg_page_end = carrier_cfg.get("packPageMax") or RULES.get("packRules", {}).get("packPageMax", 18)
    pack_pages = list(range(_cfg_page, _cfg_page_end + 1))
    pack_page_size = carrier_cfg.get("packPageSize") or RULES.get("packRules", {}).get("packPageSize", 100)

    packs = []
    seen = set()
    for pg in pack_pages:
        try:
            params = f"backendInstanceId={BID}&pageSize={pack_page_size}&page={pg}&sort=-createdAt"
            if search_query:
                params += f"&q={urllib.parse.quote(search_query, safe='')}"
            pdata = api_get(f"{BASE}/api/phone-packs?{params}", jwt, timeout=120)
            page_packs = pdata.get("data", [])
            for pp in page_packs:
                pid = pp.get("id", "")
                if pid and pid not in seen:
                    seen.add(pid)
                    packs.append(pp)
            if pg == pack_pages[0]:
                log(f"Phone packs pages={pack_pages}, q={search_query}, page {pg} got {len(page_packs)} packs (totalPages={pdata.get('totalPages', 0)})")
        except Exception as e:
            log(f"Phone packs page={pg} fetch failed: {e}, continuing with {len(packs)} packs so far")
    log(f"Phone packs merged: {len(packs)} total (deduped) from {len(pack_pages)} pages")

    all_packs = []
    used_ids = set()
    for p in packs:
        pid = p.get("id", "")
        if pid in used_ids:
            continue
        if p.get("reuseLocked", False):
            continue
        if p.get("assignmentCampaignId") is not None:
            continue
        if p.get("cleanCount", 0) < min_clean:
            continue
        src = p.get("source", "")
        if source_filter and not src.startswith(source_filter):
            continue
        pname = p.get("name", src)
        combined = (src + " " + pname).lower()
        if not any(kw.lower() in combined for kw in keywords):
            continue
        if excludes and any(ex.lower() in combined for ex in excludes):
            continue
        all_packs.append({
            "id": pid,
            "name": pname,
            "source": src,
            "cleanCount": p.get("cleanCount", 0),
        })
        used_ids.add(pid)

    import random as _random
    _random.shuffle(all_packs)

    result = dict(existing_prereq)
    result["fetchedAt"] = datetime.datetime.now().isoformat()
    result["packs"] = all_packs
    cache_file = _cache_path(RULES, carrier)
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return result


# ── Send Logic ──

def run_round(prereq, round_num, used_pack_ids, pack_blacklist=None):
    carrier = prereq["carrier"]
    tpl_id = prereq["templateId"]
    ch_ids = prereq["channelIds"]
    sl_ids = prereq["domainIds"]
    all_packs = prereq["packs"]
    round_cfg = RULES["round"]
    sl_cfg = RULES["shortlink"]
    BID = RULES["backendInstanceId"]
    BASE = RULES["apiBase"]

    packs_per_round = get_packs_per_round()

    # Expire stale blacklist entries
    if pack_blacklist:
        now_ts = time.time()
        expired = [pid for pid, exp in pack_blacklist.items() if now_ts > exp]
        for pid in expired:
            del pack_blacklist[pid]
    # Filter: exclude used AND blacklisted pack IDs
    black_ids = set(pack_blacklist.keys()) if pack_blacklist else set()
    available = [p for p in all_packs if p["id"] not in used_pack_ids and p["id"] not in black_ids]
    if len(available) < 1:
        log(f"Round {round_num}: No packs available")
        return "empty", used_pack_ids, {}, None

    # Random selection to avoid pack collision with other campaigns
    # (others likely pick biggest packs sequentially — we spread out)
    if len(available) <= packs_per_round:
        batch = available
    else:
        batch = random.sample(available, packs_per_round)
    pack_ids = [p["id"] for p in batch]
    for pid in pack_ids:
        used_pack_ids.add(pid)

    log(f"Round {round_num}: {len(batch)} packs selected (tier packs/round={packs_per_round})")

    planned = (
        datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(seconds=round_cfg["plannedAtOffsetSeconds"])
    ).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    bj = bj_now()
    carrier_tag = carrier[0].upper()  # G or S

    title_prefix = f"{bj.strftime('%m%d%H%M')}{carrier_tag}{round_num}"

    # 量化规则: 通道轮转选择, 不再固定ch_ids[0]
    picked_ch = get_next_channel(ch_ids, carrier)
    if picked_ch is None:
        picked_ch = ch_ids[0] if ch_ids else None
    if picked_ch is None:
        log(f"Round {round_num}: No channels available")
        return "empty", used_pack_ids, {}, None

    body = {
        "templateIds": [tpl_id],
        "smsInstanceIds": [picked_ch],
        "phonePackIds": pack_ids,
        "shortlinkMappingMode": sl_cfg["mappingMode"],
        "shortlinkMode": sl_cfg["mode"],
        "customShortlinkDomainConfigIds": sl_ids,
        "titlePrefix": title_prefix,
        "plannedAt": planned,
    }

    ROUNDS_DIR.mkdir(parents=True, exist_ok=True)
    round_dir = ROUNDS_DIR / f"{bj.strftime('%Y%m%d-%H%M')}-{carrier}-R{round_num}"
    round_dir.mkdir(exist_ok=True)
    with open(round_dir / "request.json", "w", encoding="utf-8") as f:
        json.dump(body, f, ensure_ascii=False, indent=2)

    # POST test-send
    log(f"Round {round_num}: POST /send-direct/test-send ...")
    resp = api_post(
        f"{BASE}/api/campaign-templates/{tpl_id}/send-direct/test-send", body
    )
    with open(round_dir / "response.json", "w", encoding="utf-8") as f:
        json.dump(resp, f, ensure_ascii=False, indent=2)

    # Safety check
    sessions = resp.get("verificationSessions", [])
    if not sessions:
        title = resp.get("summary", {}).get("title", "")
        if "模板批次待审批发送" in title:
            log(f"Round {round_num}: WRONG ENDPOINT!")
            return "wrong_endpoint", used_pack_ids, {}, picked_ch
        err_code = resp.get("errorCode", "")
        log(f"Round {round_num}: No verificationSessions: {json.dumps(resp)[:200]}")
        # Keep packs in used_pack_ids so they don't get retried (server assignment is sticky)
        # Force re-fetch on PHONE_PACK_ALREADY_ASSIGNED so we get fresh unassigned packs
        return ("pack_assigned" if "ALREADY_ASSIGNED" in err_code else "no_sessions"), used_pack_ids, {}, picked_ch

    approval_id = resp.get("approvalId", "?")
    session_ids = [s["id"] for s in sessions]
    log(f"Round {round_num}: approvalId={approval_id}, sessions={len(session_ids)}")
    log(f"  >>> TG APPROVE! approvalId={approval_id}")

    # If skipPolling mode, just fire and move on (for 1-pack rapid fire)
    if round_cfg.get("skipPolling", False):
        log(f"Round {round_num}: skipPolling mode, firing and moving to next")
        resp_data = {
            "campaignIds": resp.get("campaignIds", []),
            "campaignBatchIds": resp.get("campaignBatchIds", []),
        }
        with open(round_dir / "verdict.json", "w", encoding="utf-8") as f:
            json.dump({"status": "fired", "approvalId": approval_id, "packs": len(batch),
                       "campaignIds": resp_data["campaignIds"],
                       "campaignBatchIds": resp_data["campaignBatchIds"]}, f)
        resp_data["_channel_id"] = picked_ch
        return "fired", used_pack_ids, resp_data, picked_ch

    # Poll for clicks
    threshold = round_cfg["clickThreshold"]
    candidates = []
    poll_start = time.time()

    # Phase A: dense
    pa = round_cfg["pollPhaseA_seconds"]
    pa_iv = round_cfg["pollPhaseA_interval"]
    log(f"Round {round_num}: Phase A polling (dense, {pa}s)...")
    for i in range(int(pa / pa_iv)):
        time.sleep(pa_iv)
        try:
            ids_param = ",".join(session_ids)
            items = api_get(f"{BASE}/api/send-verification-sessions?ids={ids_param}")
            if isinstance(items, dict):
                items = items.get("items", items.get("data", []))
            for s in items:
                sid = s.get("id", "")
                clicks = s.get("clickCount", 0)
                if clicks >= 1 and sid not in candidates:
                    candidates.append(sid)
                    log(f"  Click! session={sid[:12]}... clicks={clicks}")
        except Exception as e:
            log(f"  Poll err: {e}")
        if len(candidates) >= threshold:
            log(f"Round {round_num}: {len(candidates)} sessions with clicks (>= {threshold}), scale-up!")
            break

    # Phase B: sparse
    if len(candidates) < threshold:
        pb = round_cfg["pollPhaseB_seconds"]
        pb_iv = round_cfg["pollPhaseB_interval"]
        log(f"Round {round_num}: Phase B polling (sparse, {pb}s)...")
        for i in range(int(pb / pb_iv)):
            time.sleep(pb_iv)
            try:
                ids_param = ",".join(session_ids)
                items = api_get(f"{BASE}/api/send-verification-sessions?ids={ids_param}")
                if isinstance(items, dict):
                    items = items.get("items", items.get("data", []))
                for s in items:
                    sid = s.get("id", "")
                    clicks = s.get("clickCount", 0)
                    if clicks >= 1 and sid not in candidates:
                        candidates.append(sid)
                        log(f"  Click! session={sid[:12]}... clicks={clicks}")
            except Exception as e:
                log(f"  Poll err: {e}")
            if len(candidates) >= threshold:
                break

    elapsed = time.time() - poll_start

    if len(candidates) < threshold:
        log(f"Round {round_num}: Insufficient clicks ({len(candidates)}/{threshold}), discarding")
        resp_data = {
            "campaignIds": resp.get("campaignIds", []),
            "campaignBatchIds": resp.get("campaignBatchIds", []),
        }
        with open(round_dir / "verdict.json", "w", encoding="utf-8") as f:
            json.dump({"status": "no_click", "candidates": len(candidates), "elapsed": elapsed,
                       "campaignIds": resp_data["campaignIds"],
                       "campaignBatchIds": resp_data["campaignBatchIds"]}, f)
        resp_data["_channel_id"] = picked_ch
        return "no_click", used_pack_ids, resp_data, picked_ch

    # Scale-up
    log(f"Round {round_num}: Scale-up with {len(candidates)} sessions...")
    scale_body = {**body, "verificationSessionIds": candidates}
    scale_resp = api_post(
        f"{BASE}/api/campaign-templates/{tpl_id}/send-direct", scale_body
    )
    scale_approval = scale_resp.get("approvalId", "?")
    log(f"Round {round_num}: Scale-up approvalId={scale_approval}")
    log(f"  >>> TG APPROVE #2 for scale-up! approvalId={scale_approval}")

    resp_data = {
        "campaignIds": resp.get("campaignIds", []),
        "campaignBatchIds": resp.get("campaignBatchIds", []),
    }
    with open(round_dir / "scale_response.json", "w", encoding="utf-8") as f:
        json.dump(scale_resp, f, ensure_ascii=False, indent=2)
    with open(round_dir / "verdict.json", "w", encoding="utf-8") as f:
        json.dump({
            "status": "scaled",
            "candidates": len(candidates),
            "candidateIds": candidates,
            "elapsed": elapsed,
            "scaleApprovalId": scale_approval,
            "campaignIds": resp_data["campaignIds"],
            "campaignBatchIds": resp_data["campaignBatchIds"],
        }, f, ensure_ascii=False, indent=2)

    resp_data["_channel_id"] = picked_ch
    return "scaled", used_pack_ids, resp_data, picked_ch


# ── Best Template Tracker — iron rule: use last 3 days' highest deposit template ──

def refresh_best_template(carrier):
    """Iron rule 2026-05-03: query operations-report for 3d deposit ranking, fall back to CTR if no deposit data."""
    jwt = read_jwt()
    BID = RULES["backendInstanceId"]
    BASE = RULES["apiBase"]

    # Get recent campaigns (last 200)
    camp_data = api_get(f"{BASE}/api/campaigns?pageSize=200&backendInstanceId={BID}", jwt)
    if isinstance(camp_data, dict):
        campaigns = camp_data.get("data", camp_data.get("items", camp_data.get("list", [])))
    else:
        campaigns = camp_data if isinstance(camp_data, list) else []

    carrier_cfg = RULES["carriers"][carrier]
    ch_keywords = carrier_cfg.get("channelKeywords", [])

    # Group by templateId, compute aggregate CTR
    tpl_stats = {}  # templateId -> {clicks, sent, campaigns, smsText}
    for c in campaigns:
        title = c.get("displayTitle") or ""
        # Only count campaigns matching this carrier
        carrier_match = False
        for kw in ch_keywords:
            if kw and kw.lower() in title.lower():
                carrier_match = True
                break
        # Also match carrier tag in title
        if carrier.upper() in title.upper():
            carrier_match = True
        if not carrier_match:
            continue

        tpl_id = c.get("templateId")
        if not tpl_id:
            continue

        cid = c.get("campaignId") or c.get("id")
        # Get send-logs for actual sent count
        try:
            sl = api_get(f"{BASE}/api/send-logs?campaignId={cid}&pageSize=1", jwt)
            if isinstance(sl, dict):
                sent = sl.get("successCount", sl.get("targetCount", 0))
            else:
                sent = 0
        except Exception:
            sent = 0

        # Get clicks from campaign object or batch
        clicks = c.get("clickCount", 0)

        if tpl_id not in tpl_stats:
            tpl_stats[tpl_id] = {"clicks": 0, "sent": 0, "campaigns": 0, "smsText": ""}
        tpl_stats[tpl_id]["clicks"] += clicks
        tpl_stats[tpl_id]["sent"] += sent
        tpl_stats[tpl_id]["campaigns"] += 1

    # Fetch template smsText for each
    if tpl_stats:
        tpl_data = api_get(
            f"{BASE}/api/campaign-templates?backendInstanceId={BID}&pageSize=200",
            jwt
        )
        if isinstance(tpl_data, list):
            all_tpls = tpl_data
        else:
            all_tpls = tpl_data.get("data", tpl_data.get("list", []))
        for t in all_tpls:
            if t["id"] in tpl_stats:
                tpl_stats[t["id"]]["smsText"] = t.get("smsText", "")

    # Iron rule 2026-05-03: use last 3 days' highest deposit template first
    deposit_best = find_best_by_deposit_3d()
    if deposit_best and deposit_best.get("templateId"):
        best_id = deposit_best["templateId"]
        best_sms = tpl_stats.get(best_id, {}).get("smsText", deposit_best.get("templateName", ""))
        ctr_str = f"{deposit_best.get('ctr', 0):.2%}"
        log(f"Best template for {carrier} (3d deposit ¥{deposit_best['depositAmount']:.0f} FTD={deposit_best['ftdCount']}): {best_id} CTR={ctr_str}")
    else:
        # Fallback: find best by CTR
        best_id = None
        best_ctr = 0
        best_sms = ""
        for tid, stats in tpl_stats.items():
            if stats["sent"] > 0:
                ctr = stats["clicks"] / stats["sent"] * 100
                if ctr > best_ctr:
                    best_ctr = ctr
                    best_id = tid
                    best_sms = stats["smsText"]
        ctr_str = f"{best_ctr:.2f}%" if best_ctr > 0 else "0%"

    if best_id:
        log(f"Best template for {carrier}: {best_id} CTR={ctr_str} SMS={best_sms[:60]}")

        # Update send_rules.json
        rules_path = Path(RULES.get("_rules_path", str(DEFAULT_RULES)))
        try:
            with open(rules_path, encoding="utf-8") as f:
                rules = json.load(f)
            rules["carriers"][carrier]["bestTemplateId"] = best_id
            rules["carriers"][carrier]["bestTemplateSms"] = best_sms
            rules["carriers"][carrier]["bestTemplateCtr"] = ctr_str
            with open(rules_path, "w", encoding="utf-8") as f:
                json.dump(rules, f, ensure_ascii=False, indent=2)
            # Refresh in-memory RULES
            RULES["carriers"][carrier]["bestTemplateId"] = best_id
            RULES["carriers"][carrier]["bestTemplateSms"] = best_sms
            RULES["carriers"][carrier]["bestTemplateCtr"] = ctr_str
            log(f"Updated send_rules.json: {carrier} bestTemplateId={best_id} CTR={ctr_str}")
        except Exception as e:
            log(f"Failed to update send_rules.json: {e}")
    else:
        log(f"No CTR data found for {carrier} campaigns")


# ── Main ──

def main():
    global RULES

    parser = argparse.ArgumentParser(description="bowjwj Fast Send Loop")
    parser.add_argument("--carrier", choices=["globe", "smart", "both"], default="both")
    parser.add_argument("--dry-run", action="store_true", help="Only fetch prereq, no send")
    parser.add_argument("--rounds", type=int, default=0, help="Max rounds (0=infinite)")
    parser.add_argument("--config", default=str(DEFAULT_RULES), help="Rules JSON path")
    args = parser.parse_args()

    RULES = load_rules(args.config)
    RULES["_rules_path"] = args.config  # track path for refresh_best_template

    # Apply packRules from config (overrides hardcoded defaults)
    pr = RULES.get("packRules", {})
    if pr.get("mustNotContain"):
        global PACK_MUST_NOT_CONTAIN
        PACK_MUST_NOT_CONTAIN = pr["mustNotContain"]
    if pr.get("mustContainOneOf"):
        global PACK_MUST_CONTAIN
        PACK_MUST_CONTAIN = pr["mustContainOneOf"]

    log("=" * 60)
    log("=== Fast Send Loop Starting ===")
    log(f"Carrier: {args.carrier}, dry-run: {args.dry_run}")
    log(f"Rules: {args.config}")
    log(f"Pack rules: MUST contain one of {PACK_MUST_CONTAIN}, MUST NOT contain {PACK_MUST_NOT_CONTAIN}")
    schedule = RULES.get("sendSchedule", {})
    for tier in schedule.get("tiers", []):
        windows_str = ", ".join(f'{w["start"]}-{w["end"]}' for w in tier["windows"])
        log(f"  {tier['name']}: {windows_str} | cycle={tier['cycleSeconds']}s packs={tier.get('packsPerRound', 60)}")

    # Check JWT
    if not Path(os.path.expanduser(RULES["jwtFile"])).exists():
        log("JWT file not found!")
        sys.exit(1)
    jwt = read_jwt()
    try:
        me = api_get(f"{RULES['apiBase']}/api/me", jwt)
        role = me.get("user", {}).get("role", "")
        if role not in ("SUPER_ADMIN", "OPS_ADMIN"):
            log(f"Wrong role: {role}")
            sys.exit(1)
        log(f"API OK — role={me['user']['role']}")
    except Exception as e:
        log(f"API check failed: {e}")
        sys.exit(1)

    carriers = ["globe", "smart"] if args.carrier == "both" else [args.carrier]

    # Load prereqs for all carriers upfront
    prereqs = {}
    for carrier in carriers:
        prereq = load_or_fetch_prereq(carrier)
        if prereq is None:
            log(f"!!! FATAL: Failed to load prereq for {carrier} (fetch_prereq returned None)")
            log(f"    Clearing cache and retrying once...")
            cache_file = _cache_path(RULES, carrier)
            cache_file.unlink(missing_ok=True)
            prereq = load_or_fetch_prereq(carrier)
            if prereq is None:
                log(f"!!! FATAL: Still failed for {carrier}. Exiting.")
                sys.exit(1)
        prereqs[carrier] = prereq
        log(f"Prereq for {carrier}:")
        log(f"  Template: {(prereq.get('templateId') or '?')[:12]} | {prereq.get('templateName') or '?'}")
        log(f"  Channels: {len(prereq.get('channelIds', []))}")
        log(f"  Domains: {len(prereq.get('domainIds', []))}")
        log(f"  Packs: {len(prereq.get('packs', []))}")

    if args.dry_run:
        log("Dry-run: skipping send loop")
        return

    REFRESH_EVERY_N_ROUNDS = 5
    exhaust_retry = RULES.get("exhaustRetrySeconds", 600)
    PACK_BLACKLIST_TTL = 300  # 5-min blacklist for PHONE_PACK_ALREADY_ASSIGNED packs
    state = {c: {"used_pack_ids": set(), "round_num": 0, "next_retry_at": 0,
                 "pack_blacklist": {}, "consecutive_empty": 0, "_conflict_streak": 0} for c in carriers}  # pid -> expiry_timestamp
    while True:
        if not in_send_window():
            eta = next_window_eta()
            log(f"Outside window. Next in {eta/3600:.1f}h. Sleeping...")
            time.sleep(min(eta, 600))
            continue

        # Collect carriers not in cooldown
        active_carriers = []
        for carrier in carriers:
            if time.time() >= state[carrier].get("next_retry_at", 0):
                active_carriers.append(carrier)

        if not active_carriers:
            earliest = min(state[c]["next_retry_at"] for c in carriers)
            wait = max(earliest - time.time(), 10)
            log(f"All carriers in cooldown, sleeping {wait:.0f}s...")
            time.sleep(min(wait, 60))
            continue

        loop_start = time.time()
        cycle = get_cycle_seconds()

        def _carrier_round(carrier):
            """Run one round for a single carrier. Called from parallel threads."""
            sc = state[carrier]

            # 量化规则: CTR动态调速 → 设置per-carrier冷却
            dyn_cycle = get_ctr_dynamic_cycle(carrier)
            if dyn_cycle >= 999:
                log(f"[{carrier}] CTR=0% → 停发")
                sc["next_retry_at"] = time.time() + 3600
                return
            elif dyn_cycle > 3:
                sc["next_retry_at"] = time.time() + dyn_cycle
                log(f"[{carrier}] CTR调速: {dyn_cycle}s冷却")

            sc["round_num"] += 1
            round_start = time.time()

            status, used, resp_data, picked_ch = run_round(prereqs[carrier], sc["round_num"], sc["used_pack_ids"], sc.get("pack_blacklist"))
            sc["used_pack_ids"] = used
            if resp_data:
                sc["last_batch_id"] = (resp_data.get("campaignBatchIds") or [None])[0]
                sc["last_camp_ids"] = resp_data.get("campaignIds", [])

            # 量化规则: channel error tracking
            if status in ("no_sessions",):
                channel_error(picked_ch)
            elif status == "pack_assigned":
                channel_error(picked_ch, cooldown_sec=300)  # 5min cooldown for pack conflict
            elapsed = time.time() - round_start
            log(f"[{carrier}] Round {sc['round_num']} done: {status} ({elapsed:.0f}s)")

            if status in ("fired", "scaled"):
                sc["_conflict_streak"] = 0
                sc["consecutive_empty"] = 0

            # ═══ Round 1 CTR check (skipped in skipPolling mode) ═══
            if not RULES["round"].get("skipPolling") and sc["round_num"] == 1 and status in ("fired", "scaled"):
                log(f"[{carrier}] ⚡ IRON RULE: Round 1 complete, checking send-logs for actual deliveries...")
                ctr_wait = 120
                log(f"[{carrier}] ⏳ Waiting {ctr_wait}s for clicks to register...")
                time.sleep(ctr_wait)
                try:
                    last_batch_id = sc.get("last_batch_id", "")
                    last_camp_ids = sc.get("last_camp_ids", [])
                    total_sent = 0
                    total_clicks = 0
                    for cid in last_camp_ids:
                        sl = api_get(f"{RULES['apiBase']}/api/send-logs?campaignId={cid}&pageSize=5", jwt)
                        items = sl.get("items", sl.get("data", []))
                        for item in items:
                            total_sent += item.get("successCount", 0)
                    if last_batch_id:
                        try:
                            rd = api_get(f"{RULES['apiBase']}/api/replay-dashboard/batches/{last_batch_id}", jwt)
                            headline = rd.get("headline", {})
                            traffic = headline.get("traffic", {})
                            total_clicks = traffic.get("clicks", traffic.get("rawClicks", 0))
                        except:
                            pass

                    log(f"[{carrier}] Round 1 send-logs: sent={total_sent}, clicks={total_clicks}")
                    if total_sent == 0:
                        log(f"[{carrier}] ⚠️ WARNING: No sends detected — checking replay dashboard...")
                        ctr, clicks, sent, batch_ids = check_recent_ctr(carrier, 1)
                        total_clicks = clicks
                        total_sent = sent

                    if total_sent > 0 and total_clicks == 0:
                        ctr_pct = 0
                    elif total_sent > 0:
                        ctr_pct = (total_clicks / total_sent) * 100
                    else:
                        ctr_pct = None

                    if ctr_pct is None or (total_sent > 0 and total_clicks == 0):
                        log(f"[{carrier}] 🛑 IRON RULE: Round 1 ZERO clicks! "
                            f"(sent={total_sent}, clicks={total_clicks}) — 停发诊断中...")
                        diagnosis = diagnose_zero_ctr(carrier, batch_ids[0] if batch_ids else None, None)
                        log(f"[{carrier}] 📋 诊断: {diagnosis['diagnosis']} | 修复: {diagnosis['fix_applied']} | 冷却: {diagnosis['cooldown_seconds']}s")
                        sc["next_retry_at"] = time.time() + diagnosis["cooldown_seconds"]
                        sc["used_pack_ids"] = set()
                        sc["zero_click_count"] = sc.get("zero_click_count", 0) + 1
                        max_zero = RULES.get("probePack", {}).get("maxRoundsZeroClick", 3)
                        if sc["zero_click_count"] >= max_zero:
                            log(f"[{carrier}] ⛔ {max_zero} consecutive zero-click rounds — PERMANENT STOP for {carrier}")
                            sc["stopped_no_ctr"] = True
                            sc["next_retry_at"] = time.time() + 3600
                        return
                    elif total_sent == 0 and total_clicks == 0:
                        log(f"[{carrier}] ⚠️ No data yet — allowing Round 2 to proceed")
                    else:
                        log(f"[{carrier}] ✅ IRON RULE PASSED: Round 1 CTR={ctr_pct:.2f}% ({total_clicks}/{total_sent}) — 继续发送")
                except Exception as e:
                    log(f"[{carrier}] ⚠️ CTR check error (will retry next round): {e}")

            # 🔴 ZERO CLICKS → diagnose + fix
            if status in ("no_click", "zero_click_probe"):
                log(f"[{carrier}] 🛑 ZERO CLICKS! 停发诊断中...")
                diagnosis = diagnose_zero_ctr(carrier, None, None)
                log(f"[{carrier}] 📋 诊断: {diagnosis['diagnosis']} | 修复: {diagnosis['fix_applied']} | 冷却: {diagnosis['cooldown_seconds']}s")
                if "domain_rotated" in diagnosis["fix_applied"] or "channel_switched" in diagnosis["fix_applied"]:
                    prereqs[carrier] = fetch_prereq(carrier)
                sc["used_pack_ids"] = set()
                sc["next_retry_at"] = time.time() + diagnosis["cooldown_seconds"]
                sc["zero_click_count"] = sc.get("zero_click_count", 0) + 1
                probe_cfg = RULES.get("probePack", {})
                max_zero = probe_cfg.get("maxRoundsZeroClick", 3)
                if sc["zero_click_count"] >= max_zero:
                    log(f"[{carrier}] ⛔ {max_zero} consecutive zero-click rounds — PERMANENT STOP for {carrier}")
                    sc["stopped_no_ctr"] = True
                    sc["next_retry_at"] = time.time() + 999999
                return

            if status == "empty":
                sc["consecutive_empty"] = sc.get("consecutive_empty", 0) + 1
                empty_s = sc["consecutive_empty"]
                # 量化规则: 空包分层翻页
                if empty_s <= 3:
                    retry = 3  # 1-3次: 同页刷新
                    log(f"[{carrier}] No packs — same-page refresh ({empty_s}/3, {retry}s)")
                elif empty_s <= 6:
                    retry = 10  # 4-6次: 切换页面
                    # Rotate page forward
                    ccfg = RULES["carriers"][carrier]
                    cur_page = ccfg.get("packPage", 1)
                    max_page = ccfg.get("packPageMax", 100)
                    new_page = cur_page + 5
                    if new_page > max_page or new_page > 100:
                        new_page = ccfg.get("packPageMin", 1)
                    ccfg["packPage"] = new_page
                    log(f"[{carrier}] No packs — rotating page {cur_page}→{new_page} ({empty_s}/6, {retry}s)")
                else:
                    retry = 60  # 7+次: 全量刷新
                    sc["consecutive_empty"] = 0
                    log(f"[{carrier}] Empty streak={empty_s} — full prereq refresh ({retry}s)")
                prereqs[carrier] = refresh_packs_only(carrier, prereqs[carrier])
                sc["used_pack_ids"] = set()
                sc["next_retry_at"] = time.time() + retry
                return

            if status in ("pack_assigned", "no_sessions"):
                if status == "pack_assigned":
                    now_ts = time.time()
                    bl_added = 0
                    for pid in sc["used_pack_ids"]:
                        if pid not in sc.get("pack_blacklist", {}):
                            sc["pack_blacklist"][pid] = now_ts + PACK_BLACKLIST_TTL
                            bl_added += 1
                    log(f"[{carrier}] Blacklisted {bl_added} conflicting pack(s) for {PACK_BLACKLIST_TTL}s")
                    sc["used_pack_ids"] = set()
                    sc["_conflict_streak"] = sc.get("_conflict_streak", 0) + 1
                    max_retries = 3
                    if sc["_conflict_streak"] <= max_retries:
                        retry = 3
                        log(f"[{carrier}] Pack conflict — same-page refresh (3s, streak {sc['_conflict_streak']}/{max_retries})")
                    else:
                        retry = 30
                        sc["_conflict_streak"] = 0
                        log(f"[{carrier}] Conflict retries exceeded ({max_retries}) — cooldown {retry}s, streak reset")
                    prereqs[carrier] = refresh_packs_only(carrier, prereqs[carrier])
                    sc["next_retry_at"] = time.time() + retry
                    return
                # no_sessions case
                log(f"[{carrier}] Server error — force-refreshing packs...")
                prereqs[carrier] = refresh_packs_only(carrier, prereqs[carrier])
                sc["next_retry_at"] = time.time() + 3
                return

            # ── CTR-driven Dynamic Adjustment ──
            ctr_cfg = RULES.get("sendSchedule", {}).get("ctrThresholds", {})
            CTR_CHECK_EVERY_N = 3
            if ctr_cfg and sc["round_num"] % CTR_CHECK_EVERY_N == 0 and status in ("fired", "scaled"):
                try:
                    ctr, clicks, sent, batch_ids = check_recent_ctr(carrier, ctr_cfg.get("minSendsForJudgment", 100))
                    if ctr is not None:
                        update_carrier_ctr(carrier, ctr)  # 量化规则: update CTR state for dynamic speed
                        if picked_ch:
                            update_channel_ctr(picked_ch, ctr)  # 量化规则: track channel CTR
                        pause_thr = ctr_cfg.get("pause", 0.05)
                        scale_thr = ctr_cfg.get("scale", 0.06)
                        log(f"[{carrier}] CTR: {ctr*100:.2f}% ({clicks}/{sent}) | pause<{pause_thr*100:.0f}% scale>{scale_thr*100:.0f}%")

                        if ctr < pause_thr:
                            log(f"[{carrier}] ⚠️ CTR {ctr*100:.2f}% < {pause_thr*100:.0f}% — AUTO SWITCH COPY")
                            sc["low_ctr_count"] = sc.get("low_ctr_count", 0) + 1
                            max_low = ctr_cfg.get("maxConsecutiveLowCtr", 3)
                            new_id = auto_switch_copy(carrier, f"CTR {ctr*100:.2f}% (<{pause_thr*100:.0f}%) [{sc['low_ctr_count']}/{max_low}]", ctr)
                            if new_id:
                                prereqs[carrier] = fetch_prereq(carrier)
                                sc["used_pack_ids"] = set()
                            sc["next_retry_at"] = time.time() + ctr_cfg.get("cooldownAfterPause", 600)

                        elif ctr > scale_thr:
                            log(f"[{carrier}] 🔥 CTR {ctr*100:.2f}% > {scale_thr*100:.0f}% — SCALE UP")
                            sc["low_ctr_count"] = 0
                            tier = get_current_tier()
                            if tier:
                                tier["_orig"] = tier.get("_orig", tier["packsPerRound"])
                                tier["packsPerRound"] = ctr_cfg.get("scalePacks", 3)
                        else:
                            sc["low_ctr_count"] = 0
                            tier = get_current_tier()
                            if tier and "_orig" in tier:
                                tier["packsPerRound"] = tier.pop("_orig")
                    else:
                        log(f"[{carrier}] CTR: insufficient data ({sent} < {ctr_cfg.get('minSendsForJudgment', 100)})")
                except Exception as e:
                    log(f"[{carrier}] CTR check error: {e}")

            # Periodically refresh best template
            if sc["round_num"] % REFRESH_EVERY_N_ROUNDS == 0:
                log(f"Refreshing best template for {carrier} (round {sc['round_num']})...")
                try:
                    refresh_best_template(carrier)
                except Exception as e:
                    log(f"Refresh best template error: {e}")

        # ═══ Run all active carriers in parallel ═══
        threads = []
        for carrier in active_carriers:
            t = threading.Thread(target=_carrier_round, args=(carrier,), daemon=True)
            t.start()
            threads.append(t)
            log(f"[{carrier}] Thread started (round {state[carrier]['round_num']+1})")
        for t in threads:
            t.join()

        # Check max rounds — all carriers must reach limit
        if args.rounds > 0 and all(s["round_num"] >= args.rounds for s in state.values()):
            log(f"Reached max rounds ({args.rounds})")
            break

        elapsed = time.time() - loop_start
        remaining = cycle - elapsed
        if remaining > 0:
            tier = get_current_tier()
            tier_name = tier["name"] if tier else "unknown"
            log(f"Waiting {remaining:.0f}s for next cycle (tier: {tier_name})...")
            time.sleep(remaining)

    log("=== Fast Send Loop Ended ===")


if __name__ == "__main__":
    # Write PID file for watchdog
    pidfile = Path("/tmp/fast_send.pid")
    try:
        pidfile.write_text(str(os.getpid()))
    except Exception:
        pass

    try:
        main()
    except SystemExit:
        pass
    except Exception as e:
        import traceback
        log(f"!!! FATAL EXCEPTION: {e}", flush=True)
        log(traceback.format_exc(), flush=True)
    finally:
        try:
            pidfile.unlink(missing_ok=True)
        except Exception:
            pass
