#!/usr/bin/env python3
"""Gate Remotion private output to EXACT 720x1280, verify media and full decode."""
from __future__ import annotations
import argparse
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys

from .handoff import read, file_sha, save, assert_ok
from .timeline_compiler import safe_src, compile_job

FPS=30

def probe(file):
    run=subprocess.run(["ffprobe","-v","error","-show_format","-show_streams",
                        "-of","json",str(file)],capture_output=True,text=True)
    assert_ok(run.returncode==0,"ffprobe error: "+run.stderr[-700:])
    return json.loads(run.stdout)

def validate(props_path, app_dir, output):
    props_path=Path(props_path).resolve()
    # Require the exact immutable output from the current validated decision,
    # not arbitrary JSON that happens to say render_ready=true.
    canonical=compile_job(props_path.parent.parent)
    assert_ok(Path(canonical["path"]).resolve()==props_path and
              canonical["sha256"]==file_sha(props_path),
              "Render props are not the current immutable validated timeline")
    props=read(props_path)
    t=props["timeline"]
    assert_ok(t["export"]=={"width":720,"height":1280,"fps":30,"codec":"h264","audio_codec":"aac"},
              "Render gate only accepts native 720x1280/30fps H264+AAC")
    assert_ok(t["private_preview_only"] is True and t["publish_allowed"] is False,
              "Publish authorization cannot be inferred from semantic output")
    assert_ok(t["render_ready"] is True and not t["blocked_reasons"] and
              not t.get("headline_requests"),"Timeline has unresolved safe-render gates")
    assert_ok(t["clips"] and t["duration_in_frames"]>0,"No valid source clips")
    assert_ok(output.suffix.lower()==".mp4","Output must be .mp4")
    public=(app_dir/"public").resolve()
    covered=0
    for c in t["clips"]:
        assert_ok(c["from_frame"]==covered and c["duration_frames"]>0,
                  "Video gaps/overlapping source clips")
        covered+=c["duration_frames"]
        src=safe_src(c["src"])
        path=(public/src).resolve()
        assert_ok(path.is_relative_to(public) and path.is_file(),"Missing A-roll media: "+src)
        assert_ok(file_sha(path)==c.get("source_sha256"),
                  "A-roll media content changed since ChatGPT review: "+src)
        metadata=probe(path)
        video=next((v for v in metadata["streams"] if v["codec_type"]=="video"),None)
        assert_ok(video is not None,"A-roll source has no video: "+src)
        frames=c["trim_before_frames"]+c["duration_frames"]
        fmt=metadata["format"]
        assert_ok(float(fmt["duration"])+0.06 >= frames/FPS,
                  "Clip trim exceeds source media duration: "+src)
        assert_ok(any(v["codec_type"]=="audio" for v in metadata["streams"]),
                  "A-roll has no original audio: "+src)
    assert_ok(covered==t["duration_in_frames"],"Timeline duration mismatch")
    for b in t.get("brolls",[]):
        src=safe_src(b["src"])
        path=(public/src).resolve()
        assert_ok(path.is_relative_to(public) and path.is_file(),"Missing B-roll: "+src)
        assert_ok(file_sha(path)==b.get("source_sha256"),
                  "B-roll media changed since ChatGPT review: "+src)
        assert_ok(b.get("caption_cues"),"B-roll has no validated spoken caption cues")
        assert_ok(float(probe(path)["format"]["duration"])+0.06 >= b["duration_frames"]/FPS,
                  "B-roll shorter than semantic beat: "+src)
    return {"clips":len(t["clips"]),"brolls":len(t.get("brolls",[])),
            "duration_frames":t["duration_in_frames"],"props_sha256":file_sha(props_path)}

def render(props, app, out, *, dry_run=False):
    props=Path(props).resolve()
    app=Path(app).resolve()
    out=Path(out).resolve()
    report=out.with_suffix(".qa.json")
    checks=validate(props,app,out)
    if dry_run:
        return {"status":"DRY_RUN_PASS",**checks}
    assert_ok(not out.exists(),"Output already exists: review/rename; no silent overwrite")
    out.parent.mkdir(parents=True,exist_ok=True)
    command=["npx","remotion","render","src/index.ts","Semantic720",str(out),
             "--props="+str(props),"--codec=h264","--concurrency=1","--scale=1"]
    print("STAGE:RENDER_720",flush=True)
    result=subprocess.run(command,cwd=app)
    assert_ok(result.returncode==0,"Remotion render FAILED exit="+str(result.returncode))
    assert_ok(out.is_file() and out.stat().st_size>0,"Render exited 0 but output missing")
    print("STAGE:TECHNICAL_QA",flush=True)
    info=probe(out)
    streams=info["streams"]
    video=next((s for s in streams if s["codec_type"]=="video"),None)
    audio=next((s for s in streams if s["codec_type"]=="audio"),None)
    assert_ok(video is not None and audio is not None,"Missing video or audio in output")
    assert_ok((video["width"],video["height"],video["codec_name"])==(720,1280,"h264"),
              "Output violates 720p H.264 contract")
    assert_ok(audio["codec_name"]=="aac","Missing AAC audio")
    decode=subprocess.run(["ffmpeg","-nostats","-v","error","-i",str(out),"-f","null","-"],
                          capture_output=True,text=True)
    assert_ok(decode.returncode==0,"Full video decode failed: "+decode.stderr[-800:])
    origin=read(props)["timeline"]["provenance"].get("transcript_origin")
    result_data={"status":"TECHNICAL_PASS_SYNTHETIC_ONLY" if origin=="TEST_FIXTURE"
                 else "TECHNICAL_PASS_PRIVATE_ONLY","output":str(out),
                 "sha256":file_sha(out),"bytes":out.stat().st_size,
                 "duration_sec":float(info["format"]["duration"]),
                 "width":720,"height":1280,"fps":30,"video_codec":"h264",
                 "audio_codec":"aac","full_decode":"PASS",
                 "creative_approval":"PENDING","original_source_rights":"UNCLEARED",
                 "transcript_origin":origin,
                 "props_sha256":checks["props_sha256"]}
    save(report,result_data)
    print("GATE:resolution_720p=PASS",flush=True)
    print("GATE:full_decode=PASS",flush=True)
    print("METRIC:output_bytes="+str(out.stat().st_size),flush=True)
    return result_data

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--props",required=True)
    p.add_argument("--app",required=True)
    p.add_argument("--out",required=True)
    p.add_argument("--dry-run",action="store_true")
    a=p.parse_args()
    try:
        print(json.dumps(render(a.props,a.app,a.out,dry_run=a.dry_run),indent=2))
        return 0
    except (OSError,RuntimeError,ValueError,KeyError,TypeError) as e:
        print("GATE:render_720=FAIL",flush=True)
        print(json.dumps({"status":"FAILED","error":str(e)}),file=sys.stderr)
        return 2

if __name__=="__main__":raise SystemExit(main())
