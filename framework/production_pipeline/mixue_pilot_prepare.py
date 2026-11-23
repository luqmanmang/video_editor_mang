#!/usr/bin/env python3
"""Prepare a real 42-segment Mixue ChatGPT review with visually screened stock.

Never overwrites the old PENDING_CHATGPT job. All media and evidence stay inside
private Codespace runtime. This code records actual editorial choices from the
human/ChatGPT-in-the-loop review, but does not call any model API.
"""
from pathlib import Path
import json
import subprocess
import sys
from .runner import INPUT_ROOT, RUN_ROOT, sha, atomic, require
from .prepare_semantic import build
from framework.chatgpt_semantic.packet_builder import build_source
from framework.chatgpt_semantic.handoff import prepare

ID="7481158062057770258"
PILOT=RUN_ROOT/("semantic_"+ID)/"pilot_stock_v1"
APPROVED={"mixkit_yellow_lemon_3709","mixkit_coffee_42944"}
REJECTED={
    "mixkit_lemon_42948":"Visual shows predominantly green citrus slices; the narration says lemon. Strong semantic color ambiguity.",
    "mixkit_mixing_43020":"Visual depicts dessert ingredients mixed in a kitchen, not an industrial factory; misleading during the five-mega-factories claim.",
}
def main():
    require(sys.platform.startswith("linux") and
            Path("/workspaces/video_editor_mang").is_dir(),"Codespace-only evidence")
    base=RUN_ROOT/("semantic_"+ID)
    if not (base/"spec.json").is_file():
        build(ID)
    root=INPUT_ROOT/"stock"
    data=json.loads((root/"candidate_discovery.json").read_text())
    candidate_by_id={x["asset_id"]:x for x in data["candidates"]}
    require(APPROVED|set(REJECTED)<=set(candidate_by_id),"Not all reviewed stock assets exist")
    PILOT.mkdir(parents=True,exist_ok=True)
    decisions=[]
    selected=[]
    for key in sorted(APPROVED|set(REJECTED)):
        item=candidate_by_id[key]
        video=Path(item["path"])
        require(video.is_file() and sha(video)==item["sha256"],
                "Stock asset changed after actual visual review "+key)
        require(item["license_status"]=="VERIFIED" and
                item["license_name"]=="Mixkit Stock Video Free License",
                "Unapproved stock license "+key)
        if key in APPROVED:
            reason=(
                "Three actual frames show yellow lemon slices. This illustrates the ingredient "
                "mentioned at s0013-s0014, not evidence of Mixue procurement."
                if key=="mixkit_yellow_lemon_3709" else
                "Three actual frames show coffee beans. This illustrates one of the raw materials "
                "listed at s0035; not an actual franchise supplier or sale."
            )
            selected.append({"role":key,"file":item["file"],"sha256":item["sha256"],
                             "license_status":"VERIFIED","page":item["source_url"],
                             "description":reason})
            status="APPROVED_FOR_PRIVATE_ILLUSTRATIVE_PREVIEW"
        else:
            reason=REJECTED[key]
            status="REJECTED_SEMANTIC_VISUAL"
        decisions.append({"asset_id":key,"status":status,"reason":reason,
                          "visual_evidence":[{"path":f["path"],"sha256":f["sha256"]}
                                            for f in item["frames"]],
                          "source_url":item["source_url"],"license_name":item["license_name"],
                          "stock_sha256":item["sha256"]})
    stock=PILOT/"approved_stock_manifest.json"
    audit=PILOT/"candidate_decisions.json"
    atomic(stock,{"schema_version":"1.0","assets":selected,
                  "status":"ILLUSTRATIVE_ONLY; ORIGINAL_CREATOR_RIGHTS_UNCLEARED"})
    atomic(audit,{"source_video_id":ID,"semantic_director":"CHATGPT_IN_THIS_CONVERSATION",
                  "candidates":decisions,"selected_count":len(selected),
                  "rejected_count":len(REJECTED)})
    spec=json.loads((base/"spec.json").read_text())
    spec["stock_manifest"]=str(stock)
    spec["static_root"]=str(INPUT_ROOT)
    spec["extra_evidence_paths"].extend([str(audit),str(root/"candidate_discovery.json")])
    # Import actual source-frame evidence for baked headline and caption geometry.
    for t in (1,4,8,47,104):
        frame=base/("at_"+str(t)+".jpg") if t in (47,104) else base/("open_"+str(t)+".jpg")
        require(frame.is_file(),"Actual source frame missing "+str(frame))
        spec["frames"].append({"path":str(frame),"at_ms":t*1000})
    spec["story"]={
       "status":"CHATGPT_MANUAL_EDITORIAL_REVIEW_REQUIRED",
       "focus":"Low price mystery -> supply-chain savings -> low franchise costs -> raw ingredient revenue -> geographic scaling",
       "fact_check":"Speaker claims (branch counts, lemon discounts, factories, profits) remain UNVERIFIED",
       "headline_existing_baked":"Cara mixue kekal untung walaupun jual murah?",
       "subtitle_existing_baked":True,
       "stock_inspection":"Two assets approved as illustrative, not depiction of Mixue facilities",
    }
    outspec=PILOT/"spec.json"; atomic(outspec,spec)
    packet=build_source(outspec,PILOT/"context")
    prepared=prepare(packet["source"],PILOT/"runtime")
    print("GATE:mixue_real_asr_42=PASS",flush=True)
    print("GATE:mixue_stock_2_visual_semantic=PASS",flush=True)
    print("GATE:mixue_licensed_stock_shas=PASS",flush=True)
    print("GATE:mixue_full_story_approval=PENDING_CHATGPT",flush=True)
    print(json.dumps({"pilot_dir":str(PILOT),"semantic_job":prepared["job_id"],
                      "job_folder":prepared["folder"],"source_packet":packet["source"],
                      "stock_assets":[x["role"] for x in selected]},indent=2),flush=True)

if __name__=="__main__":
    try:main()
    except (ValueError,OSError,KeyError,subprocess.TimeoutExpired) as e:
        print("GATE:mixue_pilot_prepare=FAIL",flush=True)
        print("ERROR:"+repr(e),file=sys.stderr,flush=True)
        raise SystemExit(2)
