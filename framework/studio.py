#!/usr/bin/env python3
"""Video Studio 3: deterministic editorial gates and opt-in asset discovery.
Does not call a model or claim autonomous specialist debate.
Runs in a chat-directed Codespace or a local checkout. Stdlib only.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request

BASE = Path(__file__).resolve().parent
PROJECT = BASE.parent
CACHE = BASE / ".cache"  # ignored in Git
SAFE_LICENSES = {"CC0", "PUBLIC_DOMAIN", "PEXELS", "PIXABAY"}
ROLES = {"creator", "audience_skeptic", "minimalist_editor", "independent_judge"}
REQUIRED_STORY = ("objective", "viewer", "hook_promise", "viewer_prediction", "want", "tapi", "so", "payoff")

def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def save_json(path, data):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def request_json(url, headers=None, seconds=20):
    h = {"User-Agent": "StoryStudio3/0.1 (+private-research; editorial licensing review)"}
    h.update(headers or {})
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=seconds) as r:
        return json.load(r)

def api_search(provider, query, count=5):
    count = max(1, min(count, 10))
    if provider == "pexels":
        key = os.getenv("PEXELS_API_KEY")
        if not key:
            return {"status": "BLOCKED_MISSING_API_KEY", "provider": provider, "results": []}
        url = "https://api.pexels.com/v1/videos/search?" + urllib.parse.urlencode({"query": query, "per_page": count})
        data = request_json(url, {"Authorization": key})
        results = []
        for v in data.get("videos", []):
            files = [f for f in v.get("video_files", []) if f.get("link") and f.get("file_type") == "video/mp4"]
            files.sort(key=lambda f: (f.get("width") or 0) * (f.get("height") or 0), reverse=True)
            results.append({"provider": "pexels", "id": v.get("id"), "page": v.get("url"),
                            "duration": v.get("duration"), "thumbnail": v.get("image"),
                            "creator": v.get("user", {}).get("name"), "download": files[0]["link"] if files else None,
                            "license": "PEXELS", "license_status": "NEEDS_PER_ASSET_REVIEW"})
        return {"status": "OK", "provider": provider, "results": results}
    if provider == "pixabay":
        key = os.getenv("PIXABAY_API_KEY")
        if not key:
            return {"status": "BLOCKED_MISSING_API_KEY", "provider": provider, "results": []}
        url = "https://pixabay.com/api/videos/?" + urllib.parse.urlencode({"key": key, "q": query, "per_page": count, "safesearch": "true"})
        data = request_json(url)
        results = []
        for v in data.get("hits", []):
            variants = v.get("videos", {})
            video = variants.get("medium") or variants.get("small") or {}
            results.append({"provider": "pixabay", "id": v.get("id"), "page": v.get("pageURL"),
                            "duration": v.get("duration"), "thumbnail": v.get("picture_id"),
                            "creator": v.get("user"), "download": video.get("url"),
                            "license": "PIXABAY", "license_status": "NEEDS_PER_ASSET_REVIEW"})
        return {"status": "OK", "provider": provider, "results": results}
    if provider == "commons":
        url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({
            "action": "query", "generator": "search", "gsrsearch": "filetype:video " + query,
            "gsrnamespace": 6, "gsrlimit": count, "prop": "imageinfo",
            "iiprop": "url|size|mime|extmetadata", "format": "json"})
        data = request_json(url)
        results = []
        for pg in data.get("query", {}).get("pages", {}).values():
            ii = next(iter(pg.get("imageinfo", [])), {})
            meta = ii.get("extmetadata", {})
            license_name = re.sub(r"<[^>]+>", "", meta.get("LicenseShortName", {}).get("value", ""))
            results.append({"provider": "commons", "id": pg.get("pageid"),
                            "title": pg.get("title"), "page": ii.get("descriptionurl"),
                            "download": ii.get("url"), "mime": ii.get("mime"),
                            "bytes": ii.get("size"), "license": license_name,
                            "license_status": "NEEDS_PER_ASSET_REVIEW",
                            "creator": re.sub(r"<[^>]+>", "", html.unescape(meta.get("Artist", {}).get("value", "")))[:240]})
        return {"status": "OK", "provider": provider, "results": results}
    raise ValueError("provider must be pexels, pixabay, commons")

def review(plan):
    errors, warnings = [], []
    story = plan.get("story", {})
    for k in REQUIRED_STORY:
        if not str(story.get(k, "")).strip():
            errors.append("STORY_MISSING_" + k.upper())
    if story.get("viewer_prediction", "").strip().lower() == story.get("payoff", "").strip().lower():
        warnings.append("PREDICTION_IDENTICAL_TO_PAYOFF: requires independent audience challenge")
    if plan.get("public_release", False) and plan.get("source_rights") != "CLEARED":
        errors.append("SOURCE_RIGHTS_UNCLEARED")
    profile = plan.get("style_profile", {})
    if profile.get("profile") == "minimalist_talking_head":
        if profile.get("complex_animation", False):
            errors.append("MIN_COMPLEX_ANIMATION_FORBIDDEN")
        if profile.get("a_roll_headline", False):
            errors.append("VIS_HEADLINE_ON_AROLL")
    scenes = plan.get("scenes", [])
    if not scenes:
        errors.append("NO_SCENES")
    last_end = 0.0
    for i, s in enumerate(scenes):
        prefix = f"SCENE_{i+1:02d}_"
        kind = s.get("type")
        try:
            start, duration = float(s.get("start", -1)), float(s.get("duration", 0))
        except (TypeError, ValueError):
            errors.append(prefix + "BAD_TIMING")
            continue
        if start < 0 or duration <= 0:
            errors.append(prefix + "BAD_TIMING")
        if start < last_end - .05:
            errors.append(prefix + "OVERLAP")
        last_end = max(last_end, start + duration)
        if not s.get("story_beat") or not s.get("visual_reason"):
            errors.append(prefix + "NO_STORY_REASON")
        if kind == "a_roll":
            if s.get("headline") or s.get("section_label") or s.get("overlay"):
                errors.append(prefix + "AROLL_DECORATIVE_OVERLAY")
            if not s.get("source"):
                errors.append(prefix + "NO_SOURCE")
            if s.get("captions") not in {"source_burned_in", "generated_positioned", "none"}:
                errors.append(prefix + "UNKNOWN_CAPTION_MODE")
            if s.get("captions") == "none":
                warnings.append(prefix + "CAPTIONS_NONE")
        elif kind == "b_roll":
            asset = s.get("asset", {})
            if not asset.get("file") or not asset.get("page"):
                errors.append(prefix + "BROLL_ASSET_MISSING")
            if asset.get("license_status") != "VERIFIED" or asset.get("license") not in SAFE_LICENSES:
                errors.append(prefix + "BROLL_LICENSE_UNVERIFIED")
            if not s.get("voiceover_source"):
                errors.append(prefix + "BROLL_VOICEOVER_MISSING")
            if s.get("subtitle_policy") not in {"source_burned_in", "generated_positioned"}:
                warnings.append(prefix + "BROLL_SUBTITLE_POLICY_REVIEW")
        elif kind == "animation":
            if not s.get("complexity_justification") or not s.get("human_approved"):
                errors.append(prefix + "ANIMATION_NOT_JUSTIFIED")
        else:
            errors.append(prefix + "UNKNOWN_TYPE")
    if plan.get("render_mode") == "full" and not plan.get("human_story_lock", False):
        errors.append("NO_HUMAN_STORY_LOCK")
    return {"status": "PASS" if not errors else "FAIL", "errors": errors, "warnings": warnings,
            "scenes": len(scenes), "max_end": round(last_end, 3)}

def debate_state(path):
    state = read_json(path)
    votes = state.get("independent_first_pass", {})
    missing = sorted(list({"creator", "audience_skeptic", "minimalist_editor"} - set(votes)))
    if missing:
        return {"status": "BLOCKED", "missing_independent_reviews": missing}
    if not state.get("evidence_ids"):
        return {"status": "BLOCKED", "reason": "NO_EVIDENCE_REFERENCES"}
    if len(state.get("rounds", [])) > 3:
        return {"status": "ESCALATE", "reason": "DEBATE_ROUND_LIMIT"}
    if not state.get("judge"):
        return {"status": "READY_FOR_JUDGE", "allowed_decisions": ["KEEP","REMOVE","REPLACE","ADD","VETO","ESCALATE"]}
    if state["judge"].get("decision") not in {"KEEP","REMOVE","REPLACE","ADD","VETO","ESCALATE"}:
        return {"status": "FAIL", "reason": "INVALID_JUDGE_DECISION"}
    return {"status": "REVIEWED", "decision": state["judge"]["decision"]}

def feedback(path, project, timecode, criticism, diagnosis):
    payload = {"project": project, "timecode": timecode, "feedback": criticism,
               "diagnosis": diagnosis, "status": "CANDIDATE_NOT_PROMOTED",
               "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return {"status": "LOGGED_CANDIDATE", "path": str(target)}

def main():
    a = argparse.ArgumentParser()
    sub = a.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate")
    v.add_argument("plan")
    b = sub.add_parser("debate-check")
    b.add_argument("state")
    f = sub.add_parser("feedback")
    f.add_argument("--log", required=True)
    f.add_argument("--project", required=True)
    f.add_argument("--timecode", required=True)
    f.add_argument("--criticism", required=True)
    f.add_argument("--diagnosis", required=True)
    s = sub.add_parser("search")
    s.add_argument("provider", choices=["pexels", "pixabay", "commons"])
    s.add_argument("query")
    s.add_argument("--count", type=int, default=5)
    s.add_argument("--output")
    c = sub.add_parser("catalog")
    c.add_argument("--output")
    opts = a.parse_args()
    if opts.cmd == "validate":
        result = review(read_json(opts.plan))
    elif opts.cmd == "debate-check":
        result = debate_state(opts.state)
    elif opts.cmd == "feedback":
        result = feedback(opts.log, opts.project, opts.timecode, opts.criticism, opts.diagnosis)
    elif opts.cmd == "search":
        result = api_search(opts.provider, opts.query, opts.count)
        if opts.output:
            save_json(opts.output, result)
    else:
        result = request_json("https://remotionui.com/ai/components.json")
        if opts.output:
            save_json(opts.output, result)
        if isinstance(result, (dict, list)):
            total = len(result.get("components", [])) if isinstance(result, dict) else len(result)
            result = {"status": "OK", "count": total, "path": opts.output}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result.get("status") == "FAIL":
        sys.exit(2)

if __name__ == "__main__":
    main()
