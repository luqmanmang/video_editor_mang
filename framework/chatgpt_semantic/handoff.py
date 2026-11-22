#!/usr/bin/env python3
"""Private ChatGPT semantic handoff. Stdlib only; NO model API or background AI."""
from __future__ import annotations
import argparse, hashlib, json, os, re, sys, time, uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

VERSION = "1.1.0"
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
    origin=s.get("transcript_origin")
    assert_ok(origin in ("HUMAN_VERIFIED","ASR_UNVERIFIED","TEST_FIXTURE"),
              "Transcript provenance must be explicit")
    if origin=="TEST_FIXTURE":
        assert_ok(s["project_id"].startswith("smoke_"),
                  "Synthetic transcript allowed only in smoke_ fixture projects")
    assets=s.get("assets",[])
    assert_ok(isinstance(assets,list),"assets must be array")
    ids=[a.get("asset_id") for a in assets]
    assert_ok(len(ids)==len(set(ids)) and all(isinstance(x,str) and x for x in ids),
              "Invalid/duplicate asset_id")
    for section in ("media","frames","source_documents","context_packets"):
        assert_ok(isinstance(s.get(section,[]),list),section+" must be array")
        for item in s.get(section,[]):
            assert_ok(isinstance(item,dict) and isinstance(item.get("path"),str)
                      and item["path"].strip(),"Missing evidence path in "+section)
    for f in s.get("frames",[]):
        assert_ok(type(f.get("at_ms"))==int and 0<=f["at_ms"]<=dur,"Invalid frame timestamp")
    clips=s.get("clips",[])
    assert_ok(isinstance(clips,list),"clips must be an array")
    if clips:
        unique=set(); prior=0
        for c in clips:
            cid=c.get("clip_id")
            assert_ok(isinstance(cid,str) and cid not in unique and cid,
                      "Bad/duplicate clip_id")
            unique.add(cid)
            assert_ok(type(c.get("timeline_start_ms"))==int and
                      type(c.get("duration_ms"))==int and
                      c["duration_ms"]>0 and c["timeline_start_ms"]==prior,
                      "A-roll clip timing has gaps, overlaps or bad duration")
            prior+=c["duration_ms"]
        assert_ok(abs(prior-dur)<=100,"Clip sequence does not match declared video duration")
        clip_ids={c["clip_id"]:c for c in clips}
        for segment in segments:
            cid=segment["clip_id"]
            assert_ok(cid in clip_ids,"Transcript clip_id FK not found: "+cid)
            clip=clip_ids[cid]
            start=clip["timeline_start_ms"]
            assert_ok(start<=segment["start_ms"]<segment["end_ms"]<=
                      start+clip["duration_ms"],
                      "Transcript segment exceeds its linked clip boundary: "+
                      segment["segment_id"])
    return {"status":"PASS","segments":len(segments),"assets":len(assets),
            "warnings":([] if s.get("frames") else
                        ["NO_VISUAL_EVIDENCE: face-safe headline placement must stay PENDING"]) +
                        ["TIMING_UNVERIFIED: word-level/audio cut precision requires independent QC"]}

