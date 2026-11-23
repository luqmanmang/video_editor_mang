"""ChatGPT remote skill interface for the *original* 21 upstream skills.

Uses pinned source SKILL.md files; does not reimplement the editing skills.
Execution always routes to governance stages (no bypass for native commands).
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from framework.video_governance.engine import (
    STAGES, GateError, connection, event, require, run_stage, sha, stage_row
)

SERVICE_KEYS = {
    "sound-design": "ELEVENLABS_API_KEY",
    "arcads-broll": "ARCADS_API_KEY",
    "arcads-video-edit": "ARCADS_API_KEY",
}
BLOCKED = {"PLATFORM_BLOCKED_IN_CODESPACE","EXPERIMENTAL"}


def load_manifest(path):
    obj=json.loads(Path(path).read_text(encoding="utf-8"))
    require(obj.get("skill_count")==21,"SKILL_REGISTRY_COUNT_NOT_21")
    require(len(obj.get("skills",[]))==21,"SKILL_MANIFEST_LIST_NOT_21")
    root=Path(obj["upstream_path"])
    head=subprocess.run(["git","-C",str(root),"rev-parse","HEAD"],
                        capture_output=True,text=True,check=True).stdout.strip()
    require(head==obj["upstream_commit"],"UPSTREAM_GIT_COMMIT_DRIFT")
    dirty=subprocess.run(["git","-C",str(root),"status","--porcelain",
                          "--untracked-files=no"],text=True,capture_output=True,check=True)
    require(not dirty.stdout.strip(),"UPSTREAM_TRACKED_FILES_DIRTY")
    return obj


def get_skill(manifest,name):
    item=next((s for s in manifest["skills"] if s["name"]==name),None)
    require(item is not None,"UNKNOWN_NATIVE_SKILL:"+name)
    path=Path(item["instruction_path"])
    require(path.is_file() and sha(path)==item["instruction_sha256"],
            "NATIVE_SKILL_INSTRUCTIONS_CHANGED:"+name)
    return item


def check_runtime(item):
    require(item["status"] not in BLOCKED,
            "UPSTREAM_SKILL_PLATFORM_OR_EXPERIMENTAL_BLOCK:"+item["name"])
    key=SERVICE_KEYS.get(item["name"])
    if key:
        require(bool(os.environ.get(key)),"NATIVE_SKILL_KEY_NOT_CONFIGURED:"+key)


def check_selected(con,project,name,stage):
    if stage not in ("EDIT","RENDER","TECH_QA","STORY_QA"):
        return
    row=stage_row(con,project,"EDIT_PLAN")
    require(row and row["status"]=="PASS","EDIT_PLAN_REQUIRED_FOR_NATIVE_SKILL")
    plan=json.loads(Path(row["artifact_path"]).read_text(encoding="utf-8"))
    require(name in plan.get("selected_skills",[]),
            "NATIVE_SKILL_NOT_APPROVED_IN_PLAN:"+name)


def main(argv=None):
    ap=argparse.ArgumentParser()
    ap.add_argument("--registry",required=True)
    sub=ap.add_subparsers(dest="action",required=True)
    p=sub.add_parser("list")
    p=sub.add_parser("show");p.add_argument("name")
    p=sub.add_parser("run")
    p.add_argument("--db",required=True);p.add_argument("project")
    p.add_argument("stage");p.add_argument("name");p.add_argument("artifact")
    p.add_argument("command",nargs=argparse.REMAINDER)
    args=ap.parse_args(argv)
    try:
        manifest=load_manifest(args.registry)
        if args.action=="list":
            print(json.dumps([{"name":s["name"],"owner":s["owner"],
                "status":s["status"],"lane":s["lane"]} for s in manifest["skills"]],indent=2))
        elif args.action=="show":
            item=get_skill(manifest,args.name)
            print("UPSTREAM_COMMIT:",manifest["upstream_commit"])
            print("SKILL_PATH:",item["instruction_path"])
            print("SKILL_STATUS:",item["status"])
            print(Path(item["instruction_path"]).read_text(encoding="utf-8"))
        elif args.action=="run":
            item=get_skill(manifest,args.name)
            check_runtime(item)
            require(args.stage in STAGES,"INVALID_STAGE")
            con=connection(args.db)
            try:
                check_selected(con,args.project,args.name,args.stage)
                cmd=args.command[1:] if args.command and args.command[0]=="--" else args.command
                require(bool(cmd),"NATIVE_COMMAND_MISSING")
                result=run_stage(con,args.project,args.stage,args.artifact,cmd)
                event(con,args.project,"NATIVE_SKILL_EXECUTED",
                      skill=item["name"],skill_sha256=item["instruction_sha256"],
                      upstream_commit=manifest["upstream_commit"],
                      stage=args.stage,artifact=result["sha256"])
                print(json.dumps(result,indent=2))
            finally:
                con.close()
        return 0
    except (GateError,OSError,ValueError,subprocess.CalledProcessError) as exc:
        print("SKILL_BRIDGE_FAIL:"+str(exc),file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
