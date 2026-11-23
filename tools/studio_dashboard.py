#!/usr/bin/env python3
"""Video Studio local dashboard: stdlib-only, GitHub Codespace command/log bridge.

Commands:
  py -3 studio_dashboard.py serve --open
  py -3 studio_dashboard.py run --title "Smoke test" --stage TEST --target codespace --command "echo PROGRESS:100"
  py -3 studio_dashboard.py status

Run commands only from an authorized user request. Dashboard binds to localhost.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen
import uuid
import webbrowser

# Dashboard code is versioned in repo/tools, while mutable control-plane
# state and approved MP4s remain under the authorized Windows studio root.
_SOURCE = Path(__file__).resolve()
BASE = (_SOURCE.parents[2] if _SOURCE.parent.name == "tools"
        and _SOURCE.parents[1].name == "repo" else _SOURCE.parent)
DATA = BASE / "dashboard_data"
RUNS = DATA / "runs"
CURRENT = DATA / "current.json"
PROJECT_STATE = BASE / "projects" / "kauthar_v3" / "project_state.json"
V31_QA = BASE / "outputs" / "kauthar_v31_qa.json"
V31_VIDEO = BASE / "outputs" / "kauthar_minimal_v31_prediction_720p.mp4"
FINAL_VIDEO = BASE / "outputs" / "kauthar_minimal_v31_1080_private_AUDIO_NORMALIZED.mp4"
FINAL_QA = BASE / "outputs" / "kauthar_v31_final1080_qa.json"
FINAL_LOUD = BASE / "outputs" / "kauthar_v31_final1080_loudness_report.json"
REVIEW_A = BASE / "outputs" / "review" / "kauthar_headline_A_720p_private.mp4"
REVIEW_B = BASE / "outputs" / "review" / "kauthar_headline_B_720p_private.mp4"
AB_QA_DIR = BASE / "outputs" / "qa" / "kauthar_headline_ab" / "20261123_003348_511e386"
BATCH5_DIR = BASE / "outputs" / "review" / "kauthar_batch5_20261123"
BATCH5_MANIFEST = BATCH5_DIR / "batch_manifest.json"
CODESPACE_RECEIPTS = DATA / "verified_codespace_deliveries"
DEFAULT_CS = "psychic-space-winner-p7gr9q5vj4gq27rq7"
PORT = 8765
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
PROGRESS = re.compile(r"(?:PROGRESS\s*[:=]\s*|Rendering frames[^\d]*)(\d{1,3})(?:\.\d+)?\s*%?", re.I)
FRAME = re.compile(r"(?:Rendered|Rendering)\s+(\d+)\s*/\s*(\d+)", re.I)
STAGE_LINE = re.compile(r"^STAGE:\s*([a-z][a-z0-9_-]{1,48})$", re.I)
METRIC_LINE = re.compile(r"^METRIC:\s*([a-z][a-z0-9_.-]{1,48})\s*=\s*(-?\d+(?:\.\d+)?)$", re.I)
GATE_LINE = re.compile(r"^GATE:\s*([a-z][a-z0-9_.-]{1,48})\s*=\s*(PASS|FAIL|BLOCKED|PENDING)$", re.I)
CS_CACHE = {"at": 0.0, "value": "UNKNOWN"}
RUN_LOCK = threading.Lock()
BROWSER_LOCK = threading.Lock()
BROWSER_VIEWERS = {}
BROWSER_LAST_OPEN_CLAIM = {"at": 0.0}
BROWSER_VIEWER_TTL_SECONDS = 65
BROWSER_LAUNCH_COOLDOWN_SECONDS = 20


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def ensure_dirs():
    RUNS.mkdir(parents=True, exist_ok=True)


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, TypeError):
        return default


def atomic_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    try:
        for attempt in range(12):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                if attempt == 11:
                    raise
                time.sleep(min(0.03 * (2 ** attempt), 0.5))
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def log_event(run_dir, level, message, **extra):
    item = {"ts": now(), "level": level, "message": str(message)[:2500], **extra}
    with (run_dir / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(item, ensure_ascii=False) + "\n")


def update_run(run_dir, **patch):
    path = run_dir / "checkpoint.json"
    with RUN_LOCK:
        state = read_json(path, {}) or {}
        state.update(patch)
        state["updated_at"] = now()
        atomic_json(path, state)
        return state


def cs_status(name):
    t = time.monotonic()
    if t - CS_CACHE["at"] < 25:
        return CS_CACHE["value"]
    try:
        cp = subprocess.run(
            ["gh", "codespace", "list", "--json", "name,state", "--limit", "30"],
            capture_output=True, text=True, timeout=9, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        entries = json.loads(cp.stdout) if cp.returncode == 0 else []
        result = next((e.get("state", "UNKNOWN") for e in entries if e.get("name") == name), "NOT_FOUND")
    except (OSError, subprocess.TimeoutExpired, ValueError):
        result = "UNREACHABLE"
    CS_CACHE.update({"at": t, "value": result})
    return result


def status_payload():
    ensure_dirs()
    pointer = read_json(CURRENT, {}) or {}
    run_id = pointer.get("run_id", "")
    run_dir = RUNS / run_id if re.fullmatch(r"[A-Za-z0-9_-]{1,80}", run_id) else None
    run = read_json(run_dir / "checkpoint.json", {}) if run_dir else {}
    if run and run.get("status") == "RUNNING":
        try:
            age = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(run["updated_at"])).total_seconds()
            if age > 25:
                run = dict(run, status="STALE", last_message="Worker heartbeat lost; verify process before retry")
        except (ValueError, KeyError, TypeError):
            pass
    events = []
    if run_dir:
        try:
            # Files are modest for pilot runs. UI displays only the newest 130 lines.
            with (run_dir / "events.jsonl").open("rb") as stream:
                stream.seek(0, 2)
                total = stream.tell()
                stream.seek(max(0, total - 120000))
                chunk = stream.read().decode("utf-8", errors="replace")
            if total > 120000:
                chunk = chunk.split("\n", 1)[-1]
            for line in chunk.splitlines()[-130:]:
                try:
                    events.append(json.loads(line))
                except ValueError:
                    continue
        except OSError:
            pass
    history = []
    for folder in sorted(RUNS.iterdir(), key=lambda p: p.name, reverse=True)[:15]:
        if folder.is_dir():
            r = read_json(folder / "checkpoint.json")
            if r:
                history.append({k: r.get(k) for k in ("run_id", "title", "status", "stage", "progress", "updated_at")})
    proj = read_json(PROJECT_STATE, {}) or {}
    final = proj.get("final_export_1080p", {}) or {}
    qa = read_json(FINAL_QA if FINAL_VIDEO.is_file() else V31_QA, {}) or {}
    loud = read_json(FINAL_LOUD, {}) or {}
    ab_a = read_json(AB_QA_DIR / "A" / "technical_qa.json", {}) or {}
    ab_b = read_json(AB_QA_DIR / "B" / "technical_qa.json", {}) or {}
    audio_a = read_json(AB_QA_DIR / "A" / "audio_qa.json", {}) or {}
    audio_b = read_json(AB_QA_DIR / "B" / "audio_qa.json", {}) or {}
    ab_ready = (REVIEW_A.is_file() and REVIEW_B.is_file()
                and ab_a.get("technical_status") == "PASS"
                and ab_b.get("technical_status") == "PASS"
                and audio_a.get("signal_gate") == "PASS"
                and audio_b.get("signal_gate") == "PASS")
    batch = read_json(BATCH5_MANIFEST, {}) or {}
    batch_files = batch.get("files") if isinstance(batch.get("files"), list) else []
    batch_ready = (
        batch.get("status") == "TECHNICAL_PASS_PRIVATE_ONLY"
        and batch.get("distinct_source_count") == 5
        and len(batch_files) == 5
        and len({f.get("source_video_id") for f in batch_files}) == 5
        and all((BATCH5_DIR / f.get("filename", "")).is_file() for f in batch_files)
    )
    receipts=sorted(CODESPACE_RECEIPTS.glob("cs_*.json"),
                    key=lambda p:p.stat().st_mtime,reverse=True) if CODESPACE_RECEIPTS.is_dir() else []
    receipt=read_json(receipts[0],{}) if receipts else {}
    cs_items=receipt.get("files",{}) if isinstance(receipt,dict) else {}
    cs_folder=Path(receipt.get("output_dir","")) if isinstance(receipt,dict) else Path("")
    cs_count=len(cs_items) if isinstance(cs_items,dict) else 0
    cs_ready=bool(
        receipt.get("status")=="VERIFIED_SHA256_AT_DELIVERY"
        and receipt.get("count")==cs_count
        and 1<=cs_count<=20
        and cs_folder.is_dir()
        and all(
            (cs_folder/v.get("filename","")).is_file()
            and (cs_folder/v.get("filename","")).stat().st_size==v.get("bytes")
            for v in cs_items.values()
        )
    )
    return {
        "now": now(),
        "codespace": {"name": (run or {}).get("codespace") or DEFAULT_CS,
                      "state": cs_status((run or {}).get("codespace") or DEFAULT_CS)},
        "run": run or None,
        "events": events,
        "history": history,
        "existing": {
            "project_id": proj.get("project_id"),
            "phase": "HUMAN_REVIEW" if (cs_ready or batch_ready or ab_ready) else proj.get("phase", "UNKNOWN"),
            "active_variant": (("CODESPACE_MIXUE_SEMANTIC_V2_PRIVATE"
                                if "mixue_semantic_v2" in cs_items
                                else f"CODESPACE_{cs_count}_VERIFIED_MP4_PRIVATE") if cs_ready
                               else ("KAUTHAR_5_DISTINCT_720_PRIVATE" if batch_ready
                               else ("KAUTHAR_HEADLINE_A_B_720_PRIVATE" if ab_ready
                               else proj.get("active_variant", "UNKNOWN")))),
            "project_state_preview": proj.get("preview_v31", "UNKNOWN"),
            "qa_technical": "PASS_AT_DELIVERY" if cs_ready else ("PASS" if (batch_ready or ab_ready) else qa.get("technical_status", "UNKNOWN")),
            "qa_creative": "PENDING_HUMAN_REVIEW" if (cs_ready or batch_ready or ab_ready)
                           else qa.get("creative_status", "UNKNOWN"),
            "qa_duration": None if cs_ready else qa.get("duration"),
            "video_exists": cs_ready or batch_ready or ab_ready or FINAL_VIDEO.is_file() or V31_VIDEO.is_file(),
            "video_resolution": (f"720x1280 ({cs_count} Codespace SHA-verified MP4{'s' if cs_count != 1 else ''})" if cs_ready
                                 else ("720x1280 (5 distinct review videos)" if batch_ready
                                 else ("720x1280 (2 review variants)" if ab_ready
                                 else ("1080x1920" if FINAL_VIDEO.is_file() else "720x1280")))),
            "final_status": ("CODESPACE_TECHNICAL_PASS_PRIVATE" if cs_ready
                            else ("FIVE_DISTINCT_PRIVATE_TECHNICAL_PASS" if batch_ready
                            else ("TECHNICAL_PASS_PRIVATE_REVIEW_ONLY" if ab_ready
                            else final.get("status", "NOT_YET_VERIFIED")))),
            "audio_lufs": (None if cs_ready else (round(sum(f.get("lufs", -16) for f in batch_files)/5,2)
                           if batch_ready else (audio_a.get("audio_integrated_lufs") if ab_ready
                           else (loud.get("second_pass") or {}).get("output_i")))),
            "rights": "UNCLEARED" if cs_ready else proj.get("rights_status", "UNKNOWN"),
            "possible_state_drift": bool((FINAL_VIDEO.is_file() and not final.get("status"))
                                          or (V31_VIDEO.is_file() and not FINAL_VIDEO.is_file()
                                          and qa.get("technical_status") == "PASS"
                                          and proj.get("preview_v31") == "NOT_YET_VERIFIED")),
        },
    }


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Video Studio / Control Room</title>
<style>
:root{color-scheme:dark;--bg:#090f18;--panel:#111b29;--panel2:#162336;--border:#263448;--ink:#ecf2ff;--muted:#90a2b9;--cyan:#5eead4;--lime:#b8f28e;--red:#ff8a9b;--yellow:#f6c973}
*{box-sizing:border-box}body{margin:0;font:14px/1.5 Inter,Segoe UI,system-ui,sans-serif;color:var(--ink);background:radial-gradient(ellipse at 70% 0%,#17304b 0%,transparent 43%),var(--bg)}
.wrap{max-width:1440px;margin:auto;padding:27px 32px 55px}.top{display:flex;justify-content:space-between;align-items:center;gap:15px;margin-bottom:25px;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:13px;font-size:13px;letter-spacing:2px;font-weight:800}.brandmark{background:var(--cyan);color:#082323;padding:9px 12px;border-radius:11px;font-weight:900}
.sub{color:var(--muted);font-size:12px;letter-spacing:0}.chip{display:inline-flex;gap:8px;align-items:center;border:1px solid var(--border);background:#152235;padding:8px 11px;border-radius:40px;color:#cbd9e9;font-size:12px}
.dot{height:8px;width:8px;background:var(--yellow);border-radius:99px;box-shadow:0 0 0 4px #f6c97317}.dot.good{background:var(--cyan);box-shadow:0 0 0 4px #5eead420}
h1{font-size:clamp(29px,4vw,44px);letter-spacing:-1.5px;margin:0 0 8px;line-height:1.12}h2{font-size:16px;margin:0 0 14px;letter-spacing:-.2px}.muted{color:var(--muted)}.hero{background:linear-gradient(110deg,#16293d,#122032 62%,#172b2e);border:1px solid #315069;border-radius:22px;padding:29px;display:flex;justify-content:space-between;gap:20px;align-items:center;margin-bottom:18px}
.pretitle{font-size:10px;letter-spacing:2px;font-weight:800;color:var(--cyan);margin-bottom:11px}.hero p{margin:0;color:#a9bed1}.bigpercent{font-size:55px;font-weight:800;letter-spacing:-3px;line-height:1;text-align:right}.percentlabel{font-size:11px;color:var(--muted);text-align:right;margin-top:7px}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:13px;margin-bottom:18px}.stat,.panel{border:1px solid var(--border);background:#101a28e8;border-radius:18px}.stat{padding:20px}.stathead{font-size:11px;text-transform:uppercase;letter-spacing:1.1px;color:var(--muted)}.statval{font-size:24px;font-weight:700;margin-top:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.statfoot{color:var(--muted);font-size:11px}
.cols{display:grid;grid-template-columns:1.1fr .9fr;gap:16px}.panel{padding:22px;margin-bottom:16px}.bar{height:9px;background:#25374a;border-radius:20px;overflow:hidden;margin:13px 0 10px}.fill{background:linear-gradient(90deg,#3a98b2,#5eead4);height:100%;width:0;transition:width .45s}.pill{border-radius:7px;background:#18362f;color:var(--cyan);padding:4px 8px;font-size:11px;font-weight:700;display:inline-block}
.pill.fail{background:#482631;color:var(--red)}.pill.warn{background:#3e3529;color:var(--yellow)}
.flex{display:flex;justify-content:space-between;align-items:center;gap:10px}.divider{height:1px;background:var(--border);margin:17px 0}.detail{display:grid;grid-template-columns:100px 1fr;gap:7px;margin-top:12px;color:#c0d2e2;font-size:12px}.detail b{color:var(--muted);font-weight:500}
.logbar{display:flex;gap:8px;align-items:center;justify-content:space-between;margin-bottom:12px}.logbar select{background:var(--panel2);border:1px solid var(--border);border-radius:9px;color:var(--ink);padding:7px}
.console{background:#080e16;border:1px solid #223344;border-radius:12px;height:390px;overflow:auto;padding:12px;font:12px/1.6 Consolas,'Courier New',monospace}.logline{display:grid;grid-template-columns:65px 49px 1fr;gap:8px;border-bottom:1px solid #182432;padding:4px 0;overflow-wrap:anywhere}.logline .time{color:#6e86a0}.logline .level{color:#7adcca}.logline.error .level{color:var(--red)}.logline.warning .level{color:var(--yellow)}
.history{display:flex;flex-direction:column;gap:10px}.historyrow{display:grid;grid-template-columns:1fr auto;gap:8px;padding:11px 0;border-bottom:1px solid var(--border)}.tiny{font-size:11px;color:var(--muted)}.foot{color:#7e94aa;font-size:12px;margin-top:15px}
@media(max-width:900px){.stats{grid-template-columns:repeat(2,1fr)}.cols{grid-template-columns:1fr}.wrap{padding:19px}.hero{padding:23px}}
@media(max-width:540px){.hero{align-items:start}.bigpercent{font-size:36px}.stats{grid-template-columns:repeat(2,1fr)}.stat{padding:14px}.statval{font-size:18px}}
</style></head><body><div class="wrap">
<div class="top"><div class="brand"><div class="brandmark">VS</div><div>VIDEO STUDIO <span style="color:var(--cyan)">/</span> CONTROL ROOM<div class="sub">LOCAL OBSERVABILITY · PRIVATE</div></div></div><div class="chip"><i id="connectdot" class="dot"></i><span id="cs">Checking Codespace...</span></div></div>
<section class="hero"><div><div class="pretitle">LIVE EXECUTION</div><h1 id="name">Ready to monitor</h1><p id="description">Start a tracked task from ChatGPT / Remote Desktop Commander.</p></div><div><div class="bigpercent" id="pct">—</div><div class="percentlabel" id="pctlabel">WAITING FOR TASK</div></div></section>
<section class="stats">
<div class="stat"><div class="stathead">Task status</div><div id="status" class="statval">IDLE</div><div class="statfoot" id="statussub">No tracked job yet</div></div>
<div class="stat"><div class="stathead">Current stage</div><div class="statval" id="stage">—</div><div class="statfoot">Checkpoint stage</div></div>
<div class="stat"><div class="stathead">Elapsed</div><div class="statval" id="elapsed">0:00</div><div class="statfoot">Wall-clock time</div></div>
<div class="stat"><div class="stathead">Log alerts</div><div class="statval" id="errors">0</div><div class="statfoot">Matched error messages; job status uses exit code</div></div></section>
<div class="cols"><div>
<section class="panel"><div class="flex"><h2>Execution progress</h2><span id="badge" class="pill warn">WAITING</span></div>
<div class="bar"><div class="fill" id="progressbar"></div></div><div class="flex"><span class="muted" id="progresslabel">Indeterminate until worker emits real progress</span><span class="tiny" id="runid">—</span></div>
<div class="divider"></div><div class="detail"><b>Worker</b><span id="target">—</span><b>Last event</b><span id="last">—</span><b>Updated</b><span id="updated">—</span></div></section>
<section class="panel"><div class="logbar"><h2 style="margin:0">Live process logs</h2><select id="filter"><option value="all">All events</option><option value="error">Errors</option><option value="warning">Warnings</option></select></div><div class="console" id="console"><span class="muted">No events yet</span></div></section>
</div><div>
<section class="panel"><h2>Current private review evidence</h2><div class="flex"><span class="muted">Technical QA</span><span id="qatech" class="pill warn">UNKNOWN</span></div><div class="divider"></div>
<div class="detail"><b>Variant</b><span id="variant">—</span><b>Rendered video</b><span id="video">—</span><b>Final status</b><span id="finalstatus">—</span><b>Audio LUFS</b><span id="audiolufs">—</span><b>Project phase</b><span id="phase">—</span><b>Rights</b><span id="rights">—</span><b>Creative QA</b><span id="creative">—</span></div><p class="tiny" id="drift" style="margin-top:15px">Checking checkpoint alignment.</p></section>
<section class="panel"><h2>Process KPI & gates</h2><div id="kpis"><span class="muted">Awaiting METRIC / GATE signals from worker</span></div></section>
<section class="panel"><h2>Recent jobs</h2><div class="history" id="history"><span class="muted">No tracked runs yet</span></div></section></div></div>
<div class="foot">Live updates every 2 seconds · Only jobs launched through the tracked runner emit live logs. Existing QA is displayed as separate evidence. Codespace stopping interrupts its running jobs, not this local dashboard.</div>
</div><script>
const $ = id => document.getElementById(id);
const fmt = s => {if(!s)return "—";const n=Number(s);return Math.floor(n/60)+":"+String(Math.floor(n%60)).padStart(2,"0")};
const text = (id,value) => {$(id).textContent=value==null?"—":String(value)};
let lastCount=-1;let lastRun="";
function pill(el, status) {el.textContent=status||"UNKNOWN";el.className="pill"+(/FAIL|ERROR|INTERRUPT/.test(status||"")?" fail":(/PENDING|UNKNOWN|WAIT|BLOCK|STALE/.test(status||"")?" warn":""))}
async function refresh(){
try{
 const res=await fetch("/api/status",{cache:"no-store"});if(!res.ok)throw new Error("HTTP "+res.status);
 const d=await res.json();const cs=d.codespace||{};text("cs",(cs.state||"UNKNOWN")+" · "+(cs.name||"Codespace"));
 $("connectdot").className="dot"+(cs.state==="Available"?" good":"");
 const r=d.run||{};text("name",r.title||"Ready to monitor");text("description",r.title?"Codespace / local task execution with persisted logs":"Start a tracked task from ChatGPT / Remote Desktop Commander.");
 text("status",r.status||"IDLE");text("statussub",r.exit_code==null?"No exit code yet":"Exit code: "+r.exit_code);text("stage",r.stage||"—");
 let elapsed=r.elapsed_sec||0;if(r.status==="RUNNING"&&r.started_at){elapsed=Math.max(0,(Date.now()-Date.parse(r.started_at))/1000)}
 text("elapsed",fmt(elapsed));text("errors",r.error_count||0);
 const pct=r.status==="PASS"?100:((r.progress!=null&&Number.isFinite(Number(r.progress)))?Math.max(0,Math.min(100,Number(r.progress))):null);
 text("pct",pct===null?"—":Math.round(pct)+"%");text("pctlabel",r.status==="PASS"?"TASK COMPLETED":(pct===null?"NO NUMERIC PROGRESS":"REPORTED BY WORKER"));$("progressbar").style.width=pct===null?"0%":pct+"%";
 text("progresslabel",r.status==="PASS"?"Process exited successfully; technical QA gates remain separate":(pct===null?"Indeterminate: waiting for actual progress signal":"Progress reported by running task"));
 text("runid",r.run_id?"RUN "+r.run_id.slice(-8):"—");text("target",r.target? r.target.toUpperCase()+" / "+(r.codespace||"Windows"):"—");
 text("last",r.last_message||"—");text("updated",r.updated_at||"—");pill($("badge"),r.status||"WAITING");
 const e=d.existing||{};pill($("qatech"),e.qa_technical);text("variant",e.active_variant);text("phase",e.phase);
 text("video",e.video_exists?(e.video_resolution+" MP4 present"):"No local MP4");text("creative",e.qa_creative);
 text("finalstatus",e.final_status);text("audiolufs",e.audio_lufs==null?"—":e.audio_lufs+" LUFS");text("rights",e.rights);
 text("drift",e.possible_state_drift?"Checkpoint drift: V3.1 QA PASS + MP4 exists but project state says NOT_YET_VERIFIED":"Project and QA evidence read independently");
 const k=$("kpis");k.replaceChildren();Object.entries(r.gates||{}).forEach(([name,value])=>{const row=document.createElement("div");row.className="flex";row.style.marginBottom="10px";const label=document.createElement("span");label.className="muted";label.textContent=name;const v=document.createElement("span");pill(v,value);row.append(label,v);k.append(row)});Object.entries(r.measurements||{}).forEach(([name,value])=>{const row=document.createElement("div");row.className="flex";row.style.marginBottom="10px";const label=document.createElement("span");label.className="muted";label.textContent=name;const v=document.createElement("strong");v.textContent=String(value);row.append(label,v);k.append(row)});if(!k.children.length)k.textContent="No machine-readable quality metrics yet";
 const h=$("history");h.replaceChildren();(d.history||[]).forEach(x=>{const row=document.createElement("div");row.className="historyrow";const info=document.createElement("div");const title=document.createElement("div");title.textContent=x.title||x.run_id;const sub=document.createElement("div");sub.className="tiny";sub.textContent=(x.stage||"—")+" · "+(x.updated_at||"");info.append(title,sub);const state=document.createElement("span");pill(state,x.status);row.append(info,state);h.append(row)});if(!h.children.length)h.textContent="No tracked runs yet";
 const filter=$("filter").value;const filtered=(d.events||[]).filter(x=>filter==="all"||String(x.level).toLowerCase()===filter);
 const log=$("console");const wasBottom=log.scrollTop+log.clientHeight>=log.scrollHeight-70;
 log.replaceChildren();filtered.forEach(x=>{const row=document.createElement("div");row.className="logline "+String(x.level||"").toLowerCase();const t=document.createElement("span");t.className="time";t.textContent=(x.ts||"").slice(11,19);const l=document.createElement("span");l.className="level";l.textContent=String(x.level||"").toUpperCase().slice(0,5);const m=document.createElement("span");m.textContent=x.message||"";row.append(t,l,m);log.append(row)});if(!filtered.length)log.textContent="No matching events";if(wasBottom)log.scrollTop=log.scrollHeight;
}catch(e){text("cs","Dashboard API unavailable");$("connectdot").className="dot";}}
const viewerId = ("viewer_" + (
  (globalThis.crypto && crypto.randomUUID)
    ? crypto.randomUUID().replaceAll("-", "")
    : (Date.now().toString(36) + Math.random().toString(36).slice(2))
)).slice(0,79);
async function heartbeat(){
  try {
    await fetch("/api/browser-heartbeat", {
      method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({viewer_id:viewerId}),keepalive:true
    });
  } catch (_) {}
}
window.addEventListener("pagehide", () => {
  navigator.sendBeacon("/api/browser-close",
    new Blob([JSON.stringify({viewer_id:viewerId})],{type:"application/json"}));
});
$("filter").addEventListener("change",refresh);
heartbeat();setInterval(heartbeat,5000);refresh();setInterval(refresh,2000);
</script></body></html>"""


