#!/usr/bin/env python3
"""Prepare Kauthar V3.1 private export only; verify stock integrity and scene gate."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys

from studio import review
from stage_runtime import signal, save_state

ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parent
PLAN=ROOT/"projects"/"kauthar_v3"/"scene_plan_31.json"
STOCK=ROOT/"projects"/"kauthar_v3"/"selected_asset_sources.json"
OUTPUT=ROOT/".runtime"/"kauthar_v31"/"final_scene_plan_private.json"
PUBLIC=PROJECT/"remotion-app"/"public"

def digest(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda:stream.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()

def main() -> int:
    signal("STAGE","SOURCE_REVIEW")
    manifest=json.loads(STOCK.read_text(encoding="utf-8"))
    plan=json.loads(PLAN.read_text(encoding="utf-8"))
    known={a["file"]:a for a in manifest["assets"]}
    processed=0
    try:
        for item in plan["scenes"]:
            if item["type"]=="a_roll":
                p=PUBLIC/"media"/item["source"]
                if not p.is_file() or p.stat().st_size==0:
                    raise ValueError(f"Missing original A-roll: {p}")
            elif item["type"]=="b_roll":
                asset=item["asset"]
                ref=known.get(asset["file"])
                if not ref or ref.get("license_status")!="VERIFIED" or ref.get("license")!="PEXELS":
                    raise ValueError(f"Missing verified stock record for {asset['file']}")
                if ref["page"]!=asset["page"]:
                    raise ValueError(f"Stock source page mismatch: {asset['file']}")
                p=PUBLIC/asset["file"]
                if not p.is_file() or digest(p).lower()!=ref["sha256"].lower():
                    raise ValueError(f"Stock file/hash mismatch: {p}")
                asset["license_status"]="VERIFIED"
                processed+=1
        audio=PUBLIC/"media"/"ambient.wav"
        if not audio.is_file() or audio.stat().st_size==0:
            raise ValueError("Missing ambient.wav")
        # This stays PRIVATE. We do not mark source creator rights or human review cleared.
        plan["public_release"]=False
        plan["source_rights"]="UNCLEARED"
        plan["human_story_lock"]=False
        plan["render_mode"]="preview"
        result=review(plan)
        signal("GATE","stock_provenance","PASS")
        signal("METRIC","broll_verified",processed)
        if result["status"]!="PASS":
            signal("GATE","scene_plan","FAIL")
            raise ValueError("Scene-plan validation: "+", ".join(result["errors"]))
        signal("GATE","scene_plan","PASS")
        signal("GATE","original_creator_rights","BLOCKED")
        signal("GATE","human_creative_approval","PENDING")
        signal("METRIC","scene_count",result["scenes"])
        save_state(OUTPUT,plan)
        print("Private validated scene plan:",OUTPUT,flush=True)
        print("Original creator rights UNCLEARED; no publication authorization",flush=True)
        return 0
    except (OSError,ValueError,KeyError) as exc:
        signal("GATE","preflight","FAIL")
        print("Preflight ERROR:",exc,file=sys.stderr,flush=True)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
