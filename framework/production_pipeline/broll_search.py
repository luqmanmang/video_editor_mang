#!/usr/bin/env python3
"""Stock discovery ONLY. ChatGPT must view/approve candidate and license before use.

Searches provider APIs using user-supplied env secrets. Never sends transcript
outside Codespace: only a short human/ChatGPT-approved search query is sent.
Never auto-downloads, marks licenses verified, or inserts into a timeline.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]/".runtime"
def fail(ok,msg):
    if not ok:raise ValueError(msg)
def fetch(url,headers):
    req=Request(url,headers=headers)
    with urlopen(req,timeout=18) as stream:
        raw=stream.read(3_000_000+1)
        fail(len(raw)<=3_000_000,"Oversized API response")
        return json.loads(raw)
def search(provider,query,limit=6):
    fail(provider in ("pexels","pixabay"),"Unknown stock provider")
    fail(isinstance(query,str) and 3<=len(query)<=180,
         "Query must describe a specific video scene in 3-180 characters")
    fail(type(limit)==int and 1<=limit<=10,"Maximum 10 discovery candidates")
    if provider=="pexels":
        key=os.environ.get("PEXELS_API_KEY")
        fail(key,"PEXELS_API_KEY unavailable; connect/configure user-provided key")
        url="https://api.pexels.com/videos/search?"+urlencode({"query":query,"per_page":limit})
        data=fetch(url,{"Authorization":key,"User-Agent":"KautharPrivateVideoStudio/1.0"})
        hits=[]
        for v in data.get("videos",[]):
            samples=v.get("video_files",[])
            file=next((x for x in samples if x.get("file_type")=="video/mp4"
                       and x.get("height",0)>=720),None)
            hits.append({"candidate_id":"pexels_"+str(v["id"]),"provider":"pexels",
                "description":query,"source_url":v.get("url"),
                "preview_image":v.get("image"),"duration_sec":v.get("duration"),
                "width":v.get("width"),"height":v.get("height"),
                "download_url":file.get("link") if file else None})
    else:
        key=os.environ.get("PIXABAY_API_KEY")
        fail(key,"PIXABAY_API_KEY unavailable; connect/configure user-provided key")
        url="https://pixabay.com/api/videos/?"+urlencode({
            "key":key,"q":query,"per_page":limit,"safesearch":"true"})
        data=fetch(url,{"User-Agent":"KautharPrivateVideoStudio/1.0"})
        hits=[]
        for v in data.get("hits",[]):
            files=v.get("videos",{})
            clip=files.get("medium") or files.get("large") or {}
            hits.append({"candidate_id":"pixabay_"+str(v["id"]),"provider":"pixabay",
                "description":v.get("tags",query),"source_url":v.get("pageURL"),
                "preview_image":None,"duration_sec":v.get("duration"),
                "width":clip.get("width"),"height":clip.get("height"),
                "download_url":clip.get("url")})
    return {"schema_version":"1.0","provider":provider,"query":query,
        "retrieved_at":datetime.now(timezone.utc).isoformat(),
        "candidates":[{**h,"license_status":"PENDING_LICENSE_EVIDENCE",
            "semantic_status":"PENDING_CHATGPT_REVIEW",
            "visual_status":"PENDING_ACTUAL_FRAME_REVIEW",
            "selected":False} for h in hits],
        "may_render":False,"automatic_download":False}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--provider",choices=["pexels","pixabay"],required=True)
    p.add_argument("--query",required=True)
    p.add_argument("--limit",type=int,default=6)
    p.add_argument("--out",required=True)
    o=p.parse_args()
    try:
        fail(sys.platform.startswith("linux") and Path("/workspaces/video_editor_mang").is_dir(),
             "Stock discovery must run on Codespace, not Windows")
        file=Path(o.out).resolve()
        fail(file.is_relative_to(ROOT.resolve()) and file.suffix==".json",
             "Stock candidate file must be under private Codespace .runtime")
        result=search(o.provider,o.query,o.limit)
        fail(not file.exists(),"Refuse overwrite of candidate discovery evidence")
        file.parent.mkdir(parents=True,exist_ok=True)
        file.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
        print(json.dumps({"status":"CANDIDATES_ONLY","count":len(result["candidates"]),
                          "path":str(file)}))
        return 0
    except (ValueError,OSError,KeyError) as e:
        print(json.dumps({"status":"BLOCKED","error":str(e)}),file=sys.stderr)
        return 2
if __name__=="__main__":raise SystemExit(main())
