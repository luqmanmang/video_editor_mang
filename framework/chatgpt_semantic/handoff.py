#!/usr/bin/env python3
"""Private ChatGPT semantic handoff. Stdlib only; NO model API or background AI."""
from __future__ import annotations
import argparse, hashlib, json, os, re, sys, time, uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

VERSION = "1.0.0"
HERE = Path(__file__).resolve().parent
RUNTIME = HERE.parents[2] / "semantic_runtime"
ROLES = {"HOOK","WANT","TAPI","SO","PAYOFF","CONTEXT"}
STYLES = {"NONE","AUTO","BOXED","OUTLINE"}
MOTIONS = {"STATIC","SUBTLE","EMPHASIS"}

def now(): return datetime.now(timezone.utc).isoformat(timespec="seconds")
def canon(x): return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode("utf-8")
def sha(blob): return hashlib.sha256(blob).hexdigest()
def file_sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for part in iter(lambda:f.read(1024*1024),b""): h.update(part)
    return h.hexdigest()
def read(path): return json.loads(Path(path).read_text(encoding="utf-8-sig"))
def save(path,obj):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+"."+uuid.uuid4().hex+".tmp")
    try:
        tmp.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
        os.replace(tmp,path)
    finally: tmp.unlink(missing_ok=True)
def assert_ok(condition,what):
    if not condition: raise ValueError(what)
def log(folder,event,**kwargs):
    with (folder/"events.jsonl").open("a",encoding="utf-8") as f:
        f.write(json.dumps({"timestamp":now(),"event":event,**kwargs},ensure_ascii=False)+"\n")
@contextmanager
def guarded(folder):
    lock=folder/".lock"
    for attempt in range(40):
        try:
            fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            os.close(fd); break
        except FileExistsError:
            if attempt==39: raise RuntimeError("Locked job: inspect .lock before retry")
            time.sleep(.1)
    try: yield
    finally: lock.unlink(missing_ok=True)

def check_source(s):
    assert_ok(isinstance(s,dict),"source must be JSON object")
    assert_ok(bool(re.fullmatch(r"[A-Za-z0-9_-]{3,80}",str(s.get("project_id","")))),"Invalid project_id")
    assert_ok(s.get("task")=="EDITORIAL_PLAN","task must be EDITORIAL_PLAN")
    b=s.get("brief")
    assert_ok(isinstance(b,dict) and all(isinstance(b.get(k),str) and b[k].strip()
              for k in ("viewer","goal","platform","language")),"Missing brief fields")
    out=s.get("output",{})
    assert_ok((out.get("width"),out.get("height"),out.get("fps"))==(720,1280,30),
              "Output contract must be 720x1280 30fps")
    dur=s.get("video",{}).get("duration_ms")
    assert_ok(type(dur)==int and dur>0,"Invalid video.duration_ms")
    segments=s.get("segments")
    assert_ok(isinstance(segments,list) and len(segments)>0,"Missing transcript segments")
    seen=set(); last=-1
    for v in segments:
        sid=v.get("segment_id")
        assert_ok(isinstance(sid,str) and bool(re.fullmatch(r"[A-Za-z0-9_-]{1,80}",sid))
                  and sid not in seen,"Invalid/duplicate segment_id")
        seen.add(sid)
        assert_ok(isinstance(v.get("clip_id"),str) and v["clip_id"].strip(),"Missing clip_id")
        assert_ok(isinstance(v.get("text"),str) and v["text"].strip(),"Empty segment text")
        a,z=v.get("start_ms"),v.get("end_ms")
        assert_ok(type(a)==int and type(z)==int and last<=a<z<=dur,
                  "Out-of-range/overlapping transcript timestamps")
        last=z
    assets=s.get("assets",[])
    assert_ok(isinstance(assets,list),"assets must be array")
    ids=[a.get("asset_id") for a in assets]
    assert_ok(len(ids)==len(set(ids)) and all(isinstance(x,str) and x for x in ids),
              "Invalid/duplicate asset_id")
    for section in ("media","frames"):
        assert_ok(isinstance(s.get(section,[]),list),section+" must be array")
        for item in s.get(section,[]):
            assert_ok(isinstance(item,dict) and isinstance(item.get("path"),str)
                      and item["path"].strip(),"Missing evidence path in "+section)
    for f in s.get("frames",[]):
        assert_ok(type(f.get("at_ms"))==int and 0<=f["at_ms"]<=dur,"Invalid frame timestamp")
    return {"status":"PASS","segments":len(segments),"assets":len(assets),
            "warnings":([] if s.get("frames") else
                        ["NO_VISUAL_EVIDENCE: face-safe headline placement must stay PENDING"]) +
                        ["TIMING_UNVERIFIED: word-level/audio cut precision requires independent QC"]}

