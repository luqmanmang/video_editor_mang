#!/usr/bin/env python3
"""Codespace: verified original+ASR -> private ChatGPT semantic review packet.

Creates evidence, never invents speech, transcript accuracy or human approval.
This is NOT an LLM call; ChatGPT reads the generated packet through Desktop
Commander in the conversation and manually submits validated editorial JSON.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys

from .runner import INPUT_ROOT,RUN_ROOT,require,read,sha,atomic,within
from framework.chatgpt_semantic.packet_builder import build_source
from framework.chatgpt_semantic.handoff import prepare

def normalize_asr(document,duration_ms):
    segments=document.get("segments",[])
    require(isinstance(segments,list) and segments,"No ASR segments")
    result=[]; last_end=-1
    for index,segment in enumerate(segments,1):
        start,end=segment.get("start_ms"),segment.get("end_ms")
        text=segment.get("text")
        require(type(start)==int and type(end)==int and
                last_end<=start<end<=duration_ms,
                "Overlapping/missing ASR timestamps; needs human reconciliation")
        require(isinstance(text,str) and text.strip(),"ASR speech text missing")
        result.append({"segment_id":"s%04d"%index,"clip_id":"original_01",
                       "start_ms":start,"end_ms":end,"text":text})
        last_end=end
    return result

def build(video_id,work_root=RUN_ROOT):
    require(sys.platform.startswith("linux") and
            Path("/workspaces/video_editor_mang").is_dir(),
            "Evidence preparation must run inside Codespace")
    require(video_id.isdigit() and 16<=len(video_id)<=21,"Invalid source TikTok ID")
    media=within(INPUT_ROOT/video_id,INPUT_ROOT)
    src=media/"original.mp4"
    meta=read(media/"source_manifest.json")
    transcript_path=media/"transcript.json"
    transcript=read(transcript_path)
    require(sha(src)==meta.get("original_mp4_sha256"),"Original source SHA-256 changed")
    duration=int(meta["media_probe"]["duration_ms"])
    segments=normalize_asr(transcript,duration)
    work=within(Path(work_root)/("semantic_"+video_id),work_root)
    work.mkdir(parents=True,exist_ok=True)
    normalized=work/"transcript_normalized.json"
    # Unmodified ASR transcript is always the provenance source document.
    atomic(normalized,{"transcript_origin":"ASR_UNVERIFIED",
                       "original_asr_sha256":sha(transcript_path),
                       "segments":segments})
    frames=[]
    for idx,msec in enumerate((int(duration*.10),int(duration*.44),int(duration*.78)),1):
        frame=work/("sample_%02d.jpg"%idx)
        if not frame.is_file():
            cmd=["ffmpeg","-hide_banner","-v","error","-ss",str(msec/1000),
                 "-i",str(src),"-frames:v","1","-vf","scale=360:640",str(frame)]
            run=subprocess.run(cmd,capture_output=True,text=True,timeout=60)
            require(run.returncode==0 and frame.is_file(),
                    "Frame evidence extraction failed: "+run.stderr[-400:])
        frames.append({"path":str(frame),"at_ms":msec})
    spec={"project_id":"kauthar_"+video_id,
          "brief":{"viewer":"BM TikTok audience",
                   "goal":"Video editorial story review with fidelity to actual speech",
                   "platform":"TikTok","language":"ms"},
          "video":{"duration_ms":duration,"source_rights":"UNCLEARED"},
          "transcript_path":str(normalized),
          "extra_evidence_paths":[str(transcript_path)],
          "clips":[{"clip_id":"original_01","path":str(src),
                    "static_src":"private_job_media/kauthar/"+video_id+"/original.mp4",
                    "timeline_start_ms":0,"duration_ms":duration,"source_in_ms":0,
                    "base_scale":1.0,"captions_burned":True}],
          "frames":frames,
          "story":{"status":"REQUIRES_CHATGPT_MANUAL_WTS_REVIEW",
                   "source_notes":"Source ASR is unverified, no claim of accurate dialogue."}}
    spec_path=work/"spec.json"
    atomic(spec_path,spec)
    bundle=build_source(spec_path,work/"context")
    result=prepare(bundle["source"],work/"runtime")
    print("GATE:semantic_context_packet=PASS",flush=True)
    print("GATE:semantic_manual_review=PENDING",flush=True)
    print(json.dumps({"status":"PENDING_CHATGPT","source_id":video_id,
         "segments":len(segments),"source_sha256":sha(src),"job_id":result["job_id"],
         "private_job_dir":result["folder"]},indent=2))
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--video-id",required=True)
    a=p.parse_args()
    try:
        build(a.video_id)
        return 0
    except (ValueError,OSError,RuntimeError,KeyError,subprocess.TimeoutExpired) as e:
        print("GATE:semantic_context_packet=FAIL",flush=True)
        print(str(e),file=sys.stderr)
        return 2
if __name__=="__main__":raise SystemExit(main())
