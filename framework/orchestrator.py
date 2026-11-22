#!/usr/bin/env python3
"""ChatGPT-directed Studio task router + resumable project state.
This is NOT an autonomous LLM swarm. Real model reasoning is in chat or
an explicitly connected model runtime; this file enforces workflow order.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKILLS = ROOT/"skills"
TASKS = {
 "IDEATE": ("story-debate",),
 "HOOK": ("story-debate",),
 "WTS": ("story-debate",),
 "SCRIPT": ("story-debate",),
 "ANALYZE": ("story-debate","visual-editor","qa-critic"),
 "CRITIQUE": ("story-debate","visual-editor","qa-critic"),
 "PRODUCE": ("story-debate","visual-editor","asset-discovery","qa-critic"),
 "OPTIMIZE": ("visual-editor","qa-critic"),
 "LEARN": ("story-debate","qa-critic"),
}
PIPELINE=("INTAKE","SOURCE_REVIEW","STORY_CONTRACT","INDEPENDENT_REVIEW","STORY_LOCK",
          "SCENE_PLAN","ASSET_VERIFIED","RENDERED","TECHNICAL_QA","HUMAN_REVIEW","COMPLETE")
REVIEWERS=("creator","audience_skeptic","minimalist_editor","independent_judge")
def route(task):
    task=task.upper()
    if task not in TASKS: raise ValueError("unknown task mode: "+task)
    skills=TASKS[task]
    for skill in skills:
        if not (SKILLS/skill/"SKILL.md").is_file(): raise FileNotFoundError(skill)
    return {
      "mode":task,
      "skills":[str(SKILLS/s/"SKILL.md") for s in skills],
      "priority_rules":["STORY_BEFORE_VISUAL","KEEP_REMOVE_REPLACE_BEFORE_ADD",
                       "NO_FALSE_FACTS","NO_AUTOMATIC_ANIMATION","NO_UNVERIFIED_MEDIA"],
      "reviewers":list(REVIEWERS) if task in {"SCRIPT","PRODUCE","CRITIQUE","ANALYZE"} else ["creator","audience_skeptic"],
      "independent_model_calls":"NOT_CONFIGURED_REQUIRES_EXTERNAL_RUNTIME",
      "execution":"ChatGPT chat orchestrates skill files via Remote Desktop Commander",
    }
def resume(state):
    if not isinstance(state,dict): raise ValueError("state must be object")
    phase=state.get("phase","INTAKE")
    if phase not in PIPELINE: raise ValueError("invalid phase")
    return {"project_id":state.get("project_id"),"phase":phase,"next_phase":PIPELINE[min(PIPELINE.index(phase)+1,len(PIPELINE)-1)],
            "story_lock_approved":state.get("story_lock_approved",False),
            "rights":state.get("rights_status","UNVERIFIED"),
            "human_review":state.get("human_review","PENDING"),
            "last_artifact":state.get("last_artifact"),
            "blockers":state.get("blockers",[])}
def check_transition(state,requested):
    current=state.get("phase","INTAKE")
    if current not in PIPELINE or requested not in PIPELINE: return {"status":"BLOCKED","reason":"INVALID_PHASE"}
    if PIPELINE.index(requested)>PIPELINE.index(current)+1: return {"status":"BLOCKED","reason":"SKIPPED_GATE"}
    if requested == "COMPLETE" and not state.get("story_lock_approved"):
        return {"status":"BLOCKED","reason":"STORY_LOCK_NOT_APPROVED"}
    if requested in {"SCENE_PLAN","ASSET_VERIFIED","RENDERED","TECHNICAL_QA","HUMAN_REVIEW","COMPLETE"} and not (state.get("story_lock_approved") or state.get("private_preview_only")):
        return {"status":"BLOCKED","reason":"STORY_LOCK_NOT_APPROVED"}
    if requested == "COMPLETE" and state.get("human_review")!="APPROVED":
        return {"status":"BLOCKED","reason":"HUMAN_REVIEW_NOT_APPROVED"}
    if state.get("distribution")=="PUBLIC" and state.get("rights_status")!="CLEARED":
        return {"status":"BLOCKED","reason":"PUBLIC_RIGHTS_NOT_CLEARED"}
    return {"status":"ALLOWED","from":current,"to":requested}
def main():
    p=argparse.ArgumentParser()
    sub=p.add_subparsers(dest="cmd",required=True)
    r=sub.add_parser("route");r.add_argument("mode")
    s=sub.add_parser("resume");s.add_argument("state")
    t=sub.add_parser("gate");t.add_argument("state");t.add_argument("next_phase")
    opt=p.parse_args()
    if opt.cmd=="route":result=route(opt.mode)
    else:
        state=json.loads(Path(opt.state).read_text(encoding="utf-8"))
        result=resume(state) if opt.cmd=="resume" else check_transition(state,opt.next_phase)
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
