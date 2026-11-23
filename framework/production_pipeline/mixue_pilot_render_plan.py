#!/usr/bin/env python3
"""Compile exact validated Mixue ChatGPT decision -> private Codespace FFmpeg plan.

No synthetic words, no unapproved asset, no Windows processing. The plan
keeps full source audio because human sample-accurate cut review is pending.
"""
from pathlib import Path
import json
import sys
from .runner import INPUT_ROOT,RUN_ROOT,atomic,read,sha,require
from framework.chatgpt_semantic.handoff import verify_lineage,check_response

ID="7481158062057770258"
ROOT=RUN_ROOT/("semantic_"+ID)
PILOT=ROOT/"pilot_stock_v1"
JOB="sem_a34e26d4fdcf1aa172a7"
FOLDER=PILOT/"runtime"/"jobs"/JOB
PLAN=INPUT_ROOT/"mixue_semantic_v1_private_plan.json"

def main():
    require(sys.platform.startswith("linux") and
            Path("/workspaces/video_editor_mang").is_dir(),"Codespace only")
    verify_lineage(FOLDER)
    state=read(FOLDER/"state.json")
    require(state.get("status")=="VALIDATED_FOR_PRIVATE_PREVIEW",
            "No validated real ChatGPT decision")
    decision_path=Path(state["active_decision"])
    require(sha(decision_path)==state.get("decision_sha256"),
            "Semantic decision edited after validation")
    decision=read(decision_path);req=read(FOLDER/"request.json")
    check_response(decision,req)
    headline="MIXUE JUAL MURAH, UNTUNG DARI MANA?"
    require(any(b["headline"].get("text")==headline for b in decision["beats"]),
            "Hook headline drift from semantic decision")
    source_assets={a["asset_id"]:a for a in req["source"]["assets"]}
    names={"mixkit_yellow_lemon_3709","mixkit_coffee_42944"}
    require(names<=set(source_assets),"Some approved source assets unavailable")
    raw=read(INPUT_ROOT/ID/"source_manifest.json")
    duration=raw["media_probe"]["duration_ms"]/1000
    broll=[]
    for asset_id,start,end,evidence in [
        ("mixkit_yellow_lemon_3709",45.72,49.04,ROOT/"at_47.jpg"),
        ("mixkit_coffee_42944",101.80,104.42,ROOT/"at_104.jpg"),
    ]:
        source=source_assets[asset_id]
        require(source["license_status"]=="VERIFIED" and evidence.is_file(),
                "Unverified candidate/right or source burned-caption evidence")
        target=INPUT_ROOT/("stock/"+asset_id+".mp4")
        require(target.is_file() and sha(target)==source["sha256"],
                "Stock candidate hash drift")
        broll.append({
            "asset_id":asset_id,"path":str(target.relative_to(INPUT_ROOT)),
            "sha256":source["sha256"],
            "license_status":"VERIFIED",
            "semantic_approved":True,
            "visual_approved":True,
            "caption_verified":False,
            "caption_visibility_verified":True,
            "display_mode":"PIP_KEEP_ORIGINAL_CAPTIONS",
            "source_caption_evidence":[str(evidence)],
            "editorial_disclaimer":"Illustrative stock, not Mixue source footage; original baked subtitle remains visible below overlay",
            "timeline_start_sec":start,"duration_sec":round(end-start,3),
        })
    plan={"schema_version":"1.0","batch_id":"mixue_semantic_pilot_v1",
          "render_workers":1,
          "jobs":[{
            "key":"mixue_semantic_v1","video_id":ID,
            "output":{"width":720,"height":1280,"fps":30},
            "mode":"CHATGPT_VALIDATED",
            "semantic_job_dir":str(FOLDER),
            "source_rights":"UNCLEARED_PRIVATE_ONLY",
            "cut_ranges_seconds":[[0,duration]],
            "headline_lines":["MIXUE JUAL MURAH,","UNTUNG DARI MANA?"],
            "headline_card":{"bottom":304},
            "headline_seconds":7.9,
            "motion":"STATIC",
            "broll":broll,
            "human_review":"PENDING",
            "story_fact_check":"CLAIMS_NOT_INDEPENDENTLY_VERIFIED",
            "editorial_note":"No source speech trimmed without human waveform/listening review. Full 42-segment story preserved.",
          }]}
    if PLAN.exists():
        require(read(PLAN)==plan,"Existing Mixue plan differs; manual revision required")
    else:atomic(PLAN,plan)
    print("GATE:Mixue_immutable_chatgpt_decision=PASS",flush=True)
    print("GATE:Mixue_broll_2_selected_shas=PASS",flush=True)
    print("GATE:Mixue_original_captions_preserved_strategy=PASS",flush=True)
    print("GATE:Mixue_human_listening=PENDING",flush=True)
    print(json.dumps({"plan":str(PLAN),"semantic_job":JOB,
                      "expected_duration":duration,
                      "broll_count":len(broll)},indent=2),flush=True)

if __name__=="__main__":
    try:main()
    except (ValueError,OSError,KeyError) as e:
        print("GATE:mixue_plan_compiler=BLOCKED",flush=True)
        print("ERROR:"+repr(e),file=sys.stderr,flush=True)
        raise SystemExit(2)