def prompt(req):
    s=req["source"]
    return (
        "# Manual ChatGPT semantic editorial review\n\n"
        "Read request.json via Remote Desktop Commander, and examine evidence frames where available.\n"
        "Use project WTS/REN storytelling principles, but do not invent dialogue, assets, timestamps, rights or proof.\n"
        "Build COMPLETE semantic idea beats (not single keywords). Every beat must cite real segment IDs.\n"
        "Headline: decide wording and style; placement remains provisional until geometric/face QA.\n"
        "B-roll: optional, only known VERIFIED asset IDs. Motion: optional. Cut guidance is NOT a millisecond cut.\n"
        "ChatGPT fills a new response.json using response_template.json. Then run handoff.py submit.\n"
        "No external model/API is called by Python. Public release and human review remain separately blocked.\n\n"
        "Project: "+s["project_id"]+"\n"
        "Viewer: "+s["brief"]["viewer"]+"\n"
        "Goal: "+s["brief"]["goal"]+"\n"
        "Job ID: "+req["job_id"]+"\n"
        "Input fingerprint: "+req["input_fingerprint"]+"\n"
    )

def prepare(source_path,runtime):
    path=Path(source_path).resolve(); s=read(path); q=check_source(s)
    files=[Path(x["path"]).resolve() for x in s.get("media",[])+s.get("frames",[])]
    hashes={}
    for p in files:
        assert_ok(p.is_file() and p.stat().st_size>0,"Missing/empty evidence: "+str(p))
        hashes[str(p)]=file_sha(p)
    policy=HERE/"editorial_policy.md"
    module_hashes={str(p):file_sha(p) for p in
                   (HERE/"handoff.py",HERE/"source.schema.json",HERE/"response.schema.json")}
    source_hash=file_sha(path); policy_hash=file_sha(policy)
    fingerprint=sha(canon({"version":VERSION,"source_sha256":source_hash,
                            "policy_sha256":policy_hash,"module_sha256":module_hashes,
                            "evidence_sha256":hashes}))
    job="sem_"+fingerprint[:20]
    folder=Path(runtime).resolve()/"jobs"/job
    folder.mkdir(parents=True,exist_ok=True)
    with guarded(folder):
        if (folder/"request.json").is_file():
            assert_ok(read(folder/"request.json")["input_fingerprint"]==fingerprint,
                      "Job fingerprint conflict")
            log(folder,"PREPARE_REUSED")
            return {"status":"REUSED","job_id":job,"folder":str(folder)}
        req={"schema_version":VERSION,"job_id":job,"input_fingerprint":fingerprint,"source":s}
        lineage={"job_id":job,"source_path":str(path),"source_sha256":source_hash,
                 "policy_path":str(policy),"policy_sha256":policy_hash,
                 "module_sha256":module_hashes,"evidence_sha256":hashes,
                 "input_fingerprint":fingerprint,
                 "prepared_at":now(),"derived_from":["source","policy","media","frames"]}
        tpl={"schema_version":VERSION,"job_id":job,"input_fingerprint":fingerprint,"revision":1,
             "beats":[{"beat_id":"beat_01","start_segment_id":s["segments"][0]["segment_id"],
             "end_segment_id":s["segments"][0]["segment_id"],
             "evidence_segment_ids":[s["segments"][0]["segment_id"]],"story_role":"HOOK",
             "meaning":"REPLACE WITH ACTUAL SEMANTIC ANALYSIS",
             "headline":{"text":None,"style_hint":"NONE","reason":"No overlay required"},
             "broll":{"asset_id":None,"reason":"A-roll preserves context"},
             "motion":{"mode":"STATIC","reason":"No emphasis required"},
             "cut_guidance":"REVIEW"}]}
        save(folder/"request.json",req); save(folder/"lineage.json",lineage)
        save(folder/"source_dq.json",q); save(folder/"response_template.json",tpl)
        (folder/"analysis_prompt.md").write_text(prompt(req),encoding="utf-8")
        save(folder/"state.json",{"job_id":job,"status":"PENDING_CHATGPT",
                                  "latest_revision":0,"public_release_approved":False,
                                  "updated_at":now()})
        log(folder,"PREPARED",segments=q["segments"],assets=q["assets"])
    return {"status":"PREPARED","job_id":job,"folder":str(folder),"data_quality":q}