def claim_browser_open():
    """Claim the right to open a tab only if no live dashboard viewer exists."""
    req = Request(
        "http://127.0.0.1:" + str(PORT) + "/api/browser-claim",
        data=b"{}", headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=2) as response:
            return bool(json.loads(response.read(512)).get("open_browser"))
    except (OSError, ValueError, TypeError):
        # Do not guess that there is no existing tab if the server is unreachable.
        return False


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        return

    def do_POST(self):
        origin = self.headers.get("Origin")
        if origin and origin != "http://127.0.0.1:" + str(PORT):
            self.send_error(403, "Unexpected origin")
            return
        if self.path not in ("/api/browser-heartbeat", "/api/browser-close", "/api/browser-claim"):
            self.send_error(404)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 <= size <= 1024:
                self.send_error(413)
                return
            payload = json.loads(self.rfile.read(size) or b"{}")
        except (ValueError, UnicodeDecodeError):
            self.send_error(400)
            return
        viewer = payload.get("viewer_id", "")
        if self.path != "/api/browser-claim" and not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", viewer):
            self.send_error(400, "Invalid viewer ID")
            return
        with BROWSER_LOCK:
            moment = time.monotonic()
            for sid, last in list(BROWSER_VIEWERS.items()):
                if moment - last > BROWSER_VIEWER_TTL_SECONDS:
                    del BROWSER_VIEWERS[sid]
            if self.path == "/api/browser-heartbeat":
                BROWSER_VIEWERS[viewer] = moment
                result = {"ok": True, "active_viewers": len(BROWSER_VIEWERS)}
            elif self.path == "/api/browser-close":
                BROWSER_VIEWERS.pop(viewer, None)
                result = {"ok": True, "active_viewers": len(BROWSER_VIEWERS)}
            else:
                eligible = (
                    not BROWSER_VIEWERS
                    and moment - BROWSER_LAST_OPEN_CLAIM["at"] >= BROWSER_LAUNCH_COOLDOWN_SECONDS
                )
                if eligible:
                    BROWSER_LAST_OPEN_CLAIM["at"] = moment
                result = {"open_browser": eligible, "active_viewers": len(BROWSER_VIEWERS)}
        body = json.dumps(result).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/status":
            body = json.dumps(status_payload(), ensure_ascii=False).encode("utf-8")
            typ = "application/json; charset=utf-8"
        elif self.path in ("/", "/index.html"):
            body = PAGE.encode("utf-8")
            typ = "text/html; charset=utf-8"
        elif self.path == "/health":
            body = b"OK"
            typ = "text/plain"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", typ)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve(open_browser=False):
    ensure_dirs()
    url = "http://127.0.0.1:" + str(PORT)
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError as exc:
        print("Dashboard port is busy:", exc)
        return 1
    print("Studio dashboard:", url, flush=True)
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever(poll_interval=0.3)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def is_server_up():
    try:
        with urlopen("http://127.0.0.1:" + str(PORT) + "/health", timeout=1) as response:
            return response.read(8) == b"OK"
    except Exception:
        return False