def prompt(req):
    s=req["source"]
    return (
        "# Manual ChatGPT semantic editorial review\n\n"
        "Read local_read_index.json (if pulled), request.json, then EVERY context packet via Remote Desktop Commander.\n"
        "Inspect actual reference frames where available. A filename alone is not visual inspection.\n"
        "Use project WTS/REN storytelling rules: clear promise, viewer prediction, WANT/TAPI/SO, causal payoff.\n"
        "Complete story_map in response_template.json, including factual limitations and causal_reason.\n"
        "Source is authoritative: NEVER invent dialogue, claims, studied results, word times or rights.\n"
        "Build COMPLETE non-overlapping meaning beats; cite real segment_id evidence; list justified exclusions.\n"
        "Headline: you decide exact wording and NONE/AUTO/BOXED/OUTLINE, but positioning remains pixel-QA pending.\n"
        "B-roll only from VERIFIED asset IDs and full speaking context, not isolated keywords. NONE is valid.\n"
        "Motion optional: STATIC/SUBTLE/EMPHASIS. Avoid existing aggressive crop and source captions.\n"
        "Cut guidance is not a waveform or millisecond-accurate trim; leave REVIEW if unsupported.\n"
        "Set decision_source=CHATGPT_MANUAL and review_ref to a non-secret traceable chat label.\n"
        "Write a new response.json, then submit through desktop_bridge on Windows or handoff.py remotely.\n"
        "No external model/API is called by Python. Private semantic PASS never clears human/rights gates.\n\n"
        "Project: "+s["project_id"]+"\n"
        "Viewer: "+s["brief"]["viewer"]+"\n"
        "Goal: "+s["brief"]["goal"]+"\n"
        "Job ID: "+req["job_id"]+"\n"
        "Input fingerprint: "+req["input_fingerprint"]+"\n"
    )

def prepare(source_path,runtime):
    path=Path(source_path).resolve(); s=read(path); q=check_source(s)
    files=[Path(x["path"]).resolve() for key in
           ("media","frames","source_documents","context_packets") for x in s.get(key,[])]
    hashes={}
    for p in files:
        assert_ok(p.is_file() and p.stat().st_size>0,"Missing/empty evidence: "+str(p))
        hashes[str(p)]=file_sha(p)
    for path,expected in s.get("expected_evidence_sha256",{}).items():
        assert_ok(path in hashes and hashes[path]==expected,
                  "Evidence changed after packet build; regenerate source: "+path)
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
             "decision_source":"CHATGPT_MANUAL_REQUIRED","review_ref":"REPLACE_WITH_CHAT_SESSION_REF",
             "story_map":{key:"REPLACE WITH GROUNDED CONTEXT" for key in
                          ("hook_promise","viewer_prediction","want","tapi","so",
                           "payoff","causal_reason","factual_limitations")},
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
    origin=s.get("transcript_origin")
    expected_review="SYNTHETIC_TEST" if origin=="TEST_FIXTURE" else "CHATGPT_MANUAL"
    assert_ok(r.get("decision_source")==expected_review,
              "Decision must be attributed to "+expected_review)
    assert_ok(isinstance(r.get("review_ref"),str) and
              len(r["review_ref"].strip())>=8 and
              "REPLACE_WITH" not in r["review_ref"],
              "Missing explicit decision review reference")
    story_map=r.get("story_map")
    assert_ok(isinstance(story_map,dict),"ChatGPT must provide grounded WTS story_map")
    for key in ("hook_promise","viewer_prediction","want","tapi","so","payoff",
                "causal_reason","factual_limitations"):
        value=story_map.get(key)
        assert_ok(isinstance(value,str) and len(value.strip())>=8 and
                  "REPLACE WITH" not in value.upper() and
                  "FILL_FROM" not in value.upper() and
                  "TODO" not in value.upper(),
                  "Missing/unfilled story_map field: "+key)
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
        # Failed validations are evidence too. Keep them local for RCA; never alter
        # a previously validated decision or pretend failure is semantic PASS.
        try:
            if args.command=="submit" and re.fullmatch(r"sem_[a-f0-9]{20}",args.job_id):
                folder=args.runtime/"jobs"/args.job_id
                if folder.is_dir(): log(folder,"SUBMIT_REJECTED",reason=str(e))
            elif args.command=="prepare":
                args.runtime.mkdir(parents=True,exist_ok=True)
                log(args.runtime,"PREPARE_REJECTED",reason=str(e))
        except OSError:
            pass
        print(json.dumps({"status":"FAILED","error":str(e)},ensure_ascii=False),file=sys.stderr)
        return 2

if __name__=="__main__": raise SystemExit(main())