def check_response(r,req):
    s=req["source"]; seg=s["segments"]
    ids={v["segment_id"]:i for i,v in enumerate(seg)}
    assets={v["asset_id"]:v for v in s.get("assets",[])}
    assert_ok(r.get("schema_version")==VERSION and r.get("job_id")==req["job_id"] and
              r.get("input_fingerprint")==req["input_fingerprint"],"Wrong schema/job/input fingerprint")
    assert_ok(type(r.get("revision"))==int and r["revision"]>=1,"Invalid revision")
    beats=r.get("beats")
    assert_ok(isinstance(beats,list) and beats,"No semantic beats")
    last=-1; seen=set(); covered=set()
    for b in beats:
        name=b.get("beat_id")
        assert_ok(isinstance(name,str) and bool(re.fullmatch(r"[A-Za-z0-9_-]{1,80}",name))
                  and name not in seen,"Bad/duplicate beat_id")
        seen.add(name)
        a,z=ids.get(b.get("start_segment_id"),-1),ids.get(b.get("end_segment_id"),-1)
        assert_ok(last<a<=z,"Beat range invalid/out-of-order/overlaps")
        last=z
        covered.update(range(a,z+1))
        ev=b.get("evidence_segment_ids")
        assert_ok(isinstance(ev,list) and bool(ev) and
                  all(e in ids and a<=ids[e]<=z for e in ev),"Invalid evidence segment IDs")
        assert_ok(b.get("story_role") in ROLES,"Unknown story role")
        assert_ok(isinstance(b.get("meaning"),str) and len(b["meaning"].strip())>=8 and
                  "REPLACE WITH" not in b["meaning"].upper() and "TODO" not in b["meaning"].upper(),
                  "Insufficient grounded meaning or unfilled response template")
        h=b.get("headline")
        assert_ok(isinstance(h,dict) and h.get("style_hint") in STYLES and h.get("reason"),
                  "Invalid headline decision")
        t=h.get("text")
        if h["style_hint"]=="NONE":
            assert_ok(t in (None,""),"NONE headline cannot contain text")
        else:
            assert_ok(isinstance(t,str) and 3<=len(t.strip())<=120,"Invalid headline text length")
        br=b.get("broll")
        assert_ok(isinstance(br,dict) and isinstance(br.get("reason"),str) and
                  br["reason"].strip(),"B-roll reason missing")
        asset=br.get("asset_id")
        if asset is not None:
            assert_ok(asset in assets,"Hallucinated asset ID")
            assert_ok(assets[asset].get("license_status")=="VERIFIED",
                      "Selected asset license not VERIFIED")
        motion=b.get("motion")
        assert_ok(isinstance(motion,dict) and motion.get("mode") in MOTIONS and
                  motion.get("reason"),"Invalid motion")
        assert_ok(b.get("cut_guidance") in {"KEEP","TRIM_SILENCE","REVIEW"},"Invalid cut guidance")
    excluded=r.get("excluded_segments",[])
    assert_ok(isinstance(excluded,list),"excluded_segments must be array")
    excludes=set()
    for x in excluded:
        assert_ok(isinstance(x,dict) and x.get("segment_id") in ids and
                  isinstance(x.get("reason"),str) and len(x["reason"].strip())>=8,
                  "Excluded segment requires known ID and genuine reason")
        idx=ids[x["segment_id"]]
        assert_ok(idx not in covered and idx not in excludes,"Excluded segment overlaps/duplicates")
        excludes.add(idx)
    assert_ok(covered|excludes==set(range(len(seg))),
              "Every transcript segment must be covered or explicitly excluded with reason")
    return {"status":"PASS","beat_count":len(beats),"checked_at":now(),
            "warnings":["FACE_AND_TEXT_GEOMETRY_NOT_VERIFIED",
                        "CUT_BOUNDARIES_REQUIRE_WAVEFORM_OR_LISTENING",
                        "PUBLIC_RELEASE_NOT_AUTHORIZED"]}