def spawn_detached(args, log_path):
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    with open(log_path, "a", encoding="utf-8") as output:
        proc = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve())] + args,
            cwd=str(BASE), stdin=subprocess.DEVNULL, stdout=output, stderr=output,
            creationflags=flags, close_fds=True
        )
    return proc.pid


def ensure_server():
    """Start dashboard only if needed; return True only on a fresh start."""
    ensure_dirs()
    if is_server_up():
        return False
    pid = spawn_detached(["serve"], DATA / "dashboard_server.log")
    for _ in range(25):
        if is_server_up():
            break
        time.sleep(0.2)
    if not is_server_up():
        raise RuntimeError("Dashboard server failed; check dashboard_data/dashboard_server.log")
    print("Local dashboard server PID:", pid)
    return True


def execute_worker(run_id):
    run_dir = RUNS / run_id
    request = read_json(run_dir / "request.json")
    if not request:
        raise RuntimeError("Missing worker request")
    state = update_run(run_dir, status="RUNNING", started_at=now(), progress=None)
    log_event(run_dir, "info", "Worker started; connecting to " + request["target"])
    if request["target"] == "codespace":
        cmd = ["gh", "codespace", "ssh", "-c", request["codespace"], "--", request["command"]]
    else:
        local_cmd = "$ErrorActionPreference = 'Stop'; " + request["command"] + "; if ($LASTEXITCODE -is [int] -and $LASTEXITCODE -ne 0) { exit $LASTEXITCODE }"
        cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", local_cmd]
    started = time.monotonic()
    heartbeat_stop = threading.Event()
    def heartbeat():
        while not heartbeat_stop.wait(4):
            update_run(run_dir, elapsed_sec=round(time.monotonic() - started, 1))
    threading.Thread(target=heartbeat, daemon=True).start()
    error_count = 0
    line_count = 0
    latest = ""
    percent = None
    last_progress_report = -1
    gates = {}
    measurements = {}
    current_stage = request["stage"]
    code = -1
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        with subprocess.Popen(cmd, cwd=str(BASE), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, encoding="utf-8", errors="replace", bufsize=1,
                              creationflags=flags) as process:
            for raw in process.stdout:
                line = ANSI.sub("", raw).strip()
                if not line:
                    continue
                line_count += 1
                stage_match = STAGE_LINE.fullmatch(line)
                gate_match = GATE_LINE.fullmatch(line)
                metric_match = METRIC_LINE.fullmatch(line)
                if stage_match:
                    current_stage = stage_match.group(1).upper()
                if gate_match:
                    gates[gate_match.group(1)] = gate_match.group(2).upper()
                if metric_match:
                    measurements[metric_match.group(1)] = float(metric_match.group(2))
                latest = line[:300]
                lvl = "error" if re.search(r"\b(error|failed|traceback|fatal)\b", line, re.I) else (
                    "warning" if re.search(r"\b(warn|deprecated)\b", line, re.I) else "info")
                if lvl == "error":
                    error_count += 1
                log_event(run_dir, lvl, line, stage=request["stage"])
                m = PROGRESS.search(line)
                if m:
                    percent = min(100.0, float(m.group(1)))
                else:
                    f = FRAME.search(line)
                    if f and int(f.group(2)):
                        percent = round(100 * int(f.group(1)) / int(f.group(2)), 1)
                report_progress = percent is not None and int(percent) > last_progress_report
                if line_count % 40 == 0 or report_progress or lvl == "error" or stage_match or gate_match or metric_match:
                    if report_progress:
                        last_progress_report = int(percent)
                    update_run(run_dir, last_message=latest, progress=percent, error_count=error_count,
                               gates=gates, measurements=measurements, stage=current_stage,
                               log_lines=line_count, elapsed_sec=round(time.monotonic() - started, 1))
            code = process.wait()
    except Exception as exc:
        latest = type(exc).__name__ + ": " + str(exc)
        error_count += 1
        log_event(run_dir, "error", latest)
    heartbeat_stop.set()
    elapsed = round(time.monotonic() - started, 2)
    result = "PASS" if code == 0 else "FAILED"
    # Completion percentage is not fabricated: a successful command without numeric signals stays indeterminate.
    update_run(run_dir, status=result, exit_code=code, finished_at=now(), elapsed_sec=elapsed,
               error_count=error_count + (1 if code != 0 else 0), log_lines=line_count,
               gates=gates, measurements=measurements, stage=current_stage,
               last_message=latest, progress=percent)
    atomic_json(run_dir / "metrics.json", {"run_id": run_id, "stage": request["stage"],
                                            "target": request["target"], "duration_sec": elapsed,
                                            "exit_code": code, "error_events": error_count + (1 if code != 0 else 0),
                                            "log_lines": line_count, "gates": gates,
                                            "measurements": measurements, "finished_at": now()})
    log_event(run_dir, "info" if code == 0 else "error", "Task " + result + " (exit " + str(code) + ")")


