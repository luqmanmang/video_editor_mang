#!/usr/bin/env python3
"""Codespace-only Video Studio private production runner.

Deterministic execution is separate from ChatGPT reasoning. A legacy-regression
manifest can test migration but NEVER grants semantic/editorial or publication
approval. All source/render/QA/temporary files stay in Codespace's .runtime.
Only a checksum-verified MP4 is eligible for Windows delivery.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid

CANVAS=(720,1280,30)
FONT=Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
LOCK=threading.RLock()
RUN_ROOT=Path(__file__).resolve().parents[1]/".runtime"/"production_runs"
INPUT_ROOT=Path(__file__).resolve().parents[1]/".runtime"/"production_assets"/"kauthar"

def require(ok,reason):
    if not ok: raise ValueError(reason)
def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))
def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()
def atomic(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+"."+uuid.uuid4().hex+".tmp")
    try:
        tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        os.replace(tmp,path)
    finally: tmp.unlink(missing_ok=True)
def ts():return datetime.now(timezone.utc).isoformat(timespec="seconds")
def log(folder,event,**fields):
    with LOCK:
        with (folder/"events.jsonl").open("a",encoding="utf-8") as f:
            f.write(json.dumps({"at":ts(),"event":event,**fields},ensure_ascii=False)+"\n")
def signal(kind,key,value=""):
    if kind=="STAGE": print("STAGE:"+str(key),flush=True)
    else: print(f"{kind}:{key}={value}",flush=True)
def within(path,root):
    p=Path(path).resolve(); r=Path(root).resolve()
    require(p.is_relative_to(r),"Path must remain inside private Codespace runtime: "+str(p))
    return p
def run_cmd(cmd,*,duration_limit=300):
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=duration_limit)
    require(p.returncode==0,"Command failed "+str(p.returncode)+": "+p.stderr[-750:])
    return p.stdout
def probe(path):
    return json.loads(run_cmd(["ffprobe","-v","error","-show_format","-show_streams",
                               "-of","json",str(path)],duration_limit=40))

def validate_job(job,assets_root):
    require(isinstance(job,dict),"Job must be object")
    key=job.get("key","")
    require(isinstance(key,str) and re.fullmatch(r"[a-z][a-z0-9_]{2,50}",key),"Invalid job key")
    video_id=str(job.get("video_id",""))
    require(re.fullmatch(r"\d{16,21}",video_id),"Invalid video_id")
    require(job.get("output")=={"width":720,"height":1280,"fps":30},
            "Output 720x1280 at 30 FPS is mandatory")
    require(job.get("mode") in ("PRIVATE_REGRESSION","CHATGPT_VALIDATED"),
            "Explicit private/validated decision mode required")
    require(job.get("source_rights")=="UNCLEARED_PRIVATE_ONLY",
            "This runner only prepares private review footage")
    if job["mode"]=="CHATGPT_VALIDATED":
        require(isinstance(job.get("semantic_job_dir"),str),
                "ChatGPT job must reference an actual validated handoff folder")
    else:
        require(job.get("semantic_status")=="NOT_VERIFIED",
                "Legacy regression cannot claim completed semantic review")
    cuts=job.get("cut_ranges_seconds")
    require(isinstance(cuts,list) and cuts and len(cuts)<=16,"Invalid cut list")
    previous=-1
    for pair in cuts:
        require(isinstance(pair,list) and len(pair)==2,"Each cut is [start,end]")
        a,b=pair
        require(type(a) in (int,float) and type(b) in (int,float)
                and 0<=a<b and a>=previous,"Cut ranges must be ordered/non-overlapping")
        previous=b
    title=job.get("headline_lines")
    require(isinstance(title,list) and 1<=len(title)<=3 and
            all(isinstance(t,str) and 3<=len(t.strip())<=48 and
                "\n" not in t for t in title),"Headline text invalid")
    card=job.get("headline_card",{})
    require(type(card.get("bottom"))==int and 240<=card["bottom"]<=410,
            "Headline card bottom must be geometrically bounded")
    require(job.get("motion") in ("STATIC","SUBTLE"),
            "Only validated limited motion permitted")
    require(type(job.get("headline_seconds")) in (int,float) and
            0<job["headline_seconds"]<=9,"Headline display duration invalid")
    source_dir=within(Path(assets_root)/video_id,assets_root)
    source=within(source_dir/"original.mp4",assets_root)
    manifest=within(source_dir/"source_manifest.json",assets_root)
    transcript=within(source_dir/"transcript.json",assets_root)
    for p in (source,manifest,transcript):
        require(p.is_file() and p.stat().st_size>0,"Missing source evidence "+str(p))
    meta=read(manifest); asr=read(transcript)
    require(meta.get("video_id")==video_id and meta.get("uploader")=="kautharrozmal",
            "Wrong source owner/ID")
    require(sha(source)==meta.get("original_mp4_sha256"),
            "Source hash changed "+video_id)
    if job["mode"]=="CHATGPT_VALIDATED":
        from framework.chatgpt_semantic.handoff import check_response,verify_lineage
        job_dir=within(job["semantic_job_dir"],
                       Path(__file__).resolve().parents[1]/".runtime")
        require((job_dir/"request.json").is_file() and
                (job_dir/"state.json").is_file(),"ChatGPT handoff evidence absent")
        verify_lineage(job_dir)
        state=read(job_dir/"state.json")
        require(state.get("status")=="VALIDATED_FOR_PRIVATE_PREVIEW",
                "ChatGPT semantic review not validated")
        decision_file=within(state["active_decision"],job_dir)
        require(sha(decision_file)==state.get("decision_sha256"),
                "ChatGPT decision hash mismatch")
        decision=read(decision_file)
        req=read(job_dir/"request.json")
        check_response(decision,req)
        media_paths={str(Path(m["path"]).resolve()) for m in req["source"].get("media",[])}
        require(str(source) in media_paths,
                "Validated semantic review not linked to this exact source video")
        matched_text=" ".join(job["headline_lines"]).casefold()
        accepted=[" ".join(b["headline"].get("text","").split()).casefold()
                  for b in decision["beats"] if b["headline"]["style_hint"]!="NONE"]
        require(matched_text in accepted,
                "Edit-plan headline not equal to validated ChatGPT semantic headline")
        require(job.get("cut_approval")=="HUMAN_WAVEFORM_APPROVED" or
                job.get("cut_ranges_seconds")==[[0,meta["media_probe"]["duration_ms"]/1000]],
                "Precision cuts require separate human waveform approval")
    require(isinstance(asr.get("segments"),list) and len(asr["segments"])>0,
            "Actual transcript segments missing")
    require(asr.get("human_verbatim_verified") is not True or job["mode"]=="CHATGPT_VALIDATED",
            "Unexpected source provenance")
    duration=meta["media_probe"]["duration_ms"]/1000
    require(cuts[-1][1]<=duration+.1,"Cut exceeds source duration")
    # These are ASR-based migration cut boundaries, not sample-accurate human QC.
    for a,b in cuts:
        for point,field in ((a,"start_ms"),(b,"end_ms")):
            if not point: continue
            err=min(abs(point*1000-s[field]) for s in asr["segments"])
            require(err<=250,"Cut is not grounded near an actual transcript boundary")
    brolls=job.get("broll",[])
    require(isinstance(brolls,list),"B-roll selection must be an array")
    for item in brolls:
        require(item.get("license_status")=="VERIFIED" and
                item.get("semantic_approved") is True and
                item.get("visual_approved") is True and
                item.get("caption_verified") is True,
                "B-roll requires rights + semantic + visual + speech QA")
        require(re.fullmatch(r"[0-9a-f]{64}",str(item.get("sha256",""))),
                "B-roll requires original SHA-256")
        asset=within(assets_root/item["path"],assets_root)
        require(asset.is_file() and sha(asset)==item["sha256"],"B-roll file/hash mismatch")
        require(type(item.get("timeline_start_sec")) in (int,float) and
                type(item.get("duration_sec")) in (int,float) and
                item["timeline_start_sec"]>=0 and item["duration_sec"]>0,
                "B-roll timing missing")
    return {"key":key,"source":str(source),"source_sha256":sha(source),
            "transcript_sha256":sha(transcript),"manifest_sha256":sha(manifest),
            "source_duration_sec":duration,"cuts":cuts,
            "duration_sec":sum(b-a for a,b in cuts),"brolls":brolls,"job":job}

def ffmpeg_graph(job,work):
    cuts=job["cut_ranges_seconds"]; n=len(cuts)
    chain=[]
    if n>1:
        chain.append(f"[0:v]split={n}"+ "".join(f"[vs{i}]" for i in range(n))+";")
        chain.append(f"[0:a]asplit={n}"+ "".join(f"[as{i}]" for i in range(n))+";")
    for i,(start,end) in enumerate(cuts):
        sv=f"[vs{i}]" if n>1 else "[0:v]"
        sa=f"[as{i}]" if n>1 else "[0:a]"
        chain.append(f"{sv}trim=start={start:.3f}:end={end:.3f},setpts=PTS-STARTPTS[v{i}];")
        chain.append(f"{sa}atrim=start={start:.3f}:end={end:.3f},asetpts=PTS-STARTPTS[a{i}];")
    if n>1:
        chain.append("".join(f"[v{i}][a{i}]" for i in range(n))+
                     f"concat=n={n}:v=1:a=1[cv][ca];")
    else:
        chain.append("[v0]null[cv];[a0]anull[ca];")
    visual="[cv]fps=30,scale=720:1280:flags=lanczos,setsar=1"
    if job["motion"]=="SUBTLE":
        # Legacy private test only; proper sentence-keyframed motion remains
        # under ChatGPT timeline compiler, not claimed by this regression.
        zoom=("1+0.022*if(lt(mod(on,210),60),mod(on,210)/60,"
              "if(lt(mod(on,210),150),1,(210-mod(on,210))/60))")
        visual+=",zoompan=z='"+zoom+"':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':d=1:s=720x1280:fps=30"
    visual+=",format=yuv420p[vbase];"
    chain.append(visual)
    # Optional stock B-roll; audio stays from the original. No stock source
    # unless an explicit ChatGPT-reviewed visual/license/caption manifest passes.
    visual_ref="[vbase]"
    for i,item in enumerate(job.get("broll",[])):
        stream=f"[{i+1}:v]"
        start=item["timeline_start_sec"]; end=start+item["duration_sec"]
        chain.append(f"{stream}trim=duration={item['duration_sec']:.3f},"
                     f"setpts=PTS-STARTPTS+{start:.3f}/TB,"
                     "fps=30,scale=720:1280:force_original_aspect_ratio=increase,"
                     f"crop=720:1280[br{i}];")
        chain.append(f"{visual_ref}[br{i}]overlay=eof_action=pass:"
                     f"enable='between(t,{start:.3f},{end:.3f})'[bo{i}];")
        visual_ref=f"[bo{i}]"
    bottom=job["headline_card"]["bottom"]; top=110
    # Existing burned headline is obscured only by an intentionally designed
    # graphic card. Face collision is still subject to actual human review.
    layer=(f"{visual_ref}drawbox=x=58:y={top}:w=604:h={bottom-top}:"
           f"color=white:t=fill:enable='lt(t,{job['headline_seconds']:.3f})'")
    fontsize=34 if max(map(len,job["headline_lines"]))>18 else 38
    count=len(job["headline_lines"])
    rows=[int((top+bottom)/2 + (idx-(count-1)/2)*48-19) for idx in range(count)]
    for i,(line,y) in enumerate(zip(job["headline_lines"],rows)):
        file=work/f"headline_{i}.txt"
        file.write_text(line,encoding="utf-8")
        layer+=(
            f",drawtext=fontfile={FONT}:textfile={file}:fontcolor=0x15191c:"
            f"fontsize={fontsize}:x=(w-text_w)/2:y={y}:"
            f"enable='lt(t,{job['headline_seconds']:.3f})'")
    chain.append(layer+",format=yuv420p[vout];")
    chain.append("[ca]loudnorm=I=-16:TP=-1.5:LRA=11:linear=true[aout]")
    return "".join(chain)

def audio_video_qa(video,expected):
    data=probe(video)
    streams=data.get("streams",[])
    v=next((x for x in streams if x.get("codec_type")=="video"),None)
    a=next((x for x in streams if x.get("codec_type")=="audio"),None)
    require(v and a and (v.get("width"),v.get("height"),v.get("codec_name"))==
            (720,1280,"h264") and a.get("codec_name")=="aac","720p codecs/dimensions invalid")
    duration=float(data["format"]["duration"])
    require(abs(duration-expected)<.5,"Unexpected output duration")
    decode=subprocess.run(["ffmpeg","-v","error","-i",str(video),
                           "-f","null","-"],capture_output=True,text=True)
    require(decode.returncode==0,"Full decode failed: "+decode.stderr[-350:])
    audio=subprocess.run(["ffmpeg","-nostats","-v","info","-i",str(video),"-vn",
                          "-af","loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
                          "-f","null","-"],capture_output=True,text=True)
    require(audio.returncode==0,"Loudness analysis failed")
    chunks=re.findall(r'\{\s*"input_i"\s*:.*?\}',audio.stderr,re.S)
    require(chunks,"Audio stats absent")
    stats=json.loads(chunks[-1]); lufs=float(stats["input_i"]);peak=float(stats["input_tp"])
    require(abs(lufs+16)<=2.1 and peak<=-1.0,
            "Audio outside private test tolerance: "+str((lufs,peak)))
    return {"status":"PASS","width":720,"height":1280,"fps":30,
            "video_codec":"h264","audio_codec":"aac","duration_sec":duration,
            "full_decode":"PASS","lufs":lufs,"true_peak_dbtp":peak}

class Batch:
    def __init__(self,plan,assets_root=INPUT_ROOT,runs_root=RUN_ROOT):
        require(sys.platform.startswith("linux") and
                Path("/workspaces/video_editor_mang").is_dir(),
                "Video processing is prohibited on Windows; use the Codespace worker")
        self.plan_file=Path(plan).resolve()
        self.assets_root=Path(assets_root).resolve()
        self.runs_root=Path(runs_root).resolve()
        # Input and work root MUST be Codespace ignored .runtime, not Windows.
        private=Path(__file__).resolve().parents[1]/".runtime"
        within(self.assets_root,private);within(self.runs_root,private)
        within(self.plan_file,private)
        self.plan=read(self.plan_file)
        require(self.plan.get("schema_version")=="1.0","Private batch schema mismatch")
        jobs=self.plan.get("jobs")
        require(isinstance(jobs,list) and jobs and len(jobs)<=20,"1..20 jobs per batch")
        require(len({j.get("key") for j in jobs})==len(jobs),"Duplicate job keys")
        version=sha(__file__)
        self.run_id="cs_"+hashlib.sha256((sha(self.plan_file)+version).encode()).hexdigest()[:18]
        self.folder=self.runs_root/self.run_id
        self.workers=int(self.plan.get("render_workers",1))
        require(1<=self.workers<=2,"Codespace maximum two concurrent renders")
        self.state_file=self.folder/"checkpoint.json"
        self.plan_hash=sha(self.plan_file);self.code_hash=version
        self.results={}
    def status(self,key,status,**values):
        with LOCK:
            st=read(self.state_file)
            st["jobs"].setdefault(key,{})
            st["jobs"][key].update({"status":status,"at":ts(),**values})
            atomic(self.state_file,st)
            log(self.folder,"JOB_"+status,key=key,**values)
    def start(self):
        self.folder.mkdir(parents=True,exist_ok=True)
        (self.folder/"outputs").mkdir(exist_ok=True)
        if not self.state_file.exists():
            atomic(self.state_file,{"run_id":self.run_id,
                  "manifest_sha256":self.plan_hash,"code_sha256":self.code_hash,
                  "status":"RUNNING","jobs":{},"started_at":ts(),
                  "rights":"UNCLEARED","creative_review":"PENDING"})
        else:
            st=read(self.state_file)
            require(st["manifest_sha256"]==self.plan_hash and
                    st["code_sha256"]==self.code_hash,"Stale checkpoint; new run required")
        return self.run_id
    def render_job(self,item):
        key=item["key"]
        clip=self.results[key]
        work=self.folder/"work"/key;work.mkdir(parents=True,exist_ok=True)
        out=self.folder/"outputs"/(key+".mp4")
        qa_file=self.folder/"qa"/(key+".json")
        if out.is_file() and qa_file.is_file():
            old=read(qa_file)
            if old.get("status")=="PASS" and old.get("sha256")==sha(out) and \
                old.get("source_sha256")==clip["source_sha256"] and \
                old.get("manifest_sha256")==self.plan_hash and \
                old.get("code_sha256")==self.code_hash:
                self.status(key,"REUSED_VERIFIED",sha256=old["sha256"])
                signal("GATE",key+"_idempotent","PASS")
                return old
            raise ValueError("Existing output conflicts with evidence; cannot overwrite: "+key)
        require(not out.exists(),"Unverified output exists; never overwrite")
        tmp=work/"candidate.partial.mp4"
        if tmp.exists():
            # Failed/interrupted render is not success; safe to remove transient
            # in the SAME run folder after verifying no other active worker.
            tmp.unlink()
        filters=ffmpeg_graph(item,work)
        args=["ffmpeg","-y","-hide_banner","-nostats","-loglevel","error",
              "-i",clip["source"]]
        for b in item.get("broll",[]):
            args.extend(["-i",str(within(self.assets_root/b["path"],self.assets_root))])
        args.extend(["-filter_complex",filters,
                     "-map","[vout]","-map","[aout]",
                     "-c:v","libx264","-preset","veryfast","-threads","2",
                     "-crf","24","-maxrate","2400k","-bufsize","4800k",
                     "-pix_fmt","yuv420p","-r","30",
                     "-c:a","aac","-b:a","128k","-ar","48000","-ac","2",
                     "-movflags","+faststart","-shortest","-t",
                     f"{clip['duration_sec']+.08:.3f}",
                     "-progress","pipe:1",str(tmp)])
        self.status(key,"RENDERING")
        p=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                           text=True,errors="replace")
        tail=[];last_progress=-1
        try:
            for line in p.stdout:
                line=line.strip();tail.append(line);tail=tail[-18:]
                if line.startswith("frame="):
                    try: progress=int(float(line.split("=",1)[1])*100/max(1,clip["duration_sec"]*30))
                    except ValueError: continue
                    if progress//10>last_progress:
                        last_progress=progress//10
                        signal("METRIC",key+"_frame_progress",min(100,progress))
            exit_code=p.wait()
            require(exit_code==0,"FFmpeg failed "+key+": "+str(tail))
        finally:
            if p.poll() is None: p.kill();p.wait()
        require(tmp.is_file() and tmp.stat().st_size>100_000,"Render missing/empty: "+key)
        self.status(key,"TECHNICAL_QA")
        qa=audio_video_qa(tmp,clip["duration_sec"])
        qa.update({"key":key,"source_sha256":clip["source_sha256"],
                   "transcript_sha256":clip["transcript_sha256"],
                   "manifest_sha256":self.plan_hash,"code_sha256":self.code_hash,
                   "sha256":sha(tmp),"bytes":tmp.stat().st_size,
                   "mode":item["mode"],"semantic_review":
                       "NOT_VERIFIED" if item["mode"]=="PRIVATE_REGRESSION"
                       else "STRUCTURAL_VALIDATED_ONLY",
                   "human_review":"PENDING","source_rights":"UNCLEARED",
                   "publish_allowed":False})
        qa_file.parent.mkdir(parents=True,exist_ok=True)
        atomic(qa_file,qa)
        os.replace(tmp,out)
        self.status(key,"TECHNICAL_PASS_PRIVATE",sha256=qa["sha256"])
        signal("GATE",key+"_720p_decode","PASS")
        return qa
    def run(self,preflight_only=False):
        self.start()
        print("RUN_ID:"+self.run_id,flush=True)
        signal("STAGE","SOURCE_INTEGRITY")
        with ThreadPoolExecutor(max_workers=4) as pool:
            futs={pool.submit(validate_job,j,self.assets_root):j["key"] for j in self.plan["jobs"]}
            failures=[]
            for f in as_completed(futs):
                key=futs[f]
                try:
                    info=f.result();self.results[key]=info
                    self.status(key,"SOURCE_PASS",source_sha256=info["source_sha256"])
                    signal("GATE",key+"_source","PASS")
                except Exception as e:
                    failures.append((key,str(e)))
                    self.status(key,"SOURCE_FAILED",reason=str(e))
                    signal("GATE",key+"_source","FAIL")
        require(not failures,"Preflight failed: "+str(failures))
        if preflight_only:
            signal("GATE","five_source_preflight","PASS")
            return {"run_id":self.run_id,"status":"PREFLIGHT_PASS","jobs":list(self.results)}
        signal("STAGE","BOUNDED_CODESPACE_RENDER")
        completed={};errors=[]
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            futs={pool.submit(self.render_job,j):j["key"] for j in self.plan["jobs"]}
            for f in as_completed(futs):
                key=futs[f]
                try:
                    completed[key]=f.result()
                    signal("METRIC","completed_jobs",len(completed))
                except Exception as e:
                    self.status(key,"FAILED",reason=str(e))
                    errors.append((key,str(e)))
                    signal("GATE",key+"_technical","FAIL")
        state=read(self.state_file)
        state["status"]="TECHNICAL_PASS_PRIVATE" if not errors else "PARTIAL_FAILED"
        state["finished_at"]=ts()
        atomic(self.state_file,state)
        require(not errors,"Some jobs failed: "+str(errors))
        manifest={"run_id":self.run_id,"status":"TECHNICAL_PASS_PRIVATE",
                  "job_count":len(completed),"rights":"UNCLEARED",
                  "creative_review":"PENDING","only_windows_delivery":"VERIFIED_MP4",
                  "outputs":{k:{"path":str(self.folder/"outputs"/(k+".mp4")),
                                "sha256":v["sha256"],"bytes":v["bytes"],
                                "source_sha256":v["source_sha256"],
                                "technical_status":v["status"]} for k,v in completed.items()}}
        atomic(self.folder/"delivery_manifest.json",manifest)
        signal("GATE","codespace_batch_technical","PASS")
        signal("GATE","human_creative","PENDING")
        signal("GATE","creator_rights","BLOCKED")
        return manifest

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--plan",required=True)
    ap.add_argument("--preflight-only",action="store_true")
    ap.add_argument("--assets-root",type=Path,default=INPUT_ROOT)
    args=ap.parse_args()
    try:
        b=Batch(args.plan,args.assets_root)
        result=b.run(preflight_only=args.preflight_only)
        print(json.dumps(result,indent=2),flush=True)
        return 0
    except (OSError,ValueError,RuntimeError,KeyError,subprocess.TimeoutExpired) as exc:
        signal("GATE","production_pipeline","FAIL")
        print("ERROR:"+repr(exc),file=sys.stderr,flush=True)
        return 2
if __name__=="__main__":raise SystemExit(main())
