#!/usr/bin/env python3
"""
计划管理监控 — 每5分钟检查凯总巴西漏包并自动发送
==================================================
规则:
  1. 凯总巴西: campaignId 含 "凯总"
  2. 漏包: launchStatus = launched/draft/scheduled/created
  3. 发送: launched→send直接发, draft→先launch再send
  4. 通道: Globe/Dito→yo家Globe, Smart/TNT→yo家Smart
  5. 间隔: 0.5s/条, 锁文件防重叠
  6. 频率: 每5分钟 (cron: */5 * * * *)
"""

import json, os, subprocess, sys, time
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ============ 配置 ============
JWT_FILE = Path.home() / ".hermes" / "state" / "bowjwj" / ".jwt"
BASE_URL = "https://bowjwj.cc"
BACKEND_ID = "c7ee7c4c-ce0a-49c9-880a-9315d07c07b6"
LOG_FILE = Path.home() / "Desktop" / "计划管理监控.log"
LOCK_FILE = Path("/tmp/bowjwj_plan_monitor.lock")

GLOBE_CHANNELS = [
    "04596485-8dd0-4eae-930b-0ba0f60b11bb",
    "a1e0747e-ced3-4279-8752-5c126b00d61b",
    "699847d5-83d0-4abe-9c2c-72e5381729c0",
    "dc70d6e8-02b6-4531-b89e-6458d0509241",
    "f61e1f3f-5978-437e-a3aa-04dc1ce37904",
    "f49e287b-4d9d-407c-8bd5-81f6f2e05021",
    "8b029e9a-5cc1-44b3-92c0-4dd130d37dc2",
    "e062ada6-edd9-4e26-a58d-e529712a0d0f",
]
SMART_CHANNELS = [
    "05b39523-544c-4e13-ae7b-08e27cb6dc1c",
    "165b9ca3-3220-4383-bcc2-901941ffcfd3",
    "feca8a41-5cc9-434e-be2f-757c4ddb964f",
    "c40db47c-2080-42fa-b2df-0aa9b77ad5f6",
    "df51fa52-5336-443b-9e8c-194297cbb394",
    "0a30f2d0-ac30-4681-b0dc-70626e1e4109",
]

KAZONG_KEYWORD = "凯总"
UNSENT_STATUSES = ("launched", "scheduled", "draft", "created")
BJ = timezone(timedelta(hours=8))

# ============ 工具函数 ============

def log(msg):
    now = datetime.now(BJ).strftime("%m-%d %H:%M:%S")
    line = f"[{now}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except: pass

def api_call(jwt, method, path, body=None, timeout=20):
    cmd = [
        "curl", "-sS", "-k", "-X", method,
        "--connect-timeout", "8", "--max-time", str(timeout),
        "-H", f"Authorization: Bearer {jwt}",
        "-H", "Content-Type: application/json",
        "-w", "\n%{http_code}",
    ]
    if body is not None:
        cmd += ["-d", json.dumps(body)]
    cmd.append(f"{BASE_URL}{path}")
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout + 5)
        out = r.stdout.decode("utf-8")
        parts = out.rsplit("\n", 1)
        if len(parts) == 2:
            try: return int(parts[1].strip()), parts[0]
            except: pass
        return 0, out
    except Exception as e:
        return 0, str(e)

def detect_carrier(campaign):
    pack = campaign.get("phonePack") or {}
    src = (pack.get("source", "") + " " + campaign.get("phonePackTitle", "")).lower()
    if "globe" in src or "dito" in src: return "globe"
    if "smart" in src or "tnt" in src: return "smart"
    return "unknown"

def acquire_lock():
    if LOCK_FILE.exists():
        try:
            pid = int(LOCK_FILE.read_text().strip())
            os.kill(pid, 0)
            return False
        except (ValueError, OSError):
            pass
    LOCK_FILE.write_text(str(os.getpid()))
    return True

def release_lock():
    try: LOCK_FILE.unlink()
    except: pass

# ============ 主逻辑 ============

def scan_unsent(jwt):
    """快速扫描"""
    unsent = []
    page = 1
    no_kazong_pages = 0

    while True:
        status, body = api_call(jwt, "GET",
            f"/api/campaigns?backendInstanceId={BACKEND_ID}&pageSize=200"
            f"&page={page}&sort=createdAt&order=desc")
        if status != 200:
            page += 1
            continue
        try: data = json.loads(body)
        except: break

        items = data.get("items", [])
        if not items: break

        found = 0
        for c in items:
            if KAZONG_KEYWORD not in c.get("campaignId", ""): continue
            ls = c.get("launchStatus", "")
            if ls not in UNSENT_STATUSES: continue
            found += 1
            unsent.append({"id": c["id"], "carrier": detect_carrier(c), "status": ls})

        if found == 0:
            no_kazong_pages += 1
            if no_kazong_pages >= 5: break
        else:
            no_kazong_pages = 0

        total_pages = data.get("totalPages", 0)
        if page >= total_pages: break
        page += 1
        time.sleep(0.08)

    return unsent

def send_all(jwt, campaigns):
    if not campaigns:
        return {"globe": 0, "smart": 0}, 0

    gci = sci = 0
    sent = {"globe": 0, "smart": 0}
    fail = 0
    start = time.time()

    for i, c in enumerate(campaigns):
        carrier = c["carrier"]
        if carrier == "unknown": continue

        ch = (GLOBE_CHANNELS[gci % len(GLOBE_CHANNELS)]
              if carrier == "globe"
              else SMART_CHANNELS[sci % len(SMART_CHANNELS)])
        cid = c["id"]

        if c["status"] in ("draft", "created", "scheduled"):
            s2, b2 = api_call(jwt, "POST", f"/api/campaigns/{cid}/launch")
            if s2 >= 400:
                fail += 1
                continue
            time.sleep(0.25)

        s3, b3 = api_call(jwt, "POST", f"/api/campaigns/{cid}/send", {"smsInstanceId": ch})
        if s3 == 202:
            sent[carrier] += 1
            if carrier == "globe": gci += 1
            else: sci += 1
        elif "ALREADY_SENT" not in (b3 or ""):
            fail += 1

        total = sent["globe"] + sent["smart"]
        if total > 0 and (total % 100 == 0 or i == len(campaigns) - 1):
            elapsed = time.time() - start
            rate = total / elapsed if elapsed > 0 else 0
            log(f"  进度: {total}/{len(campaigns)} ({sent['globe']}G+{sent['smart']}S) "
                f"速率={rate:.0f}/s 失败={fail}")

        time.sleep(0.5)

    return sent, fail

def main():
    if not acquire_lock():
        log("上一轮仍在运行, 跳过")
        sys.exit(0)

    try:
        jwt = JWT_FILE.read_text().strip()
    except Exception as e:
        log(f"FATAL: JWT读取失败: {e}")
        release_lock()
        sys.exit(1)

    start = datetime.now(BJ)
    log("=" * 50)
    log("计划管理监控启动")

    unsent = scan_unsent(jwt)
    sc = Counter(c["status"] for c in unsent)
    cc = Counter(c["carrier"] for c in unsent)
    log(f"扫描: {len(unsent)}漏包 状态={dict(sc)} Globe={cc.get('globe',0)} Smart={cc.get('smart',0)}")

    sent, fail = send_all(jwt, unsent)

    elapsed = (datetime.now(BJ) - start).total_seconds()
    total = sent["globe"] + sent["smart"]
    log(f"完成: {total}发送({sent['globe']}G+{sent['smart']}S) {fail}失败 耗时{elapsed:.0f}s")
    log("=" * 50)

    release_lock()

if __name__ == "__main__":
    main()