def run_task(args):
    # This Windows dashboard is control/monitor/transport only. Video encoding,
    # ASR and stock processing belong on Codespace. Refuse legacy local jobs.
    if re.search(r"render_kauthar_batch5\.py", args.command, re.I):
        raise ValueError("Legacy Windows batch renderer is disabled; use Codespace production_pipeline")
    if args.target == "local" and re.search(
        r"(?i)(?:\bffmpeg(?:\.exe)?\b|\bremotion\s+render\b|"
        r"\brender_guard\.py\b|\brender_kauthar_batch5\.py\b)",
        args.command,
    ):
        raise ValueError("Local video processing disabled; Windows may only dispatch Codespace jobs")
    ensure_server()
    run_id = dt.datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:7]
    rd = RUNS / run_id
    rd.mkdir(parents=True, exist_ok=False)
    request = {"title": args.title, "stage": args.stage.upper(), "target": args.target,
               "codespace": args.codespace, "command": args.command}
    atomic_json(rd / "request.json", request)
    atomic_json(rd / "checkpoint.json", {
        "run_id": run_id, "title": args.title, "stage": args.stage.upper(),
        "target": args.target, "codespace": args.codespace,
        "status": "PENDING", "progress": None, "error_count": 0, "log_lines": 0,
        "created_at": now(), "updated_at": now(), "last_message": "Queued by ChatGPT"
    })
    atomic_json(CURRENT, {"run_id": run_id})
    pid = spawn_detached(["_worker", "--run-id", run_id], rd / "worker.log")
    # A server can remain alive after its last browser tab is closed.
    # The active viewer heartbeat prevents duplicate opens; the atomic
    # server-side claim prevents concurrent jobs from opening multiple tabs.
    should_open = claim_browser_open()
    opened = bool(webbrowser.open("http://127.0.0.1:" + str(PORT))) if should_open else False
    print(json.dumps({"run_id": run_id, "worker_pid": pid,
                      "dashboard": "http://127.0.0.1:" + str(PORT),
                      "browser_open_claimed": should_open,
                      "browser_launch_requested": opened,
                      "checkpoint": str(rd / "checkpoint.json")}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Local dashboard + Codespace process monitor")
    sub = parser.add_subparsers(dest="mode", required=True)
    s = sub.add_parser("serve")
    s.add_argument("--open", action="store_true")
    run = sub.add_parser("run")
    run.add_argument("--title", required=True)
    run.add_argument("--stage", required=True)
    run.add_argument("--target", choices=("codespace", "local"), default="codespace")
    run.add_argument("--codespace", default=DEFAULT_CS)
    run.add_argument("--command", required=True, help="Explicit authorized command; never put secrets in args")
    w = sub.add_parser("_worker")
    w.add_argument("--run-id", required=True)
    sub.add_parser("status")
    opt = parser.parse_args()
    if opt.mode == "serve":
        return serve(opt.open)
    if opt.mode == "run":
        run_task(opt)
    elif opt.mode == "_worker":
        if not re.fullmatch(r"\d{8}_\d{6}_[a-f0-9]{7}", opt.run_id):
            parser.error("Invalid run id")
        execute_worker(opt.run_id)
    else:
        print(json.dumps(status_payload(), indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
