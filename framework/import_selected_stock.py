#!/usr/bin/env python3
"""Verify selected Pexels clips from private asset_licenses.json.
Build private validated scene_plan; never version private assets/metadata.
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parent.parent
PUBLIC=ROOT/"remotion-app"/"public"/"stock"
LEDGER=PUBLIC/"asset_licenses.json"
CACHE=ROOT/"framework"/".cache"

def main():
    data=json.loads((ROOT/"framework"/"projects"/"kauthar_v3"/"selected_asset_sources.json").read_text(encoding="utf-8"))
    assets=data.get("assets", [])
    if len(assets)!=2: raise ValueError("Exactly two selected clips required for pilot")
    by_role={}
    for a in assets:
        if a.get("role") not in {"experience","giving"}: raise ValueError("unknown B-roll role")
        if a.get("license")!="PEXELS" or a.get("license_status")!="VERIFIED":
            raise ValueError("unverified Pexels license")
        if not a.get("page","").startswith("https://www.pexels.com/video/"):
            raise ValueError("missing exact Pexels source page")
        path=ROOT/"remotion-app"/"public"/a["file"]
        if not path.is_file(): raise ValueError("asset missing: "+str(path))
        actual=hashlib.sha256(path.read_bytes()).hexdigest()
        if actual!=a["sha256"]: raise ValueError("checksum mismatch: "+str(path))
        if shutil.which("ffprobe"):
            cmd=["ffprobe","-v","error","-select_streams","v:0",
                 "-show_entries","stream=width,height,codec_name","-of","json",str(path)]
            probe=subprocess.run(cmd,capture_output=True,text=True,check=True)
            streams=json.loads(probe.stdout).get("streams",[])
            if not streams or streams[0].get("width",0)<640: raise ValueError("invalid visual stream")
            a["probe"]=streams[0]
        by_role[a["role"]]=a
    plan=json.loads((ROOT/"framework"/"projects"/"kauthar_v3"/"scene_plan.json").read_text(encoding="utf-8"))
    for s in plan["scenes"]:
        if s["type"]=="b_roll":
            role="experience" if "experience" in s["asset"]["file"] else "giving"
            s["asset"]=by_role[role]
    LEDGER.parent.mkdir(parents=True,exist_ok=True)
    LEDGER.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    CACHE.mkdir(parents=True,exist_ok=True)
    dest=CACHE/"kauthar_v3_verified.json"
    dest.write_text(json.dumps(plan,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"status":"VERIFIED","asset_count":len(assets),"plan":str(dest),
        "original_creator_rights":"UNCLEARED_PRIVATE_ONLY","assets":[{"role":a["role"],"sha256":a["sha256"],"source":a["page"],"probe":a.get("probe")} for a in assets]},indent=2))
if __name__=="__main__": main()
