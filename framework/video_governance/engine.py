"""Fail-closed video stage governance and compact frame/asset lineage.

SQLite is the transactional control plane; native editors remain the workers.
No AI decision, paid API, or render is made by this module on its own.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import uuid

STAGES = ("SOURCE", "STORY_LOCK", "EDIT_PLAN", "EDIT", "RENDER",
          "TECH_QA", "STORY_QA", "HUMAN_REVIEW", "DELIVERY")
ROLE_SET = {"HOOK", "WANT", "TAPI", "SO", "PAYOFF", "CONTEXT"}
SCHEMA_VERSION = 1


class GateError(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise GateError(reason)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def connection(db):
    db = Path(db)
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db, timeout=30, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=30000")
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript("""
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY, created_at TEXT NOT NULL,
        story_version TEXT NOT NULL, max_variants INTEGER NOT NULL CHECK(max_variants BETWEEN 1 AND 32)
    );
    CREATE TABLE IF NOT EXISTS stages (
        project_id TEXT NOT NULL REFERENCES projects(id),
        stage TEXT NOT NULL, status TEXT NOT NULL,
        input_fingerprint TEXT, artifact_path TEXT, artifact_sha TEXT,
        started_at TEXT, finished_at TEXT, failure_reason TEXT,
        PRIMARY KEY(project_id, stage)
    );
    CREATE TABLE IF NOT EXISTS assets (
        project_id TEXT NOT NULL REFERENCES projects(id),
        asset_id TEXT NOT NULL, kind TEXT NOT NULL, path TEXT NOT NULL,
        sha256 TEXT NOT NULL, event_time TEXT, ingested_at TEXT NOT NULL,
        rights TEXT NOT NULL, PRIMARY KEY(project_id, asset_id)
    );
    CREATE TABLE IF NOT EXISTS clips (
        project_id TEXT NOT NULL, clip_id TEXT NOT NULL, asset_id TEXT NOT NULL,
        source_in_ms INTEGER NOT NULL, source_out_ms INTEGER NOT NULL,
        PRIMARY KEY(project_id, clip_id),
        FOREIGN KEY(project_id,asset_id) REFERENCES assets(project_id,asset_id),
        CHECK(source_in_ms >= 0 AND source_out_ms > source_in_ms)
    );
    CREATE TABLE IF NOT EXISTS beats (
        project_id TEXT NOT NULL REFERENCES projects(id), beat_id TEXT NOT NULL,
        story_version TEXT NOT NULL, role TEXT NOT NULL, PRIMARY KEY(project_id,beat_id)
    );
    CREATE TABLE IF NOT EXISTS renders (
        project_id TEXT NOT NULL REFERENCES projects(id), render_id TEXT NOT NULL,
        path TEXT NOT NULL, sha256 TEXT NOT NULL, fps_num INTEGER NOT NULL,
        fps_den INTEGER NOT NULL, frame_count INTEGER NOT NULL,
        created_at TEXT NOT NULL, PRIMARY KEY(project_id,render_id)
    );
    CREATE TABLE IF NOT EXISTS spans (
        project_id TEXT NOT NULL, render_id TEXT NOT NULL, span_id TEXT NOT NULL,
        beat_id TEXT NOT NULL, clip_id TEXT NOT NULL, layer TEXT NOT NULL,
        source_in_ms INTEGER NOT NULL, source_out_ms INTEGER NOT NULL,
        output_first_frame INTEGER NOT NULL, output_end_frame INTEGER NOT NULL,
        transform_id TEXT NOT NULL, transform_version TEXT NOT NULL,
        PRIMARY KEY(project_id,render_id,span_id),
        FOREIGN KEY(project_id,render_id) REFERENCES renders(project_id,render_id),
        FOREIGN KEY(project_id,beat_id) REFERENCES beats(project_id,beat_id),
        FOREIGN KEY(project_id,clip_id) REFERENCES clips(project_id,clip_id),
        CHECK(output_first_frame >= 0 AND output_end_frame > output_first_frame)
    );
    CREATE TABLE IF NOT EXISTS frame_evidence (
        project_id TEXT NOT NULL, render_id TEXT NOT NULL,
        frame_number INTEGER NOT NULL, type TEXT NOT NULL,
        path TEXT NOT NULL, sha256 TEXT NOT NULL,
        PRIMARY KEY(project_id,render_id,frame_number,type),
        FOREIGN KEY(project_id,render_id) REFERENCES renders(project_id,render_id)
    );
    CREATE TABLE IF NOT EXISTS variants (
        project_id TEXT NOT NULL REFERENCES projects(id),
        variant_id TEXT NOT NULL, body_sha256 TEXT NOT NULL, hook_sha256 TEXT NOT NULL,
        PRIMARY KEY(project_id,variant_id), UNIQUE(project_id,body_sha256,hook_sha256)
    );
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL,
        created_at TEXT NOT NULL, event TEXT NOT NULL, details TEXT NOT NULL
    );
    """)
    return con


def event(con, project, action, **data):
    con.execute("INSERT INTO events(project_id,created_at,event,details) VALUES (?,?,?,?)",
                (project, utc(), action, canonical(data)))


def stage_row(con, project, stage):
    return con.execute("SELECT * FROM stages WHERE project_id=? AND stage=?",
                       (project, stage)).fetchone()


def assets(con, project):
    return [dict(x) for x in con.execute(
        "SELECT asset_id,kind,sha256,path,rights FROM assets WHERE project_id=? ORDER BY asset_id",
        (project,))]


def fingerprint(con, project, stage):
    index = STAGES.index(stage)
    deps = []
    for name in STAGES[:index]:
        item = stage_row(con, project, name)
        require(item is not None and item["status"] == "PASS",
                "BLOCKED_DEPENDENCY:" + name)
        require(Path(item["artifact_path"]).is_file()
                and sha(item["artifact_path"]) == item["artifact_sha"],
                "STALE_DEPENDENCY:" + name)
        deps.append([name, item["artifact_sha"]])
    relevant = [a for a in assets(con, project)
                if stage not in {"SOURCE","STORY_LOCK"} or
                a["kind"] in {"SOURCE","TRANSCRIPT","REFERENCE"}]
    for a in relevant:
        require(Path(a["path"]).is_file() and sha(a["path"]) == a["sha256"],
                "STALE_ASSET:" + a["asset_id"])
    project_row = con.execute("SELECT story_version FROM projects WHERE id=?",
                              (project,)).fetchone()
    require(project_row is not None, "UNKNOWN_PROJECT")
    return hashlib.sha256(canonical({
        "stage": stage, "story_version": project_row["story_version"],
        "deps": deps, "assets": [[a["asset_id"], a["sha256"]] for a in relevant],
        "contract": SCHEMA_VERSION
    }).encode()).hexdigest()


def invalidate(con, project, start, reason):
    for name in STAGES[STAGES.index(start):]:
        con.execute("""UPDATE stages SET status='STALE',failure_reason=?
                    WHERE project_id=? AND stage=? AND status IN ('PASS','RUNNING')""",
                    (reason,project,name))
    event(con, project, "INVALIDATE", from_stage=start, reason=reason)


def add_asset(con, project, asset_id, kind, path, rights, event_time=None):
    path = Path(path).resolve()
    require(path.is_file() and path.stat().st_size, "ASSET_MISSING_OR_EMPTY")
    require(rights.strip(), "RIGHTS_STATUS_REQUIRED")
    require(kind in {"SOURCE","TRANSCRIPT","BROLL","AUDIO","IMAGE","REFERENCE"},
            "INVALID_ASSET_KIND")
    digest = sha(path)
    con.execute("BEGIN IMMEDIATE")
    try:
        existing = con.execute("SELECT sha256 FROM assets WHERE project_id=? AND asset_id=?",
                               (project,asset_id)).fetchone()
        if existing:
            require(existing["sha256"] == digest, "ASSET_ID_IMMUTABLE_USE_NEW_ID")
            con.execute("COMMIT")
            return "IDEMPOTENT"
        con.execute("""INSERT INTO assets VALUES (?,?,?,?,?,?,?,?)""",
                    (project,asset_id,kind,str(path),digest,event_time,utc(),rights))
        start = "SOURCE" if kind in {"SOURCE","TRANSCRIPT","REFERENCE"} else "EDIT_PLAN"
        invalidate(con,project,start,"LATE_ARRIVING_ASSET:"+asset_id)
        event(con,project,"ASSET_REGISTERED",asset_id=asset_id,kind=kind,sha256=digest,
              event_time=event_time,ingested_at=utc())
        con.execute("COMMIT")
        return "REGISTERED"
    except Exception:
        con.execute("ROLLBACK")
        raise


def inspect_video(path):
    command = ["ffprobe","-v","error","-show_streams","-of","json",str(path)]
    p = subprocess.run(command,capture_output=True,text=True,timeout=60)
    require(p.returncode==0,"RENDER_FFPROBE_FAILED:"+p.stderr[-200:])
    streams = json.loads(p.stdout)["streams"]
    video = next((x for x in streams if x.get("codec_type")=="video"),None)
    audio = next((x for x in streams if x.get("codec_type")=="audio"),None)
    require(video and audio, "RENDER_VIDEO_AND_AUDIO_REQUIRED")
    fps = str(video.get("r_frame_rate","0/1")).split("/")
    num, den = int(fps[0]),int(fps[1])
    require(num>0 and den>0,"RENDER_INVALID_FPS")
    count = video.get("nb_frames")
    if not count:
        p = subprocess.run(["ffprobe","-v","error","-count_frames","-select_streams","v:0",
            "-show_entries","stream=nb_read_frames","-of","default=nokey=1:noprint_wrappers=1",
            str(path)],capture_output=True,text=True,timeout=120)
        require(p.returncode==0,"RENDER_FRAME_COUNT_FAILED")
        count=p.stdout.strip()
    require(str(count).isdigit() and int(count)>0,"RENDER_NO_FRAMES")
    return num,den,int(count)


def render_sha(con, project):
    row = stage_row(con,project,"RENDER")
    require(row and row["status"]=="PASS","RENDER_NOT_PASSED")
    return row["artifact_sha"]


def validate(con, project, stage, path):
    if stage == "SOURCE":
        require(any(a["kind"]=="SOURCE" for a in assets(con,project)),
                "SOURCE_MEDIA_NOT_REGISTERED")
    if stage == "RENDER":
        return inspect_video(path)
    if stage == "DELIVERY":
        require(sha(path)==render_sha(con,project),"DELIVERY_RENDER_HASH_MISMATCH")
        review=read_json(stage_row(con,project,"HUMAN_REVIEW")["artifact_path"])
        if review.get("visibility")=="PUBLIC":
            require(all(a["rights"]=="VERIFIED" for a in assets(con,project)
                        if a["kind"] in {"SOURCE","BROLL","AUDIO","IMAGE"}),
                    "PUBLIC_RIGHTS_NOT_CLEARED")
        else:
            require(review.get("visibility")=="PRIVATE_REVIEW","REVIEW_VISIBILITY_REQUIRED")
        render=con.execute("SELECT * FROM renders WHERE project_id=? AND sha256=?",
                           (project,render_sha(con,project))).fetchone()
        require(render is not None,"RENDER_REGISTRY_MISSING")
        rows=con.execute("""SELECT * FROM spans WHERE project_id=? AND render_id=?
                           AND layer='PRIMARY' ORDER BY output_first_frame""",
                         (project,render["render_id"])).fetchall()
        cursor=0
        for span in rows:
            require(span["output_first_frame"]==cursor,"PRIMARY_FRAME_GAP_OR_OVERLAP")
            cursor=span["output_end_frame"]
        require(cursor==render["frame_count"],"INCOMPLETE_FRAME_LINEAGE")
        required={x["beat_id"] for x in con.execute(
                 "SELECT beat_id FROM beats WHERE project_id=?",(project,))}
        covered={x["beat_id"] for x in rows}
        require(required and required.issubset(covered),"STORY_BEAT_FRAME_LINEAGE_MISSING")
        return None
    if stage not in {"STORY_LOCK","EDIT_PLAN","EDIT","TECH_QA","STORY_QA","HUMAN_REVIEW"}:
        return None
    obj = read_json(path)
    require(isinstance(obj,dict),"RECEIPT_NOT_OBJECT")
    if stage == "STORY_LOCK":
        story = obj.get("story_map",obj)
        for key in ("hook_promise","viewer_prediction","want","tapi","so","payoff"):
            require(isinstance(story.get(key),str) and len(story[key].strip())>=8,
                    "STORY_MISSING:"+key)
        beats = obj.get("beats",[])
        require(isinstance(beats,list) and beats,"STORY_BEATS_EMPTY")
        ids=set()
        for beat in beats:
            require(beat.get("beat_id") and beat.get("role") in ROLE_SET
                    and beat["beat_id"] not in ids,"INVALID_STORY_BEAT")
            ids.add(beat["beat_id"])
        require({"HOOK","TAPI","SO","PAYOFF"}.issubset({b["role"] for b in beats}),
                "STORY_MISSING_CRITICAL_ROLES")
    if stage=="EDIT":
        plan=stage_row(con,project,"EDIT_PLAN")
        info=read_json(plan["artifact_path"])
        require(obj.get("plan_sha256")==plan["artifact_sha"],"EDIT_PLAN_HASH_MISMATCH")
        require(set(obj.get("beat_ids",[]))==set(info["beat_ids"]),
                "EDIT_STORY_BEAT_MISSING")
        executed=obj.get("executed_skills",[])
        required_skills=set(info["selected_skills"])-{"video-edit-pipeline"}
        require(isinstance(executed,list) and
                {entry.get("name") for entry in executed}==required_skills,
                "EDIT_SKILL_EXECUTION_COVERAGE_MISSING")
        for entry in executed:
            proof=Path(entry.get("proof_path",""))
            require(proof.is_file() and proof.stat().st_size>0 and
                    sha(proof)==entry.get("proof_sha256"),
                    "EDIT_SKILL_PROOF_MISSING_OR_CHANGED:"+str(entry.get("name")))
    if stage=="EDIT_PLAN":
        story = stage_row(con,project,"STORY_LOCK")
        require(obj.get("story_sha256")==story["artifact_sha"],"PLAN_STALE_STORY")
        chosen=obj.get("selected_skills")
        require(isinstance(chosen,list) and bool(chosen)
                and len(chosen)==len(set(chosen)),"PLAN_SKILL_SELECTION_MISSING_OR_DUPLICATE")
        require("video-edit-pipeline" in chosen,"MASTER_SKILL_REQUIRED")
        require(len(set(chosen)-{"video-edit-pipeline"})>=1,
                "NO_NATIVE_EDIT_SKILL_SELECTED")
        registry=next((a for a in assets(con,project)
                       if a["kind"]=="REFERENCE" and a["asset_id"]=="editor_skill_pack"),None)
        require(registry is not None,"PINNED_SKILL_REGISTRY_REQUIRED")
        manifest=read_json(registry["path"])
        require(len(manifest.get("skills",[]))==21,"SKILL_REGISTRY_INCOMPLETE")
        by_name={entry["name"]:entry for entry in manifest["skills"]}
        for name in chosen:
            entry=by_name.get(name)
            require(entry is not None,"UNREGISTERED_SKILL:"+name)
            require(entry["status"] not in {"PLATFORM_BLOCKED_IN_CODESPACE","EXPERIMENTAL"},
                    "UNSUPPORTED_SKILL:"+name)
            skill_path=Path(entry["instruction_path"])
            require(skill_path.is_file() and sha(skill_path)==entry["instruction_sha256"],
                    "UPSTREAM_SKILL_DRIFT:"+name)
        beat_ids = {x["beat_id"] for x in read_json(story["artifact_path"])["beats"]}
        require(isinstance(obj.get("beat_ids"),list) and
                set(obj["beat_ids"])==beat_ids,"PLAN_BEAT_COVERAGE_MISMATCH")
    if stage in {"TECH_QA","STORY_QA","HUMAN_REVIEW"}:
        require(obj.get("render_sha256")==render_sha(con,project),
                "QA_OR_REVIEW_STALE_RENDER")
    if stage=="TECH_QA":
        require(obj.get("status")=="PASS" and
                all(obj.get("checks",{}).get(k)=="PASS" for k in
                    ("decode","video","audio","captions")),"TECH_QA_NOT_PASSED")
    if stage=="STORY_QA":
        require(obj.get("story_sha256")==stage_row(con,project,"STORY_LOCK")["artifact_sha"],
                "STORY_QA_STALE_STORY")
        require(obj.get("status")=="PASS" and
                all(obj.get("checks",{}).get(k)=="PASS" for k in
                    ("hook_payoff","wts_causality","beat_coverage","factual_integrity")),
                "STORY_QA_NOT_PASSED")
    if stage=="HUMAN_REVIEW":
        require(obj.get("human_approved") is True and
                isinstance(obj.get("reviewer"),str) and len(obj["reviewer"].strip())>=3
                and obj.get("reviewed_at"),"HUMAN_APPROVAL_NOT_RECORDED")
        require(obj.get("visibility") in {"PRIVATE_REVIEW","PUBLIC"},
                "REVIEW_VISIBILITY_REQUIRED")
    return None


def run_stage(con, project, stage, artifact, command):
    require(stage in STAGES,"UNKNOWN_STAGE")
    require(bool(command),"EXECUTABLE_COMMAND_REQUIRED")
    artifact = Path(artifact).resolve()
    con.execute("BEGIN IMMEDIATE")
    try:
        sig = fingerprint(con,project,stage)
        previous=stage_row(con,project,stage)
        require(not previous or previous["status"]!="PASS","IMMUTABLE_STAGE_ALREADY_PASSED")
        require(not previous or previous["status"]!="RUNNING","STAGE_ALREADY_RUNNING")
        con.execute("""INSERT INTO stages(project_id,stage,status,input_fingerprint,
                       artifact_path,started_at) VALUES(?,?,?,?,?,?)
                       ON CONFLICT(project_id,stage) DO UPDATE SET
                       status=excluded.status,input_fingerprint=excluded.input_fingerprint,
                       artifact_path=excluded.artifact_path,artifact_sha=NULL,
                       started_at=excluded.started_at,finished_at=NULL,failure_reason=NULL""",
                    (project,stage,"RUNNING",sig,str(artifact),utc()))
        event(con,project,"STAGE_START",stage=stage,command=command)
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    failure=None
    try:
        process=subprocess.run(command,check=False)
        require(process.returncode==0,"COMMAND_EXIT_"+str(process.returncode))
        require(artifact.is_file() and artifact.stat().st_size>0,"ARTIFACT_MISSING_OR_EMPTY")
        require(fingerprint(con,project,stage)==sig,"INPUT_CHANGED_DURING_STAGE")
        meta=validate(con,project,stage,artifact)
        digest=sha(artifact)
        con.execute("BEGIN IMMEDIATE")
        try:
            row=stage_row(con,project,stage)
            require(row and row["status"]=="RUNNING" and row["input_fingerprint"]==sig,
                    "STAGE_LEASE_LOST")
            con.execute("""UPDATE stages SET status='PASS',artifact_sha=?,
                           finished_at=?,failure_reason=NULL
                           WHERE project_id=? AND stage=?""",(digest,utc(),project,stage))
            if stage=="STORY_LOCK":
                story=read_json(artifact)
                version=con.execute("SELECT story_version FROM projects WHERE id=?",
                                    (project,)).fetchone()["story_version"]
                con.execute("DELETE FROM beats WHERE project_id=?",(project,))
                for beat in story["beats"]:
                    con.execute("INSERT INTO beats VALUES(?,?,?,?)",
                                (project,beat["beat_id"],version,beat["role"]))
            if stage=="RENDER":
                n,den,count=meta
                con.execute("INSERT INTO renders VALUES(?,?,?,?,?,?,?,?)",
                            (project,"render_"+digest[:20],str(artifact),digest,n,den,count,utc()))
            event(con,project,"STAGE_PASS",stage=stage,artifact_sha=digest)
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        return {"stage":stage,"status":"PASS","sha256":digest}
    except Exception as exc:
        failure=str(exc)
        con.execute("BEGIN IMMEDIATE")
        try:
            con.execute("""UPDATE stages SET status='FAILED',failure_reason=?,finished_at=?
                           WHERE project_id=? AND stage=? AND status='RUNNING'""",
                        (failure,utc(),project,stage))
            event(con,project,"STAGE_FAILED",stage=stage,reason=failure)
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
        raise GateError(failure) from exc


def audit(con,project):
    issues=[]
    for stage in STAGES:
        row=stage_row(con,project,stage)
        if row is None or row["status"]!="PASS":
            issues.append(stage+":NOT_PASS:"+(row["status"] if row else "PENDING"))
            continue
        try:
            require(Path(row["artifact_path"]).is_file() and
                    sha(row["artifact_path"])==row["artifact_sha"],"ARTIFACT_HASH_MISMATCH")
            require(fingerprint(con,project,stage)==row["input_fingerprint"],
                    "INPUT_FINGERPRINT_STALE")
            validate(con,project,stage,row["artifact_path"])
        except Exception as e:
            issues.append(stage+":"+str(e))
    for asset in assets(con,project):
        if not Path(asset["path"]).is_file() or sha(asset["path"])!=asset["sha256"]:
            issues.append("ASSET_DRIFT:"+asset["asset_id"])
    return {"project_id":project,"status":"PASS" if not issues else "BLOCKED",
            "issues":issues,"stage_statuses":{s:(stage_row(con,project,s)["status"]
             if stage_row(con,project,s) else "PENDING") for s in STAGES}}


def add_clip(con,project,clip,asset,start,end):
    require(0<=start<end,"INVALID_CLIP_INTERVAL")
    con.execute("INSERT INTO clips VALUES(?,?,?,?,?)",(project,clip,asset,start,end))
    invalidate(con,project,"EDIT_PLAN","NEW_CLIP:"+clip)
    event(con,project,"CLIP_REGISTERED",clip_id=clip,asset_id=asset)


def add_span(con,project,render,span,beat,clip,layer,src0,src1,frame0,frame1,transform,version):
    row=con.execute("SELECT frame_count FROM renders WHERE project_id=? AND render_id=?",
                    (project,render)).fetchone()
    require(row and 0<=frame0<frame1<=row["frame_count"],"SPAN_FRAMES_OUT_OF_RENDER")
    original=con.execute("SELECT source_in_ms,source_out_ms FROM clips WHERE project_id=? AND clip_id=?",
                         (project,clip)).fetchone()
    require(original and original["source_in_ms"]<=src0<src1<=original["source_out_ms"],
            "SPAN_OUTSIDE_SOURCE_CLIP")
    if layer=="PRIMARY":
        overlap=con.execute("""SELECT span_id FROM spans WHERE project_id=? AND render_id=?
            AND layer='PRIMARY' AND output_first_frame<? AND output_end_frame>?""",
            (project,render,frame1,frame0)).fetchone()
        require(overlap is None,"PRIMARY_FRAME_OVERLAP")
    con.execute("INSERT INTO spans VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (project,render,span,beat,clip,layer,src0,src1,frame0,frame1,transform,version))
    invalidate(con,project,"TECH_QA","LINEAGE_EDIT:"+span)
    event(con,project,"SPAN_MAPPED",render_id=render,span_id=span,beat_id=beat)


def add_frame_evidence(con,project,render,frame,kind,path):
    r=con.execute("SELECT frame_count FROM renders WHERE project_id=? AND render_id=?",
                  (project,render)).fetchone()
    require(r and 0<=frame<r["frame_count"],"EVIDENCE_FRAME_OUT_OF_RANGE")
    require(Path(path).is_file(),"EVIDENCE_FILE_MISSING")
    con.execute("INSERT INTO frame_evidence VALUES(?,?,?,?,?,?)",
                (project,render,frame,kind,str(Path(path).resolve()),sha(path)))


def add_variant(con,project,variant,body,hook):
    con.execute("BEGIN IMMEDIATE")
    try:
        limit=con.execute("SELECT max_variants FROM projects WHERE id=?",(project,)).fetchone()
        require(limit is not None,"UNKNOWN_PROJECT")
        existing=con.execute("SELECT body_sha256,hook_sha256 FROM variants WHERE project_id=? AND variant_id=?",
                             (project,variant)).fetchone()
        if existing:
            require((existing["body_sha256"],existing["hook_sha256"])==(body,hook),
                    "VARIANT_ID_IMMUTABLE")
            con.execute("COMMIT")
            return "IDEMPOTENT"
        count=con.execute("SELECT COUNT(*) n FROM variants WHERE project_id=?",
                          (project,)).fetchone()["n"]
        require(count<limit["max_variants"],"FANOUT_LIMIT_EXCEEDED")
        require(len(body)==64 and len(hook)==64,"INVALID_VARIANT_HASH")
        con.execute("INSERT INTO variants VALUES(?,?,?,?)",(project,variant,body,hook))
        event(con,project,"VARIANT_REGISTERED",variant_id=variant)
        con.execute("COMMIT")
        return "REGISTERED"
    except Exception:
        con.execute("ROLLBACK")
        raise


def trace_frame(con,project,render,frame):
    render_row=con.execute("SELECT * FROM renders WHERE project_id=? AND render_id=?",
                           (project,render)).fetchone()
    require(render_row is not None and 0<=frame<render_row["frame_count"],
            "TRACE_FRAME_NOT_IN_RENDER")
    records=con.execute("""SELECT s.*,c.asset_id,a.path,a.sha256 as asset_sha256,
                           b.role,b.story_version FROM spans s
                           JOIN clips c ON c.project_id=s.project_id AND c.clip_id=s.clip_id
                           JOIN assets a ON a.project_id=c.project_id AND a.asset_id=c.asset_id
                           JOIN beats b ON b.project_id=s.project_id AND b.beat_id=s.beat_id
                           WHERE s.project_id=? AND s.render_id=?
                           AND s.output_first_frame<=? AND s.output_end_frame>?
                           ORDER BY CASE WHEN s.layer='PRIMARY' THEN 0 ELSE 1 END""",
                        (project,render,frame,frame)).fetchall()
    require(records,"FRAME_LINEAGE_UNMAPPED")
    return {"render_id":render,"render_sha256":render_row["sha256"],
            "frame_number":frame,"fps":[render_row["fps_num"],render_row["fps_den"]],
            "source_spans":[dict(r) for r in records]}


def recover(con,project,stage,confirm):
    require(confirm is True,"WORKER_STOP_CONFIRMATION_REQUIRED")
    require(stage in STAGES,"UNKNOWN_STAGE")
    con.execute("BEGIN IMMEDIATE")
    try:
        row=stage_row(con,project,stage)
        require(row and row["status"]=="RUNNING","NO_INTERRUPTED_RUNNING_STAGE")
        con.execute("""UPDATE stages SET status='FAILED',failure_reason=?,
                       finished_at=? WHERE project_id=? AND stage=?""",
                    ("OPERATOR_CONFIRMED_WORKER_STOPPED",utc(),project,stage))
        event(con,project,"MANUAL_RECOVER",stage=stage,prior_fingerprint=row["input_fingerprint"])
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise


def main(argv=None):
    ap=argparse.ArgumentParser(description="Fail-closed video production control plane")
    ap.add_argument("--db",required=True)
    sub=ap.add_subparsers(dest="action",required=True)
    p=sub.add_parser("init");p.add_argument("project");p.add_argument("--story-version",default="v1")
    p.add_argument("--max-variants",type=int,default=8)
    p=sub.add_parser("asset");p.add_argument("project");p.add_argument("asset_id")
    p.add_argument("kind");p.add_argument("path");p.add_argument("--rights",required=True)
    p.add_argument("--event-time")
    p=sub.add_parser("clip");p.add_argument("project");p.add_argument("clip_id")
    p.add_argument("asset_id");p.add_argument("start_ms",type=int);p.add_argument("end_ms",type=int)
    p=sub.add_parser("run");p.add_argument("project");p.add_argument("stage")
    p.add_argument("artifact");p.add_argument("command",nargs=argparse.REMAINDER)
    p=sub.add_parser("span");p.add_argument("project");p.add_argument("render_id")
    p.add_argument("span_id");p.add_argument("beat_id");p.add_argument("clip_id")
    p.add_argument("layer");p.add_argument("source_in_ms",type=int)
    p.add_argument("source_out_ms",type=int);p.add_argument("first_frame",type=int)
    p.add_argument("end_frame",type=int);p.add_argument("transform_id")
    p.add_argument("transform_version")
    p=sub.add_parser("variant");p.add_argument("project");p.add_argument("variant_id")
    p.add_argument("body_sha256");p.add_argument("hook_sha256")
    p=sub.add_parser("frame-evidence");p.add_argument("project");p.add_argument("render_id")
    p.add_argument("frame",type=int);p.add_argument("kind");p.add_argument("path")
    p=sub.add_parser("audit");p.add_argument("project")
    p=sub.add_parser("status");p.add_argument("project")
    p=sub.add_parser("recover");p.add_argument("project");p.add_argument("stage")
    p.add_argument("--confirm-worker-stopped",action="store_true")
    p=sub.add_parser("trace");p.add_argument("project");p.add_argument("render_id")
    p.add_argument("frame",type=int)
    p=sub.add_parser("snapshot");p.add_argument("project");p.add_argument("out")
    args=ap.parse_args(argv)
    con=connection(args.db)
    try:
        if args.action=="init":
            require(1<=args.max_variants<=32,"MAX_VARIANTS_OUT_OF_RANGE")
            con.execute("INSERT OR IGNORE INTO projects VALUES(?,?,?,?)",
                        (args.project,utc(),args.story_version,args.max_variants))
            result={"status":"READY","project":args.project}
        elif args.action=="asset":
            result={"status":add_asset(con,args.project,args.asset_id,args.kind,args.path,
                                     args.rights,args.event_time)}
        elif args.action=="clip":
            add_clip(con,args.project,args.clip_id,args.asset_id,args.start_ms,args.end_ms)
            result={"status":"REGISTERED"}
        elif args.action=="run":
            cmd=args.command[1:] if args.command and args.command[0]=="--" else args.command
            result=run_stage(con,args.project,args.stage,args.artifact,cmd)
        elif args.action=="span":
            add_span(con,args.project,args.render_id,args.span_id,args.beat_id,args.clip_id,
                     args.layer,args.source_in_ms,args.source_out_ms,args.first_frame,
                     args.end_frame,args.transform_id,args.transform_version)
            result={"status":"REGISTERED"}
        elif args.action=="variant":
            result={"status":add_variant(con,args.project,args.variant_id,
                                         args.body_sha256,args.hook_sha256)}
        elif args.action=="frame-evidence":
            add_frame_evidence(con,args.project,args.render_id,args.frame,
                               args.kind,args.path)
            result={"status":"REGISTERED"}
        elif args.action=="recover":
            recover(con,args.project,args.stage,args.confirm_worker_stopped)
            result={"status":"FAILED_RETRY_ELIGIBLE","stage":args.stage}
        elif args.action=="trace":
            result=trace_frame(con,args.project,args.render_id,args.frame)
        elif args.action=="snapshot":
            result={"project":args.project,"audit":audit(con,args.project),
                    "assets":assets(con,args.project),
                    "stages":[dict(r) for r in con.execute("SELECT * FROM stages WHERE project_id=?",(args.project,))],
                    "spans":[dict(r) for r in con.execute("SELECT * FROM spans WHERE project_id=?",(args.project,))],
                    "events":[dict(r) for r in con.execute("SELECT * FROM events WHERE project_id=? ORDER BY id",(args.project,))]}
            dest=Path(args.out);dest.parent.mkdir(parents=True,exist_ok=True)
            temp=dest.with_name(dest.name+"."+uuid.uuid4().hex+".tmp")
            temp.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
            os.replace(temp,dest)
            result={"status":"EXPORTED","file":str(dest)}
        else:
            result=audit(con,args.project)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 2 if result.get("status")=="BLOCKED" and args.action=="audit" else 0
    except (GateError,OSError,ValueError,sqlite3.Error,subprocess.TimeoutExpired) as exc:
        print("GATE_FAIL:"+str(exc),file=sys.stderr)
        return 2
    finally:
        con.close()


if __name__=="__main__":
    raise SystemExit(main())
