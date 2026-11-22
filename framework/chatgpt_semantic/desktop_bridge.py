#!/usr/bin/env python3
"""Manual Desktop Commander <-> Codespace bridge; no API or automatic AI calls.

Read data on Windows; ChatGPT edits response locally; validator stays remote
where source video hashes can be checked immediately before decisions are sealed.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

from .handoff import RUNTIME, read, save, file_sha, assert_ok

REMOTE_BASE="/workspaces/video_editor_mang/"
REMOTE_JOB_ROOT=REMOTE_BASE+"framework/.runtime/"
JOB=re.compile(r"^sem_[a-f0-9]{20}$")
CS=re.compile(r"^[A-Za-z0-9_-]{6,100}$")
REMOTE_SAFE=re.compile(r"^/[A-Za-z0-9_./-]{1,400}$")

def check_path(path,root=REMOTE_BASE):
    assert_ok(isinstance(path,str) and bool(REMOTE_SAFE.fullmatch(path)) and
              ".." not in PurePosixPath(path).parts and path.startswith(root),
              "Remote path disallowed: "+str(path))
    return path

def run(cmd,timeout=180):
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout)
    if p.returncode:
        raise RuntimeError("Command failed exit="+str(p.returncode)+": "+
                           " ".join(cmd[:5])+"; "+p.stderr[-650:])
    return p.stdout

def copy(cs, remote, local, recursive=False):
    check_path(remote)
    local=Path(local)
    local.parent.mkdir(parents=True,exist_ok=True)
    cmd=["gh","codespace","cp","-e","-c",cs]
    if recursive: cmd.append("-r")
    cmd += ["remote:"+remote,str(local)]
    run(cmd,timeout=240)

def get_cs(cs):
    assert_ok(bool(CS.fullmatch(cs)),"Invalid Codespace name")
    return cs

def pull(cs,remote_job_dir,runtime):
    cs=get_cs(cs)
    remote_job_dir=check_path(remote_job_dir,REMOTE_JOB_ROOT).rstrip("/")
    job=PurePosixPath(remote_job_dir).name
    assert_ok(bool(JOB.fullmatch(job)),"Invalid remote semantic job directory")
    runtime=Path(runtime).resolve()
    local=runtime/"jobs"/job
    if (local/"bridge_state.json").is_file():
        state=read(local/"bridge_state.json")
        assert_ok(state.get("remote_job_dir")==remote_job_dir and
                  state.get("codespace")==cs,"Local job conflicts with remote job")
        assert_ok(read(local/"request.json")["input_fingerprint"]==state["input_fingerprint"],
                  "Local semantic request no longer matches original fingerprint")
        assert_ok(state.get("local_request_sha256")==file_sha(local/"request.json"),
                  "Local request checksum missing/mismatched; manual inspection required")
        for packet in read(local/"request.json")["source"].get("context_packets",[]):
            check=local/"context_packets"/PurePosixPath(packet["path"]).name
            assert_ok(check.is_file() and file_sha(check)==packet["sha256"],
                      "Local context packet changed: "+str(check))
        return {"status":"REUSED_LOCAL_COPY","local_job":str(local),
                "fingerprint":state["input_fingerprint"]}
    incoming=runtime/"incoming"
    incoming.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="sem_pull_",dir=incoming) as tmp:
        copy(cs,remote_job_dir,tmp,recursive=True)
        source=Path(tmp)/job
        assert_ok((source/"request.json").is_file(),"Remote folder copy lacks request.json")
        req=read(source/"request.json")
        assert_ok(req.get("job_id")==job and bool(re.fullmatch(r"[a-f0-9]{64}",req.get("input_fingerprint",""))),
                  "Invalid job ID or source fingerprint")
        assert_ok(read(source/"lineage.json").get("input_fingerprint")==req["input_fingerprint"],
                  "Remote lineage mismatch")
        local_index={"job_id":job,"source_fingerprint":req["input_fingerprint"],
                     "context_packets":[],"frames":[],"source_request":str(local/"request.json")}
        packets_dir=source/"context_packets"
        packets_dir.mkdir(exist_ok=True)
        for packet in req["source"].get("context_packets",[]):
            remote=check_path(packet["path"],REMOTE_JOB_ROOT)
            filename=PurePosixPath(remote).name
            assert_ok(bool(re.fullmatch(r"packet_[0-9]{3}\.json",filename)),
                      "Unsafe packet filename")
            target=packets_dir/filename
            copy(cs,remote,target)
            assert_ok(file_sha(target)==packet["sha256"],"Packet checksum mismatch")
            local_index["context_packets"].append(str(local/"context_packets"/filename))
        frame_dir=source/"frames"
        frame_dir.mkdir(exist_ok=True)
        hashes=read(source/"lineage.json")["evidence_sha256"]
        for ix,frame in enumerate(req["source"].get("frames",[]),1):
            remote=check_path(frame["path"])
            path=frame_dir/("frame_%03d"%ix+PurePosixPath(remote).suffix.lower())
            assert_ok(path.suffix in (".png",".jpg",".jpeg",".webp"),"Unexpected image extension")
            copy(cs,remote,path)
            assert_ok(path.stat().st_size<=6_000_000,"Frame too large to inspect safely")
            assert_ok(file_sha(path)==hashes.get(remote),"Frame checksum mismatch")
            local_index["frames"].append({"local_path":str(local/"frames"/path.name),
                                          "at_ms":frame["at_ms"]})
        save(source/"local_read_index.json",local_index)
        save(source/"bridge_state.json",{
            "job_id":job,"input_fingerprint":req["input_fingerprint"],
            "remote_job_dir":remote_job_dir,"codespace":cs,
            "local_request_sha256":file_sha(source/"request.json"),
            "status":"PULLED_FOR_CHATGPT_REVIEW"})
        local.parent.mkdir(parents=True,exist_ok=True)
        assert_ok(not local.exists(),"Local destination changed concurrently")
        shutil.move(str(source),str(local))
    return {"status":"PULLED_FOR_CHATGPT_REVIEW","local_job":str(local),
            "fingerprint":req["input_fingerprint"],"packet_count":len(local_index["context_packets"]),
            "frame_count":len(local_index["frames"])}

def push_decision(local_job,response_path):
    local_job=Path(local_job).resolve()
    mapping=read(local_job/"bridge_state.json")
    cs=get_cs(mapping["codespace"])
    remote=check_path(mapping["remote_job_dir"],REMOTE_JOB_ROOT)
    job=PurePosixPath(remote).name
    response_path=Path(response_path).resolve()
    r=read(response_path)
    assert_ok(r.get("job_id")==job and
              r.get("input_fingerprint")==mapping["input_fingerprint"],
              "Wrong response job or stale source fingerprint")
    assert_ok(r.get("decision_source")=="CHATGPT_MANUAL",
              "Desktop bridge accepts only real manually authored ChatGPT decisions")
    remote_response=remote+"/response_from_chatgpt.json"
    cmd=["gh","codespace","cp","-e","-c",cs,str(response_path),"remote:"+check_path(remote_response,REMOTE_JOB_ROOT)]
    run(cmd)
    runtime=PurePosixPath(remote).parent.parent
    remote_cmd=("cd "+shlex.quote(REMOTE_BASE.rstrip("/"))+
                " && python3 -m framework.chatgpt_semantic.handoff --runtime "+
                shlex.quote(str(runtime))+" submit --job-id "+shlex.quote(job)+
                " --response "+shlex.quote(remote_response))
    outcome=run(["gh","codespace","ssh","-c",cs,"--",remote_cmd],timeout=180)
    reply=json.loads(outcome)
    assert_ok(reply.get("status") in ("VALIDATED_FOR_PRIVATE_PREVIEW","REUSED_VALIDATED"),
              "Remote semantic submission did not PASS")
    # Mirror only the committed decision and immutable validation evidence;
    # never replace a locally authored response on a failed remote submit.
    decision=check_path(reply["path"],REMOTE_JOB_ROOT)
    revision=reply["revision"]
    local_decisions=local_job/"decisions"
    local_decisions.mkdir(parents=True,exist_ok=True)
    local_decision=local_decisions/("revision_%03d.json"%revision)
    copy(cs,decision,local_decision)
    copy(cs,remote+"/decisions/revision_%03d_dq.json"%revision,
         local_decisions/("revision_%03d_dq.json"%revision))
    copy(cs,remote+"/state.json",local_job/"state.json")
    remote_state=read(local_job/"state.json")
    assert_ok(file_sha(local_decision)==remote_state.get("decision_sha256"),
              "Local decision mirror failed checksum verification")
    save(local_job/"last_submit_result.json",reply)
    return {"status":reply["status"],"job_id":job,
            "remote_path":reply["path"],"revision":revision,
            "local_decision":str(local_decision),
            "local_response_sha256":file_sha(response_path)}

def main():
    p=argparse.ArgumentParser(description="Safe GitHub Codespace bridge for ChatGPT semantic review")
    sub=p.add_subparsers(dest="action",required=True)
    pull_p=sub.add_parser("pull")
    pull_p.add_argument("--codespace",required=True)
    pull_p.add_argument("--remote-job-dir",required=True)
    pull_p.add_argument("--runtime",default=str(RUNTIME))
    push=sub.add_parser("submit")
    push.add_argument("--local-job",required=True)
    push.add_argument("--response",required=True)
    a=p.parse_args()
    try:
        result=pull(a.codespace,a.remote_job_dir,a.runtime) if a.action=="pull" else (
            push_decision(a.local_job,a.response))
        print(json.dumps(result,indent=2,ensure_ascii=False))
        return 0
    except (OSError,ValueError,RuntimeError,KeyError,subprocess.TimeoutExpired) as e:
        print(json.dumps({"status":"FAILED","error":str(e)},ensure_ascii=False),file=sys.stderr)
        return 2

if __name__=="__main__":raise SystemExit(main())
