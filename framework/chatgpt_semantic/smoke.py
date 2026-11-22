#!/usr/bin/env python3
"""Synthetic end-to-end contract smoke, NOT a real semantic review or human QA."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys

from .handoff import prepare, read, save, submit
from .packet_builder import build_source
from .timeline_compiler import compile_job
from .render_guard import render

def create_fixture(root, app):
    root.mkdir(parents=True,exist_ok=True)
    clip=app/"public"/"media"/"semantic_smoke_fixture.mp4"
    clip.parent.mkdir(parents=True,exist_ok=True)
    if not clip.is_file():
        cmd=["ffmpeg","-y","-v","error","-f","lavfi",
             "-i","color=c=0x23445b:s=720x1280:r=30",
             "-f","lavfi","-i","sine=frequency=440:sample_rate=48000",
             "-t","2","-c:v","libx264","-preset","ultrafast",
             "-c:a","aac","-pix_fmt","yuv420p","-shortest",str(clip)]
        run=subprocess.run(cmd,capture_output=True,text=True)
        if run.returncode: raise RuntimeError(run.stderr[-1800:])
    transcript={"transcript_origin":"TEST_FIXTURE",
      "segments":[
       {"segment_id":"fixture_01","clip_id":"fixture_clip",
        "start_ms":0,"end_ms":900,"text":"Synthetic contract check, not actual speech"},
       {"segment_id":"fixture_02","clip_id":"fixture_clip",
        "start_ms":900,"end_ms":2000,"text":"Synthetic conclusion, not actual speech"}]}
    save(root/"transcript.json",transcript)
    spec={"project_id":"smoke_semantic_contract","brief":{"viewer":"Integration test only",
        "goal":"Check schema and render","platform":"Test","language":"en"},
       "video":{"duration_ms":2000,"source_rights":"UNCLEARED"},
       "transcript_path":str(root/"transcript.json"),
       "clips":[{"clip_id":"fixture_clip","path":str(clip),
                 "static_src":"media/semantic_smoke_fixture.mp4","duration_ms":2000,
                 "timeline_start_ms":0,"source_in_ms":0,"base_scale":1.0}]}
    save(root/"spec.json",spec)
    return root/"spec.json"

def pipeline(work,app,run_render):
    spec=create_fixture(work,app)
    bundle=build_source(spec,work/"context")
    runtime=work/"runtime"
    data=prepare(bundle["source"],runtime)
    folder=Path(data["folder"])
    template=read(folder/"response_template.json")
    template["decision_source"]="SYNTHETIC_TEST"
    template["review_ref"]="automated_synthetic_fixture_not_chatgpt"
    template["story_map"]={
        "hook_promise":"Synthetic test needs the end-to-end video export to work",
        "viewer_prediction":"A deterministic short preview should render correctly",
        "want":"Smoke fixture wants a verified two-second test output",
        "tapi":"Pipeline may reject malformed media or stale source lineage",
        "so":"A fully checked synthetic fixture can reach the render stage",
        "payoff":"720p H264 AAC output is verified with full frame decode",
        "causal_reason":"Passing contract gates allows exactly one private test render",
        "factual_limitations":"This is a synthetic tone video, not spoken human footage"}
    template["beats"]=[
     {"beat_id":"fixture_hook","start_segment_id":"fixture_01","end_segment_id":"fixture_01",
      "evidence_segment_ids":["fixture_01"],"story_role":"HOOK",
      "meaning":"Synthetic test checks that short source segments compile to timed beats",
      "headline":{"text":None,"style_hint":"NONE","reason":"Fixture bypasses creative overlay"},
      "broll":{"asset_id":None,"reason":"Test clip includes a clear synthetic background"},
      "motion":{"mode":"SUBTLE","reason":"Only tests smooth keyframe interpolation"},
      "cut_guidance":"KEEP"},
     {"beat_id":"fixture_payoff","start_segment_id":"fixture_02","end_segment_id":"fixture_02",
      "evidence_segment_ids":["fixture_02"],"story_role":"PAYOFF",
      "meaning":"Synthetic conclusion validates end-of-timeline composition boundaries",
      "headline":{"text":None,"style_hint":"NONE","reason":"No title for synthetic fixture"},
      "broll":{"asset_id":None,"reason":"No substitute footage in fixture"},
      "motion":{"mode":"STATIC","reason":"Static fixture ending"},
      "cut_guidance":"KEEP"}
    ]
    response=work/"response.json"
    save(response,template)
    verdict=submit(folder.name,response,runtime)
    compiled=compile_job(folder)
    result={"status":"SYNTHETIC_CONTRACT_PASS","packet":bundle,
            "semantic_validation":verdict["status"],"compiler":compiled,
            "not_an_actual_chatgpt_review":True}
    if run_render:
        output=work/"synthetic_720_only.mp4"
        if output.exists():
            output.unlink()
        if output.with_suffix(".qa.json").exists():
            output.with_suffix(".qa.json").unlink()
        qa=render(compiled["path"],app,output)
        result["render_qa"]=qa
    save(work/"result.json",result)
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--work",required=True)
    p.add_argument("--app",required=True)
    p.add_argument("--run-render",action="store_true")
    a=p.parse_args()
    try:
        result=pipeline(Path(a.work).resolve(),Path(a.app).resolve(),a.run_render)
        print(json.dumps(result,indent=2,ensure_ascii=False))
        return 0
    except (OSError,ValueError,RuntimeError,KeyError,TypeError) as e:
        print("GATE:synthetic_pipeline=FAIL",flush=True)
        print(json.dumps({"status":"FAILED","error":str(e)}),file=sys.stderr)
        return 2

if __name__=="__main__":raise SystemExit(main())
