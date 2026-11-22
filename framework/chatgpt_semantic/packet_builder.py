#!/usr/bin/env python3
"""Prepare verifiable context packets for manual ChatGPT reading. No ASR/LLM.

Input spec references actual transcript JSON, approved project metadata, media,
stock manifest and optionally sampled frame files. Outputs are PRIVATE.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from .handoff import check_source, file_sha, read, save

def must(test, msg):
    if not test:
        raise ValueError(msg)

def resolve_path(raw, base):
    p=Path(raw)
    return (p if p.is_absolute() else base/p).resolve()

def safe_rel_static(value):
    must(isinstance(value,str) and bool(value) and
         not value.startswith(("/", "\\")) and
         not re.match(r"^[A-Za-z]:",value) and
         ".." not in Path(value).parts and "\\" not in value,
         "Unsafe staticFile reference")
    return value

def build_source(spec_file, out_dir, *, chunk_chars=4200):
    spec_file=Path(spec_file).resolve()
    s=read(spec_file)
    base=spec_file.parent
    must(isinstance(s,dict) and s.get("project_id"),"Missing project_id")
    must(chunk_chars>=500,"chunk_chars too low")
    must("transcript_path" in s,"No real transcript supplied: BLOCKED_TRANSCRIPT")
    transcript_path=resolve_path(s["transcript_path"],base)
    must(transcript_path.is_file(),"Transcript missing: BLOCKED_TRANSCRIPT")
    transcript=read(transcript_path)
    segments=transcript.get("segments") if isinstance(transcript,dict) else transcript
    must(isinstance(segments,list) and segments,"Transcript must contain segments, not scene summaries")
    must(all(isinstance(v,dict) and v.get("text") for v in segments),
         "Actual transcription text required for every segment")
    must(transcript.get("transcript_origin") in
         ("HUMAN_VERIFIED","ASR_UNVERIFIED","TEST_FIXTURE") if isinstance(transcript,dict) else False,
         "transcript_origin must be HUMAN_VERIFIED, ASR_UNVERIFIED or TEST_FIXTURE")
    if transcript.get("transcript_origin")=="TEST_FIXTURE":
        must(str(s["project_id"]).startswith("smoke_"),
             "TEST_FIXTURE restricted to smoke_ projects")
    transcript_origin=transcript["transcript_origin"]

    refs=[{"path":str(spec_file),"kind":"project_spec"},
          {"path":str(transcript_path),"kind":"transcript"}]
    frames=[{"path":str(resolve_path(f["path"],base)),"at_ms":int(f["at_ms"])}
            for f in s.get("frames",[])]
    media=[]
    clips=[]
    for index,c in enumerate(s.get("clips",[])):
        p=resolve_path(c["path"],base)
        must(p.is_file() and p.stat().st_size>0,"Clip source missing: "+str(p))
        static=safe_rel_static(c["static_src"])
        clip={"clip_id":c["clip_id"],"path":str(p),"src":static,
              "timeline_start_ms":int(c["timeline_start_ms"]),
              "source_in_ms":int(c.get("source_in_ms",0)),
              "duration_ms":int(c["duration_ms"]),
              "base_scale":float(c.get("base_scale",1.0)),
              "captions_burned":bool(c.get("captions_burned",False)),
              "source_sha256":file_sha(p)}
        must(clip["duration_ms"]>0 and clip["source_in_ms"]>=0 and
             1<=clip["base_scale"]<=1.5,"Invalid clip duration/base scale")
        clips.append(clip)
        media.append({"path":str(p),"kind":"a_roll","clip_id":clip["clip_id"]})
    assets=[]
    if s.get("stock_manifest"):
        stock_path=resolve_path(s["stock_manifest"],base)
        refs.append({"path":str(stock_path),"kind":"stock_manifest"})
        stock=read(stock_path)
        media_root=resolve_path(s["static_root"],base) if s.get("static_root") else None
        must(media_root is not None,"static_root required when using stock_manifest")
        for item in stock.get("assets",[]):
            rel=safe_rel_static(item["file"])
            p=(media_root/rel).resolve()
            must(p.is_relative_to(media_root),"Asset path escapes static root")
            must(p.is_file() and p.stat().st_size>0,"Missing B-roll: "+str(p))
            expected=item.get("sha256")
            must(isinstance(expected,str) and file_sha(p).lower()==expected.lower(),
                 "B-roll checksum mismatch: "+rel)
            assets.append({"asset_id":item["role"],"src":rel,"path":str(p),
                           "license_status":item["license_status"],
                           "source_url":item["page"],"sha256":expected,
                           "description":item.get("description","")})
            media.append({"path":str(p),"kind":"b_roll","asset_id":item["role"]})
    if s.get("story_plan"):
        story_path=resolve_path(s["story_plan"],base)
        refs.append({"path":str(story_path),"kind":"story_plan"})
        story_document=read(story_path)
        story=story_document.get("story",{})
    else:
        story=s.get("story",{})

    out=Path(out_dir).resolve()
    packets_dir=out/"context_packets"
    packets_dir.mkdir(parents=True,exist_ok=True)
    # Deterministic grouping by actual segment text length, with context pointers.
    groups=[]; current=[]; n=0
    for v in segments:
        size=len(v["text"])
        if current and n+size>chunk_chars:
            groups.append(current); current=[]; n=0
        current.append(v); n+=size
    if current: groups.append(current)
    packet_paths=[]
    for i,group in enumerate(groups,1):
        filepath=packets_dir/("packet_%03d.json"%i)
        save(filepath,{"project_id":s["project_id"],"packet_index":i,
                       "packet_count":len(groups),"transcript_origin":transcript_origin,
                       "previous_segment_id":segments[segments.index(group[0])-1]["segment_id"] if group[0] is not segments[0] else None,
                       "segments":group,
                       "next_segment_id":segments[segments.index(group[-1])+1]["segment_id"] if group[-1] is not segments[-1] else None})
        packet_paths.append({"path":str(filepath),"segment_start":group[0]["segment_id"],
                             "segment_end":group[-1]["segment_id"],"sha256":file_sha(filepath)})
    expected_hashes={x["path"]:file_sha(x["path"]) for x in
                     refs+frames+media+packet_paths}
    source={"builder_sha256":file_sha(__file__),
            "project_id":s["project_id"],"task":"EDITORIAL_PLAN",
            "brief":s["brief"],"output":{"width":720,"height":1280,"fps":30},
            "video":{"duration_ms":int(s["video"]["duration_ms"]),
                     "source_rights":s["video"].get("source_rights","UNCLEARED")},
            "transcript_origin":transcript_origin,
            "segments":segments,"clips":clips,"assets":assets,"media":media,"frames":frames,
            "story":story,"source_documents":refs,"context_packets":packet_paths,
            "expected_evidence_sha256":expected_hashes}
    check_source(source)
    # Make segment-clip timing checks prior to handoff. Silence/gaps are allowed
    # but a transcript segment cannot be silently mapped to a different clip.
    clip_ids={c["clip_id"]:c for c in clips}
    for v in segments:
        c=clip_ids.get(v["clip_id"])
        must(c is not None,"Transcript segment references unknown clip "+v["clip_id"])
        assert c
        must(c["timeline_start_ms"]<=v["start_ms"]<v["end_ms"]<=
             c["timeline_start_ms"]+c["duration_ms"],
             "Transcript timestamp exceeds its source clip: "+v["segment_id"])
    save(out/"source.json",source)
    save(out/"context_index.json",{"project_id":s["project_id"],
         "transcript_origin":transcript_origin,"source_sha256":file_sha(out/"source.json"),
         "packets":packet_paths,"segment_count":len(segments),
         "status":"PREPARED_FOR_CHATGPT_NOT_YET_ANALYZED"})
    return {"status":"PACKET_PASS","source":str(out/"source.json"),
            "packets":len(groups),"segments":len(segments),
            "transcript_origin":transcript_origin,
            "source_sha256":file_sha(out/"source.json")}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--spec",required=True)
    p.add_argument("--out",required=True)
    p.add_argument("--chunk-chars",type=int,default=4200)
    args=p.parse_args()
    try:
        print(json.dumps(build_source(args.spec,args.out,chunk_chars=args.chunk_chars),indent=2))
        return 0
    except (OSError,ValueError,KeyError,TypeError,IndexError) as e:
        print(json.dumps({"status":"BLOCKED","error":str(e)}),file=sys.stderr)
        return 2

if __name__=="__main__": raise SystemExit(main())
