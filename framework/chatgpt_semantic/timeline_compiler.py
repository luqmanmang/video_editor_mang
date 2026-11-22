#!/usr/bin/env python3
"""Compile validated ChatGPT decisions to immutable, private Remotion 720p props.

Compiler NEVER invents words, trims, headlines or publish authorization.
A 'compiler PASS' is not audiovisual, face-safe or creative approval.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path, PurePosixPath
import sys

from .handoff import check_response, file_sha, read, save, verify_lineage, assert_ok, canon, sha

FPS=30
EXPORT={"width":720,"height":1280,"fps":FPS,"codec":"h264","audio_codec":"aac"}

def frame(ms):
    return round(ms*FPS/1000)

def safe_src(value):
    assert_ok(isinstance(value,str) and value and
              not value.startswith(("/", "\\")) and "\\" not in value and
              ":" not in value and ".." not in PurePosixPath(value).parts,
              "Invalid static media path")
    return value

def compile_job(job_dir):
    folder=Path(job_dir).resolve()
    verify_lineage(folder)
    req=read(folder/"request.json")
    state=read(folder/"state.json")
    assert_ok(state.get("status")=="VALIDATED_FOR_PRIVATE_PREVIEW",
              "Semantic decision not validated for preview")
    decision_path=Path(state["active_decision"])
    assert_ok(decision_path.is_file() and file_sha(decision_path)==state["decision_sha256"],
              "Decision modified or missing")
    decision=read(decision_path)
    check_response(decision,req)
    src=req["source"]
    assert_ok(src["output"]=={"width":720,"height":1280,"fps":30},
              "720p export contract violation")
    clips=src.get("clips",[])
    assert_ok(clips,"Source clips missing: prepare real clip metadata before compiling")
    segs={s["segment_id"]:s for s in src["segments"]}
    assets={a["asset_id"]:a for a in src.get("assets",[])}
    clipmap={c["clip_id"]:c for c in clips}
    warnings=[]
    blockers=[]
    compiled=[]
    for c in clips:
        safe_src(c["src"])
        a=frame(c["timeline_start_ms"])
        z=frame(c["timeline_start_ms"]+c["duration_ms"])
        assert_ok(z>a,"Zero-frame source clip")
        assert_ok(len(c.get("source_sha256",""))==64,
                  "Source clip missing checksum from packet builder")
        compiled.append({"clip_id":c["clip_id"],"src":c["src"],
                         "source_sha256":c["source_sha256"],"from_frame":a,
                         "duration_frames":z-a,
                         "trim_before_frames":frame(c["source_in_ms"]),
                         "base_scale":float(c.get("base_scale",1.0)),
                         "captions_burned":bool(c.get("captions_burned",False))})
    scenes=[]; headlines=[]; motions=[]; brolls=[]
    for beat in decision["beats"]:
        a=segs[beat["start_segment_id"]]["start_ms"]
        z=segs[beat["end_segment_id"]]["end_ms"]
        a_f,z_f=frame(a),frame(z)
        assert_ok(a_f<z_f,"Beat spans less than one frame: "+beat["beat_id"])
        ref_ids=beat["evidence_segment_ids"]
        source_ids=list(dict.fromkeys(segs[sid]["clip_id"] for sid in ref_ids))
        scenes.append({"beat_id":beat["beat_id"],"role":beat["story_role"],
                       "from_frame":a_f,"duration_frames":z_f-a_f,
                       "meaning":beat["meaning"],"source_clip_ids":source_ids,
                       "source_segment_ids":ref_ids})
        h=beat["headline"]
        if h["style_hint"]!="NONE":
            headlines.append({"beat_id":beat["beat_id"],"text":h["text"],
                              "style_hint":h["style_hint"],"from_frame":a_f,
                              "duration_frames":z_f-a_f,"geometry_status":"PENDING_VISUAL_QA"})
            blockers.append("UNPLACED_HEADLINE:"+beat["beat_id"])
        br=beat["broll"]
        if br.get("asset_id"):
            asset=assets[br["asset_id"]]
            assert_ok(asset["license_status"]=="VERIFIED","B-roll provenance invalid")
            safe_src(asset["src"])
            captions=[]
            for segment in src["segments"]:
                if segment["end_ms"]<=a or segment["start_ms"]>=z:
                    continue
                text=segment["text"].strip()
                cue_start=frame(max(segment["start_ms"],a))
                cue_end=frame(min(segment["end_ms"],z))
                if cue_end<=cue_start:
                    continue
                if len(text)>64:
                    blockers.append("BROLL_CAPTION_TEXT_TOO_LONG:"+beat["beat_id"])
                captions.append({"start_frame":cue_start,"end_frame":cue_end,
                                 "text":text,"segment_id":segment["segment_id"]})
            if not captions:
                blockers.append("BROLL_WITHOUT_SPOKEN_CAPTION:"+beat["beat_id"])
            if src.get("transcript_origin")!="HUMAN_VERIFIED":
                blockers.append("BROLL_CAPTIONS_NOT_HUMAN_VERIFIED:"+beat["beat_id"])
            warnings.append("BROLL_CAPTIONS_REQUIRE_VISUAL_LISTENING_QA:"+beat["beat_id"])
            brolls.append({"beat_id":beat["beat_id"],"asset_id":asset["asset_id"],
                           "src":asset["src"],"from_frame":a_f,
                           "duration_frames":z_f-a_f,"muted":True,
                           "source_url":asset["source_url"],
                           "source_sha256":asset["sha256"],"caption_cues":captions})
        m=beat["motion"]
        if m["mode"]!="STATIC":
            start_clip=clipmap[segs[beat["start_segment_id"]]["clip_id"]]
            end_clip=clipmap[segs[beat["end_segment_id"]]["clip_id"]]
            if start_clip["clip_id"]!=end_clip["clip_id"]:
                blockers.append("MOTION_CROSSES_CLIP:"+beat["beat_id"])
            elif start_clip["base_scale"]>1.1:
                # Source headline crop is already aggressive; prevent unsafe extra zoom.
                warnings.append("MOTION_SUPPRESSED_EXISTING_CROP:"+beat["beat_id"])
            else:
                motions.append({"beat_id":beat["beat_id"],"mode":m["mode"],
                                "from_frame":a_f,"duration_frames":z_f-a_f,
                                "max_relative_scale":1.03 if m["mode"]=="SUBTLE" else 1.05,
                                "frame_safety_status":"PENDING_VISUAL_QA"})
                warnings.append("MOTION_REQUIRES_FACE_REVIEW:"+beat["beat_id"])
        if beat["cut_guidance"]=="TRIM_SILENCE":
            blockers.append("UNVERIFIED_PRECISION_CUT:"+beat["beat_id"])
        elif beat["cut_guidance"]=="REVIEW":
            warnings.append("CUT_REQUIRES_LISTENING:"+beat["beat_id"])
    if decision.get("excluded_segments"):
        blockers.append("EXCLUDED_SPEECH_REQUIRES_APPROVED_CUT_PLAN")
    if src.get("transcript_origin")!="HUMAN_VERIFIED":
        warnings.append("ASR_TEXT_AND_TIMINGS_UNVERIFIED")
    if not src.get("frames"):
        warnings.append("NO_VISUAL_FRAME_EVIDENCE")
    # No autogenerated captions in this compiler; burned subtitles are preserved.
    if len(headlines):
        warnings.append("HEADLINE_NOT_RENDERED_UNTIL_PIXEL_POSITIONING_QA")
    total_frames=frame(src["video"]["duration_ms"])
    assert_ok(compiled[-1]["from_frame"]+compiled[-1]["duration_frames"]==total_frames,
              "Source clip frames do not cover output timeline")
    timeline={
        "schema_version":"1.0.0","project_id":src["project_id"],
        "private_preview_only":True,"publish_allowed":False,
        "export":dict(EXPORT),"duration_in_frames":total_frames,
        "clips":compiled,"scenes":scenes,"brolls":brolls,"motions":motions,
        "headline_requests":headlines,"render_ready":len(blockers)==0,
        "blocked_reasons":sorted(set(blockers)),
        "qa_pending":sorted(set(warnings+["HUMAN_CREATIVE_REVIEW","ORIGINAL_SOURCE_RIGHTS"])),
        "provenance":{"semantic_job_id":req["job_id"],
                      "input_fingerprint":req["input_fingerprint"],
                      "decision_sha256":file_sha(decision_path),
                      "revision":decision["revision"],
                      "source_rights":src["video"].get("source_rights","UNCLEARED"),
                      "transcript_origin":src.get("transcript_origin","UNSPECIFIED"),
                      "decision_source":decision["decision_source"],
                      "review_ref":decision["review_ref"]}
    }
    props={"timeline":timeline}
    compiler_digest=file_sha(__file__)
    path=folder/"timelines"/("revision_%03d_%s_props.json" %
                             (decision["revision"],compiler_digest[:10]))
    if path.exists():
        assert_ok(canon(read(path))==canon(props),"Compiled timeline conflict for same revision")
        result="REUSED"
    else:
        save(path,props)
        result="COMPILED_PREVIEW" if timeline["render_ready"] else "COMPILED_BLOCKED"
    # lineage is immutable per revision and includes exact compiler code digest.
    audit_path=folder/"timelines"/("revision_%03d_%s_audit.json" %
                                   (decision["revision"],compiler_digest[:10]))
    audit={"status":result,"input_fingerprint":req["input_fingerprint"],
           "decision_sha256":file_sha(decision_path),"compiler_sha256":compiler_digest,
           "props_sha256":file_sha(path),"render_ready":timeline["render_ready"],
           "blocked_reasons":timeline["blocked_reasons"],"qa_pending":timeline["qa_pending"]}
    if not audit_path.exists():
        save(audit_path,audit)
    return {"status":result,"path":str(path),"sha256":file_sha(path),
            "duration_in_frames":total_frames,"render_ready":timeline["render_ready"],
            "blocked_reasons":timeline["blocked_reasons"],
            "qa_pending":timeline["qa_pending"]}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--job-dir",required=True)
    args=parser.parse_args()
    try:
        print(json.dumps(compile_job(args.job_dir),indent=2,ensure_ascii=False))
        return 0
    except (OSError,ValueError,KeyError,TypeError) as e:
        print(json.dumps({"status":"FAILED","error":str(e)},ensure_ascii=False),file=sys.stderr)
        return 2

if __name__=="__main__":raise SystemExit(main())
