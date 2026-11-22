"""Resumable, checksum-verified stage execution for Video Studio.

Only use on an authorized local/Codespace shell. This module never uploads files.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

def signal(kind, name, value=None):
    if kind == "STAGE":
        print(f"STAGE:{name}", flush=True)
    elif kind == "PROGRESS":
        print(f"PROGRESS:{name}", flush=True)
    else:
        print(f"{kind}:{name}={value}", flush=True)

def stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

def read_state(file):
    try:
        data=json.loads(file.read_text(encoding="utf-8"))
        return data if isinstance(data,dict) else {"schema":1,"stages":{}}
    except (OSError,ValueError):
        return {"schema":1,"stages":{}}

def save_state(file, data):
    file.parent.mkdir(parents=True,exist_ok=True)
    temp=file.with_name(file.name+"."+uuid.uuid4().hex+".tmp")
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    os.replace(temp,file)

def sha256(file):
    h=hashlib.sha256()
    with file.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()

def signature(stage, command, inputs, outputs):
    data={"stage":stage,"command":command,"outputs":[str(p.resolve()) for p in outputs],"inputs":{}}
    for f in inputs:
        if not f.is_file():
            raise FileNotFoundError("Input missing: "+str(f))
        data["inputs"][str(f.resolve())]=sha256(f)
    raw=json.dumps(data,sort_keys=True,ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

def outputs_verified(outputs, stored=None):
    if not outputs:
        return False
    for p in outputs:
        if not p.is_file() or p.stat().st_size==0:
            return False
        if stored is not None and stored.get(str(p.resolve()))!=sha256(p):
            return False
    return True

def step(state_path, stage, command, input_paths, output_paths):
    stage=stage.upper()
    if not stage.replace("_","").isalnum():
        raise ValueError("Invalid stage name")
    if not command:
        raise ValueError("Missing command after --")
    inputs=[Path(x).resolve() for x in input_paths]
    outputs=[Path(x).resolve() for x in output_paths]
    signal("STAGE",stage)
    try:
        sig=signature(stage,command,inputs,outputs)
    except (OSError,ValueError) as exc:
        signal("GATE","source_integrity","FAIL")
        print(f"Stage preflight failed: {exc}",file=sys.stderr,flush=True)
        return 2
    signal("GATE","source_integrity","PASS")
    state=read_state(state_path)
    state.setdefault("schema",1)
    stages=state.setdefault("stages",{})
    prev=stages.get(stage,{})
    if prev.get("status")=="PASS" and prev.get("signature")==sig and outputs_verified(outputs,prev.get("output_hashes",{})):
        signal("METRIC","stage_skipped",1)
        signal("METRIC","outputs_verified",len(outputs))
        signal("GATE","artifact_integrity","PASS")
        signal("GATE","stage","PASS")
        print("CACHE_HIT: same inputs, command and verified outputs; render skipped",flush=True)
        return 0

    # Failed/interrupted stages are rerun; never mark PASS until outputs verify.
    state["updated_at"]=stamp()
    stages[stage]={"status":"RUNNING","signature":sig,"started_at":stamp(),
                   "inputs":[str(i) for i in inputs],"outputs":[str(o) for o in outputs],
                   "command":command}
    save_state(state_path,state)
    started=time.monotonic()
    exit_code=1
    try:
        with subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                              text=True,encoding="utf-8",errors="replace",bufsize=1) as proc:
            for line in proc.stdout:
                print(line.rstrip("\r\n"),flush=True)
            exit_code=proc.wait()
    except OSError as exc:
        print(f"Stage command failure: {exc}",file=sys.stderr,flush=True)
    duration=round(time.monotonic()-started,3)
    good=(exit_code==0 and outputs_verified(outputs))
    output_hashes={str(o):sha256(o) for o in outputs} if good else {}
    stages[stage].update({"status":"PASS" if good else "FAILED","finished_at":stamp(),
                          "exit_code":exit_code,"duration_sec":duration,"output_hashes":output_hashes})
    state["updated_at"]=stamp()
    save_state(state_path,state)
    signal("METRIC","stage_duration_sec",duration)
    signal("METRIC","outputs_verified",len(outputs) if good else 0)
    signal("GATE","artifact_integrity","PASS" if good else "FAIL")
    signal("GATE","stage","PASS" if good else "FAIL")
    if not good:
        print(f"Stage {stage} FAILED: exit={exit_code}, outputs verified={outputs_verified(outputs)}",file=sys.stderr,flush=True)
    return 0 if good else (exit_code or 2)
