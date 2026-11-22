import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from studio import review, debate_state, api_search, feedback

STORY = dict(objective="trust", viewer="personal finance audience",
  hook_promise="why temporary purchase happiness fails",
  viewer_prediction="more expensive purchases may satisfy",
  want="viewer wants meaningful spending", tapi="buying things gives brief excitement",
  so="consider experiences, time, generosity", payoff="purchases are not the only source of value")
def base():
    return {"story":STORY, "public_release":False, "source_rights":"UNCLEARED",
        "style_profile":{"profile":"minimalist_talking_head","complex_animation":False,
          "a_roll_headline":False},"human_story_lock":True,"render_mode":"full",
        "scenes":[{"type":"a_roll","start":0,"duration":3,"story_beat":"HOOK",
                   "visual_reason":"speaker clarity","source":"01_hook.mp4","captions":"source_burned_in"}]}
class StudioTests(unittest.TestCase):
    def test_minimalist_pass(self):
        self.assertEqual(review(base())["status"],"PASS")
    def test_v2_overlay_rejected(self):
        p=base()
        p["scenes"][0]["headline"]="HUGE TEXT"
        self.assertIn("SCENE_01_AROLL_DECORATIVE_OVERLAY", review(p)["errors"])
    def test_unlicensed_broll_rejected(self):
        p=base()
        p["scenes"].append(dict(type="b_roll",start=3,duration=2,story_beat="TAPI",
           visual_reason="real-life footage", voiceover_source="01_hook.mp4",
           asset=dict(file="x.mp4",page="https://example.org",license="UNKNOWN",license_status="UNVERIFIED")))
        self.assertIn("SCENE_02_BROLL_LICENSE_UNVERIFIED", review(p)["errors"])
    def test_animation_requires_approval(self):
        p=base()
        p["scenes"].append(dict(type="animation",start=3,duration=2,story_beat="SO",visual_reason="pretty"))
        self.assertIn("SCENE_02_ANIMATION_NOT_JUSTIFIED",review(p)["errors"])
    def test_source_rights_block_release(self):
        p=base();p["public_release"]=True
        self.assertIn("SOURCE_RIGHTS_UNCLEARED", review(p)["errors"])
    def test_no_silent_broll_substitute(self):
        p=base()
        p["scenes"].append(dict(type="b_roll",start=3,duration=2,story_beat="TAPI",
          visual_reason="needs visual",voiceover_source="01_hook.mp4",asset={}))
        self.assertIn("SCENE_02_BROLL_ASSET_MISSING",review(p)["errors"])
    def test_debate_independence_required(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"d.json"
            p.write_text(json.dumps({"independent_first_pass":{"creator":{}}}),encoding="utf-8")
            self.assertEqual(debate_state(p)["status"],"BLOCKED")
    def test_feedback_append_only(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"f.jsonl"
            feedback(p,"demo","00:10","too much graphics","minimalist style")
            feedback(p,"demo","00:20","too much text","caption-only")
            self.assertEqual(len(p.read_text().strip().splitlines()),2)
if __name__ == "__main__": unittest.main()
