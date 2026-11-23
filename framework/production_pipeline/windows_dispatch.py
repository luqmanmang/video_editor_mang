#!/usr/bin/env python3
"""Windows dashboard transport only: run Codespace worker and verify MP4 delivery.

NO local FFmpeg, Pillow, ASR or rendering. GitHub CLI must already be
authenticated and Codespace must be running. No local private transcript or
QA files are written to the output folder.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import subprocess
import sys
import tempfile
import uuid

REPO="/workspaces/video_editor_mang"
RUNS=REPO+"/framework/.runtime/production_runs"
RUNID=re.compile(r"^cs_[a-f0-9]{18}$")
CODESPACE=re.compile(r"^[A-Za-z0-9_-]{8,100}$")
PRIVATE_PLAN=re.compile(r"^/workspaces/video_editor_mang/framework/\.runtime/[a-zA-Z0-9_./-]+\.json$")

def require(test,message):
    if not test: raise ValueError(message)
def checksum(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()
def remote_copy(cs,remote,local):
    require(remote.startswith(RUNS+"/"),"Refusing export from non-runtime path")
    require(".." not in PurePosixPath(remote).parts,"Refusing traversal")
    cmd=["gh","codespace","cp","-e","-c",cs,
         "remote:"+remote,str(local)]
    code=subprocess.run(cmd,timeout=300)
    require(code.returncode==0,"Codespace transfer failed: "+remote)
    require(Path(local).is_file() and Path(local).stat().st_size>0,
            "Codespace transfer produced no file")
def deliver(cs,run_id,out_dir,expected_count=None):
    require(bool(CODESPACE.fullmatch(cs)),"Invalid Codespace ID")
    require(bool(RUNID.fullmatch(run_id)),"Invalid run ID")
    folder=RUNS+"/"+run_id
    out_dir=Path(out_dir).resolve()
    results={}
    with tempfile.TemporaryDirectory(prefix="cs_verified_") as temp:
        manifest=Path(temp)/"manifest.json"
        remote_copy(cs,folder+"/delivery_manifest.json",manifest)
        info=json.loads(manifest.read_text(encoding="utf-8"))
        outputs=info.get("outputs")
        require(info.get("run_id")==run_id and info.get("status")=="TECHNICAL_PASS_PRIVATE"
                and info.get("rights")=="UNCLEARED" and
                info.get("creative_review")=="PENDING"
                and isinstance(outputs,dict) and outputs,
                "Remote delivery manifest lacks private QA proof")
        if expected_count is not None:
            require(len(outputs)==expected_count,
                    "Number of outputs differs from requested jobs")
        require(len(outputs)==len(set(outputs)),"Duplicate output key")
        for index,(key,item) in enumerate(sorted(outputs.items()),1):
            require(re.fullmatch(r"[a-z][a-z0-9_]{2,50}",key),"Unsafe job name")
            src=item.get("path","")
            require(src==folder+"/outputs/"+key+".mp4",
                    "Remote output path is not a canonical video")
            expected=item.get("sha256")
            require(re.fullmatch(r"[a-f0-9]{64}",str(expected)) and
                    item.get("technical_status")=="PASS" and
                    item.get("bytes",0)>100_000,
                    "Remote SHA/QA receipt invalid")
            file=out_dir/(key+"_720p_private.mp4")
            if file.is_file():
                require(file.stat().st_size==item["bytes"] and checksum(file)==expected,
                        "Existing local output does not match verified remote version")
                print("GATE:"+key+"_local_idempotent=PASS",flush=True)
                results[key]=str(file)
                continue
            out_dir.mkdir(parents=True,exist_ok=True)
            partial=out_dir/(key+"."+uuid.uuid4().hex+".partial.mp4")
            try:
                remote_copy(cs,src,partial)
                require(partial.stat().st_size==item["bytes"] and checksum(partial)==expected,
                        "Video transfer hash/size mismatch: "+key)
                os.replace(partial,file)
            finally:
                partial.unlink(missing_ok=True)
            results[key]=str(file)
            print("GATE:"+key+"_transfer_sha256=PASS",flush=True)
            print("METRIC:"+key+"_delivered_bytes="+str(item["bytes"]),flush=True)
            print("PROGRESS:"+str(int(index*100/len(outputs))),flush=True)
    print("GATE:verified_mp4_only_windows=PASS",flush=True)
    return {"status":"DELIVERED_VERIFIED_MP4_ONLY",
            "count":len(results),"local_video_paths":results}

def remote_run(cs,plan,preflight_only=False):
    require(bool(CODESPACE.fullmatch(cs)),"Invalid Codespace ID")
    require(bool(PRIVATE_PLAN.fullmatch(plan)) and
            ".." not in PurePosixPath(plan).parts,"Plan must be private Codespace JSON")
    command=(f"cd {REPO} && python3 -m framework.production_pipeline.runner "
             f"--plan {shlex.quote(plan)}")
    if preflight_only:command+=" --preflight-only"
    print("STAGE:CODESPACE_WORKER",flush=True)
    proc=subprocess.Popen(["gh","codespace","ssh","-c",cs,"--",command],
                          stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                          text=True,errors="replace")
    run_id=None;tail=[]
    for line in proc.stdout:
        text=line.rstrip()
        print(text,flush=True)
        tail.append(text);tail=tail[-30:]
        found=re.search(r"\bRUN_ID:(cs_[a-f0-9]{18})\b",text)
        if found: run_id=found.group(1)
    status=proc.wait()
    require(status==0,"Codespace worker failed exit "+str(status)+"; "+str(tail[-6:]))
    require(run_id is not None,"Codespace runner did not identify run_id")
    return run_id

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--codespace",default="psychic-space-winner-p7gr9q5vj4gq27rq7")
    p.add_argument("--remote-plan")
    p.add_argument("--deliver-run")
    p.add_argument("--preflight-only",action="store_true")
    p.add_argument("--expected-count",type=int)
    p.add_argument("--output-root",default=
                   r"D:\Thread Automation\Video_Clipping_Studio\outputs\review")
    args=p.parse_args()
    try:
        require(bool(args.remote_plan)^bool(args.deliver_run),
                "Choose remote-plan or deliver-run")
        if args.remote_plan:
            run_id=remote_run(args.codespace,args.remote_plan,args.preflight_only)
            if args.preflight_only:
                result={"status":"PREFLIGHT_ONLY","run_id":run_id}
            else:
                result=deliver(args.codespace,run_id,
                               Path(args.output_root)/("codespace_"+run_id),
                               args.expected_count)
        else:
            result=deliver(args.codespace,args.deliver_run,
                           Path(args.output_root)/("codespace_"+args.deliver_run),
                           args.expected_count)
        print(json.dumps(result,indent=2,ensure_ascii=False),flush=True)
        return 0
    except (ValueError,OSError,RuntimeError,subprocess.TimeoutExpired,KeyError) as e:
        print("GATE:codespace_verified_delivery=FAIL",flush=True)
        print("ERROR:"+str(e),file=sys.stderr,flush=True)
        return 2

if __name__=="__main__":raise SystemExit(main())
