#!/usr/bin/env python3
"""Non-destructive V3 technical QA and contact sheet. No creative PASS claims."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

def run(args, check=True):
    p=subprocess.run(args,capture_output=True,text=True)
    if check and p.returncode: raise RuntimeError("command failed: "+str(args)+"\n"+p.stderr[-1500:])
    return p

def main():
    a=argparse.ArgumentParser()
    a.add_argument("video")
    a.add_argument("--out-dir",required=True)
    a.add_argument("--plan")
    opt=a.parse_args()
    video=Path(opt.video).resolve()
    out=Path(opt.out_dir).resolve();out.mkdir(parents=True,exist_ok=True)
    if not video.is_file(): raise FileNotFoundError(video)
    info=json.loads(run(["ffprobe","-v","error","-show_format","-show_streams","-of","json",str(video)]).stdout)
    streams=info.get("streams",[])
    vids=[s for s in streams if s.get("codec_type")=="video"]
    auds=[s for s in streams if s.get("codec_type")=="audio"]
    dur=float(info["format"].get("duration") or 0)
    errors=[]
    if len(vids)!=1 or vids[0].get("codec_name")!="h264": errors.append("VIDEO_CODEC")
    if not auds or auds[0].get("codec_name")!="aac": errors.append("AUDIO_CODEC")
    if not 36<=dur<=39: errors.append("DURATION_OUT_OF_RANGE")
    if vids and (vids[0].get("width"),vids[0].get("height"))!=(720,1280): errors.append("DIMENSIONS")
    if run(["ffmpeg","-hide_banner","-v","error","-i",str(video),"-f","null","-"],check=False).returncode!=0:
        errors.append("DECODE_FAILURE")
    sheet=out/"kauthar_v3_contact.jpg"
    run(["ffmpeg","-y","-hide_banner","-loglevel","error","-i",str(video),
         "-vf","fps=1/2.9,scale=180:320,tile=4x4","-frames:v","1",str(sheet)])
    shot_times=[1.0,8.9,9.7,27.9,29.1,35.1]
    stills=[]
    for i,t in enumerate(shot_times):
        frame=out/f"v3_frame_{i+1:02d}_{t:.1f}s.jpg"
        run(["ffmpeg","-y","-hide_banner","-loglevel","error","-ss",str(t),"-i",str(video),
             "-frames:v","1","-q:v","3",str(frame)])
        stills.append(str(frame))
    report={"video":str(video),"duration":dur,"bytes":video.stat().st_size,
            "video_stream":vids[0] if vids else None,"audio_stream":auds[0] if auds else None,
            "technical_status":"PASS" if not errors else "FAIL",
            "errors":errors,"contact_sheet":str(sheet),"sample_frames":stills,
            "creative_status":"PENDING_HUMAN_WATCH_AND_AUDIO_LISTEN",
            "source_creator_rights":"UNCLEARED_PRIVATE_ONLY",
            "note":"Checks technical codec/decode only; frame presence, subtitle accuracy and real cut quality require inspection."}
    if opt.plan:
        report["scene_plan"]=str(Path(opt.plan).resolve())
    (out/"kauthar_v3_qa.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"technical_status":report["technical_status"],"errors":errors,
            "duration":dur,"contact_sheet":str(sheet),"report":str(out/"kauthar_v3_qa.json"),
            "creative_status":report["creative_status"]},indent=2))
    if errors: sys.exit(2)
if __name__=="__main__": main()