def verify_lineage(folder):
    d=read(folder/"lineage.json")
    assert_ok(file_sha(d["source_path"])==d["source_sha256"],"Source changed; prepare new job")
    assert_ok(file_sha(d["policy_path"])==d["policy_sha256"],"Policy changed; prepare new job")
    for p,h in d["module_sha256"].items():
        assert_ok(file_sha(p)==h,"Semantic validator/schema changed; prepare new job: "+p)
    for p,h in d["evidence_sha256"].items():
        assert_ok(Path(p).is_file() and file_sha(p)==h,"Media changed; prepare new job: "+p)

def submit(job,response_path,runtime):
    assert_ok(bool(re.fullmatch(r"sem_[a-f0-9]{20}",job)),"Invalid job ID")
    folder=Path(runtime).resolve()/"jobs"/job
    assert_ok((folder/"request.json").is_file(),"Unknown job")
    r=read(response_path)
    with guarded(folder):
        verify_lineage(folder)
        dq=check_response(r,read(folder/"request.json"))
        rev=r["revision"]
        out=folder/"decisions"/("revision_%03d.json"%rev)
        if out.is_file():
            assert_ok(canon(read(out))==canon(r),"Revision conflict; increment revision for changes")
            log(folder,"SUBMIT_REUSED",revision=rev)
            return {"status":"REUSED_VALIDATED","job_id":job,"revision":rev,"path":str(out)}
        state=read(folder/"state.json")
        assert_ok(rev==state["latest_revision"]+1,"Revision must increment by 1")
        save(out,r)
        save(folder/"decisions"/("revision_%03d_dq.json"%rev),dq)
        save(folder/"state.json",{"job_id":job,"status":"VALIDATED_FOR_PRIVATE_PREVIEW",
                                  "latest_revision":rev,"active_decision":str(out),
                                  "decision_sha256":file_sha(out),"updated_at":now(),
                                  "public_release_approved":False})
        log(folder,"SEMANTIC_VALIDATED",revision=rev,decision_sha256=file_sha(out))
        return {"status":"VALIDATED_FOR_PRIVATE_PREVIEW","job_id":job,"revision":rev,
                "path":str(out),"data_quality":dq}

def main():
    p=argparse.ArgumentParser(description="Local ChatGPT semantic handoff")
    p.add_argument("--runtime",type=Path,default=RUNTIME)
    sub=p.add_subparsers(dest="command",required=True)
    a=sub.add_parser("prepare"); a.add_argument("--source",required=True)
    a=sub.add_parser("submit"); a.add_argument("--job-id",required=True); a.add_argument("--response",required=True)
    a=sub.add_parser("status"); a.add_argument("--job-id",required=True)
    sub.add_parser("pending")
    args=p.parse_args()
    try:
        if args.command=="prepare": result=prepare(args.source,args.runtime)
        elif args.command=="submit": result=submit(args.job_id,args.response,args.runtime)
        elif args.command=="status":
            assert_ok(bool(re.fullmatch(r"sem_[a-f0-9]{20}",args.job_id)),"Invalid job ID")
            result=read(args.runtime/"jobs"/args.job_id/"state.json")
        else:
            root=args.runtime/"jobs"
            result=[{"job_id":v.parent.name,"folder":str(v.parent)}
                    for v in sorted(root.glob("sem_*/state.json")) if
                    read(v).get("status")=="PENDING_CHATGPT"] if root.is_dir() else []
        print(json.dumps(result,indent=2,ensure_ascii=False));return 0
    except (OSError,ValueError,RuntimeError,KeyError) as e:
        print(json.dumps({"status":"FAILED","error":str(e)},ensure_ascii=False),file=sys.stderr)
        return 2

if __name__=="__main__": raise SystemExit(main())
