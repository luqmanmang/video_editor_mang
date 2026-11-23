"""Discover upstream Claude SKILL.md files without copying or executing them.

ChatGPT can read an exact skill file via Desktop Commander/Codespace SSH and
invoke native tools. This registry does NOT install a native ChatGPT skill.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

# Owner is the existing Video Studio editorial authority, not a substitute
# for the original upstream skill instructions.
SKILLS = {
    "video-edit-pipeline": ("MASTER", "orchestration"),
    "reel-style-clone": ("STORY_DIRECTOR", "reference"),
    "pre-shoot-edit": ("STORY_DIRECTOR", "pre_shoot"),
    "branded-ad-edit": ("VISUAL_EDITOR", "branded"),
    "reel-recut": ("VISUAL_EDITOR", "recut"),
    "arcads-video-edit": ("VISUAL_EDITOR", "multi_take"),
    "recap-video": ("VISUAL_EDITOR", "recap"),
    "talking-head-image-overlays": ("VISUAL_EDITOR", "overlays"),
    "hook-splitter": ("STORY_DIRECTOR", "hook"),
    "hook-variations": ("STORY_DIRECTOR", "hook"),
    "edits-hook-overlay": ("VISUAL_EDITOR", "iphone_overlay"),
    "broll-capture": ("ASSET_DISCOVERY", "browser"),
    "openart-broll": ("ASSET_DISCOVERY", "generated"),
    "arcads-broll": ("ASSET_DISCOVERY", "generated"),
    "edl-tighten": ("VISUAL_EDITOR", "pacing"),
    "sound-design": ("VISUAL_EDITOR", "sound"),
    "ai-audio-sound-design": ("VISUAL_EDITOR", "sound"),
    "video-qa": ("QA_CRITIC", "qa"),
    "video-review-canvas": ("QA_CRITIC", "review"),
    "naming-convention": ("MASTER", "delivery"),
    "capcut-export": ("VISUAL_EDITOR", "export"),
}
REQUIRES = {
    "hook-variations": ["macOS Swift/AVFoundation for native verification"],
    "edits-hook-overlay": ["iPhone USB / Instagram Edits; not Codespace-only"],
    "capcut-export": ["pyJianYingDraft; WIP and actual CapCut verification"],
    "sound-design": ["ELEVENLABS_API_KEY"],
    "openart-broll": ["OpenArt MCP and credits"],
    "arcads-broll": ["ARCADS_API_KEY and companion pack"],
    "arcads-video-edit": ["Arcads integration for generated clips"],
    "video-review-canvas": ["here.now credentials for shared review"],
    "ai-audio-sound-design": ["numpy/scipy plus suitable audio material"],
    "broll-capture": ["Puppeteer or supported browser MCP"],
    "branded-ad-edit": ["HyperFrames render support"],
    "pre-shoot-edit": ["HyperFrames render support"],
}


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def probe(name):
    return shutil.which(name) is not None


def discover(root):
    root = Path(root).expanduser().resolve()
    skill_root = root / ".claude" / "skills"
    assert skill_root.is_dir(), "UPSTREAM_PACK_MISSING"
    names = {p.parent.name for p in skill_root.glob("*/SKILL.md")}
    assert names == set(SKILLS), (
        "UPSTREAM_SKILL_DRIFT added=" + str(sorted(names - set(SKILLS))) +
        " removed=" + str(sorted(set(SKILLS) - names)))
    head = subprocess.run(["git","-C",str(root),"rev-parse","HEAD"],
                          text=True,capture_output=True,check=True).stdout.strip()
    require_core = {key: probe(key) for key in ("node","python3","ffmpeg","ffprobe")}
    environment = {
        "platform": os.name,
        "core_tools": require_core,
        "whisper": probe("whisper-cli"),
        "swift": probe("swiftc"),
        "npm": probe("npm"),
        "hyperframes_scaffold": probe("npx"),
        "env_configured": {
            x: bool(os.environ.get(x)) for x in
            ("ELEVENLABS_API_KEY","GEMINI_API_KEY","ARCADS_API_KEY","OPENAI_API_KEY")
        }
    }
    skills = []
    for name,(owner,lane) in SKILLS.items():
        path = skill_root/name/"SKILL.md"
        needs = REQUIRES.get(name, [])
        if name in {"hook-variations","edits-hook-overlay"}:
            status="PLATFORM_BLOCKED_IN_CODESPACE"
        elif name=="capcut-export":
            status="EXPERIMENTAL"
        elif name in {"sound-design","openart-broll","arcads-broll",
                      "video-review-canvas","arcads-video-edit"}:
            status="OPTIONAL_SERVICE_DEPENDENT"
        else:
            status="REGISTERED_NEEDS_SMOKE_TEST"
        skills.append({
            "name":name, "owner":owner, "lane":lane, "instruction_path":str(path),
            "instruction_sha256":file_sha(path), "status":status,
            "requirements":needs
        })
    return {"schema_version":1, "upstream_commit":head, "upstream_path":str(root),
            "skill_count":len(skills), "environment":environment,
            "skills":skills, "execution_policy":"CHATGPT_MANUAL_VIA_REMOTE_DESKTOP",
            "verified_e2e":False}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--upstream",required=True)
    ap.add_argument("--output")
    args=ap.parse_args()
    result=discover(args.upstream)
    payload=json.dumps(result,indent=2,ensure_ascii=False)+"\n"
    if args.output:
        dest=Path(args.output)
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(payload,encoding="utf-8")
    print(json.dumps({"skill_count":result["skill_count"],"upstream_commit":result["upstream_commit"],
                      "statuses":{x["name"]:x["status"] for x in result["skills"]}},
                     indent=2))
if __name__=="__main__":
    main()
