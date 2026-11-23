"""Real FFmpeg + original reel-recut smoke in private Codespace runtime.

The story is SYNTHETIC TEST DATA. This intentionally stops before human approval;
nothing here proves storytelling quality or clears publishing rights.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

from framework.video_governance.engine import (
    add_asset, add_clip, add_span, audit, connection, run_stage, sha
)
from framework.video_governance.router import discover


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return path


def run(cmd):
    subprocess.run(cmd,check=True)


def story():
    return {
        "story_map": {
            "hook_promise":"Synthetic hook and an explicit promised ending",
            "viewer_prediction":"Synthetic viewer predicts a short solution",
            "want":"Synthetic speaker wants to finish the task",
            "tapi":"Synthetic speaker encounters a documented obstacle",
            "so":"Synthetic speaker reacts to the stated obstacle",
            "payoff":"Synthetic ending explicitly answers the opening"
        },
        "beats":[{"beat_id":x,"role":x} for x in
                 ("HOOK","WANT","TAPI","SO","PAYOFF")]
    }


def native_edit(work,upstream,plan_sha):
    # Run THE original upstream implementation, not a replacement renderer.
    spec=save(work/"recut_spec.json",{
        "source":str(work/"source.mp4"),"output":str(work/"native_recut.mp4"),
        "work_dir":str(work/"native_work"),
        "silence_cut":{"enabled":False},"manual_cuts":[]
    })
    run([sys.executable,str(upstream/".claude/skills/reel-recut/scripts/build_reel.py"),
         str(spec)])
    proof=work/"native_recut.mp4"
    if not proof.is_file() or proof.stat().st_size==0:
        raise RuntimeError("Original reel-recut did not produce MP4")
    save(work/"edit_receipt.json",{
        "plan_sha256":plan_sha,
        "beat_ids":["HOOK","WANT","TAPI","SO","PAYOFF"],
        "executed_skills":[{
            "name":"reel-recut","proof_path":str(proof),"proof_sha256":sha(proof)
        }]
    })


def smoke():
    root=Path(__file__).resolve().parents[2]
    work=root/"framework/.runtime/governance_native_smoke"/uuid.uuid4().hex[:8]
    upstream=Path("/workspaces/_video_edit_upstream/mrpaidsocial-video-editor-agent")
    work.mkdir(parents=True,exist_ok=True)
    source=work/"source.mp4"
    run(["ffmpeg","-hide_banner","-loglevel","error","-y",
         "-f","lavfi","-i","testsrc2=size=720x1280:rate=30",
         "-f","lavfi","-i","sine=frequency=330:sample_rate=48000",
         "-t","2","-c:v","libx264","-preset","ultrafast",
         "-pix_fmt","yuv420p","-c:a","aac",str(source)])
    registry=save(work/"skills.json",discover(upstream))
    con=connection(work/"governance.sqlite")
    project="synthetic_native_smoke"
    try:
        con.execute("INSERT INTO projects VALUES(?,?,?,?)",
                    (project,"2026-11-23T00:00:00Z","v1",8))
        # Unique run folder; previous smoke artifacts remain immutable.
        add_asset(con,project,"editor_skill_pack","REFERENCE",registry,
                  "LICENSE_SCOPE_USER_REPORTED")
        add_asset(con,project,"synthetic_source","SOURCE",source,
                  "UNCLEARED_PRIVATE_ONLY")
        add_clip(con,project,"synth_clip","synthetic_source",0,2000)
        receipt=save(work/"source_receipt.json",{
            "synthetic":True,"source_sha256":sha(source)
        })
        run_stage(con,project,"SOURCE",receipt,[sys.executable,"-c","pass"])
        story_path=save(work/"story.json",story())
        run_stage(con,project,"STORY_LOCK",story_path,[sys.executable,"-c","pass"])
        plan=save(work/"edit_plan.json",{
            "story_sha256":sha(story_path),
            "selected_skills":["video-edit-pipeline","reel-recut"],
            "beat_ids":["HOOK","WANT","TAPI","SO","PAYOFF"]
        })
        run_stage(con,project,"EDIT_PLAN",plan,[sys.executable,"-c","pass"])
        edit_receipt=work/"edit_receipt.json"
        # Exercise the real ChatGPT-oriented skill bridge, not only direct engine calls.
        run([sys.executable,"-m","framework.video_governance.skill_bridge",
             "--registry",str(registry),"run","--db",str(work/"governance.sqlite"),
             project,"EDIT","reel-recut",str(edit_receipt),"--",
             sys.executable,"-m","framework.video_governance.smoke_native",
             "--build-edit",str(work),str(upstream),sha(plan)])
        render=work/"render.mp4"
        run_stage(con,project,"RENDER",render,
                  [sys.executable,"-c","import shutil,sys; shutil.copyfile(sys.argv[1],sys.argv[2])",
                   str(work/"native_recut.mp4"),str(render)])
        from framework.video_governance.engine import render_sha
        digest=render_sha(con,project)
        info=con.execute("SELECT render_id,frame_count FROM renders WHERE project_id=? AND sha256=?",
                         (project,digest)).fetchone()
        frames=info["frame_count"]
        for idx,name in enumerate(("HOOK","WANT","TAPI","SO","PAYOFF")):
            start=frames*idx//5
            end=frames*(idx+1)//5
            add_span(con,project,info["render_id"],"synth_span_"+name,name,
                     "synth_clip","PRIMARY",2000*idx//5,2000*(idx+1)//5,
                     start,end,"synthetic_identity","v1")
        report=audit(con,project)
        # No fabricated human or semantic approvals: expected BLOCKED.
        assert report["status"]=="BLOCKED"
        assert report["stage_statuses"]["RENDER"]=="PASS"
        assert report["stage_statuses"]["DELIVERY"]=="PENDING"
        result={"status":"NATIVE_EDIT_AND_RENDER_PASS__RELEASE_BLOCKED",
                "run_folder":str(work),
                "upstream_sha":discover(upstream)["upstream_commit"],
                "render_sha256":digest,"frame_count":frames,"audit":report}
        save(work/"smoke_result.json",result)
        print(json.dumps(result,indent=2))
    finally:
        con.close()


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--build-edit",nargs=3,metavar=("WORK","UPSTREAM","PLAN_SHA"))
    args=parser.parse_args()
    if args.build_edit:
        native_edit(Path(args.build_edit[0]),Path(args.build_edit[1]),args.build_edit[2])
    else:
        smoke()
