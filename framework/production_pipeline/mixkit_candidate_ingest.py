#!/usr/bin/env python3
"""Codespace-only: fetch specific, license-screened Mixkit candidates for private visual review.

No arbitrary stock scraping, bulk database, or autonomous video selection.
Every candidate URL is a manually curated specific source page. Actual frame
inspection and semantic approval are mandatory after download.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

from .runner import INPUT_ROOT,require,atomic,sha,probe

CANDIDATES=[
 {"asset_id":"mixkit_lemon_42948","id":"42948",
  "page":"https://mixkit.co/free-stock-video/lemons-rotating-in-a-cluster-at-a-leisurely-pace-42948/",
  "hypothesis":"Illustration of lemon ingredient; NOT proof of Mixue procurement"},
 {"asset_id":"mixkit_coffee_42944","id":"42944",
  "page":"https://mixkit.co/free-stock-video/coffee-beans-texture-42944/",
  "hypothesis":"Illustration of coffee raw material sold to franchisees; NOT an actual Mixue ingredient shipment"},
 {"asset_id":"mixkit_mixing_43020","id":"43020",
  "page":"https://mixkit.co/free-stock-video/cook-mixing-ingredients-in-a-mixture-43020/",
  "hypothesis":"Candidate for generic ingredient processing; likely unsuitable as depiction of Mixue factories"},
]
ROOT=INPUT_ROOT/"stock"
HEADERS={"User-Agent":"Mozilla/5.0 (compatible; PrivateEditorialReview/1.0)"}

def get_page(url):
    require(url.startswith("https://mixkit.co/free-stock-video/"),"Untrusted provider URL")
    with urlopen(Request(url,headers=HEADERS),timeout=25) as r:
        page=r.read(5_000_000).decode("utf-8","replace")
    require("Mixkit Stock Video Free License" in page,
            "No explicit Free License evidence on specific item page")
    require("Free Download" in page,
            "Item page has no matching Free Download")
    return page

def save_candidate(entry,overwrite=False):
    ROOT.mkdir(parents=True,exist_ok=True)
    page=get_page(entry["page"])
    i=entry["id"]
    regex=r'https://assets\.mixkit\.co/videos/'+re.escape(i)+r'/'+re.escape(i)+r'-720\.mp4'
    matches=re.findall(regex,page)
    require(matches,"Canonical 720p media URL unavailable for asset "+i)
    url=matches[0]
    target=ROOT/(entry["asset_id"]+".mp4")
    if not target.exists():
        temp=ROOT/(entry["asset_id"]+".partial")
        try:
            with urlopen(Request(url,headers=HEADERS),timeout=60) as r, temp.open("wb") as f:
                require(r.headers.get("Content-Type","").lower().startswith("video/"),
                        "Provider returned non-video content")
                size=0
                while True:
                    block=r.read(1024*1024)
                    if not block:break
                    size+=len(block)
                    require(size<=40_000_000,"Unexpectedly large B-roll response")
                    f.write(block)
            require(temp.stat().st_size>200_000,"Stock asset empty/too small")
            temp.rename(target)
        finally: temp.unlink(missing_ok=True)
    media=probe(target)
    vs=next((s for s in media["streams"] if s["codec_type"]=="video"),None)
    require(vs and vs["width"]>=480 and vs["height"]>=480 and
            float(media["format"]["duration"])>=3.0,
            "Downloaded candidate failed minimum video quality/duration")
    frames=[]
    frame_dir=ROOT/(entry["asset_id"]+"_frames")
    frame_dir.mkdir(exist_ok=True)
    total=float(media["format"]["duration"])
    for j,sec in enumerate((min(1,total/6),total*.4,total*.75),1):
        dst=frame_dir/f"frame_{j:02d}.jpg"
        if not dst.exists():
            cmd=["ffmpeg","-hide_banner","-v","error","-ss",str(sec),
                 "-i",str(target),"-frames:v","1","-vf","scale=270:480:force_original_aspect_ratio=decrease",
                 str(dst)]
            res=subprocess.run(cmd,capture_output=True,text=True,timeout=50)
            require(res.returncode==0 and dst.is_file(),"Stock frame extraction failed")
        frames.append({"path":str(dst),"time_sec":round(sec,2),"sha256":sha(dst)})
    return {"asset_id":entry["asset_id"],"file":str(target.relative_to(INPUT_ROOT)),
            "path":str(target),"sha256":sha(target),
            "source_url":entry["page"],"download_url":url,"provider":"Mixkit",
            "license_status":"VERIFIED","license_name":"Mixkit Stock Video Free License",
            "license_evidence":"Official individual page explicitly states Free License for commercial or personal use",
            "license_checked_at":datetime.now(timezone.utc).isoformat(),
            "semantic_status":"PENDING_CHATGPT_REVIEW",
            "visual_status":"PENDING_ACTUAL_FRAMES",
            "hypothesis":entry["hypothesis"],
            "duration_sec":round(total,2),"width":vs["width"],"height":vs["height"],
            "frames":frames}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--only",choices=[e["asset_id"] for e in CANDIDATES],default=None)
    a=ap.parse_args()
    try:
        require(sys.platform.startswith("linux") and
                Path("/workspaces/video_editor_mang").is_dir(),"Codespace only")
        chosen=[e for e in CANDIDATES if not a.only or e["asset_id"]==a.only]
        results=[]
        for entry in chosen:
            r=save_candidate(entry)
            results.append(r)
            print("GATE:"+entry["asset_id"]+"_download_license=PASS",flush=True)
        path=ROOT/"candidate_discovery.json"
        if path.exists():
            prior=json.loads(path.read_text())
            byid={x["asset_id"]:x for x in prior["candidates"]}
            byid.update({x["asset_id"]:x for x in results})
            results=list(byid.values())
        atomic(path,{"schema_version":"1.0","status":"CANDIDATES_UNREVIEWED",
                     "candidates":results})
        print(json.dumps({"status":"PENDING_VISUAL_REVIEW","candidate_count":len(results),
                          "manifest":str(path),
                          "asset_ids":[x["asset_id"] for x in results]},indent=2),flush=True)
        return 0
    except (OSError,ValueError,KeyError,subprocess.TimeoutExpired,URLError) as err:
        print("GATE:mixkit_candidate_ingest=BLOCKED",flush=True)
        print("ERROR:"+repr(err),file=sys.stderr,flush=True)
        return 2
if __name__=="__main__":raise SystemExit(main())
