"""Contract regression tests for manual ChatGPT semantic handoff."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from chatgpt_semantic.handoff import prepare, submit, read, check_response

class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p=Path(self.tmp.name)
        self.runtime=self.p/"runtime"
        self.media=self.p/"media.mp4"
        self.media.write_bytes(b"TEST_MEDIA_NOT_A_REAL_VIDEO")
        self.source=self.p/"source.json"
        self.record={
            "project_id":"kauthar_test",
            "task":"EDITORIAL_PLAN",
            "brief":{"viewer":"BM TikTok viewers","goal":"Trust", "platform":"TikTok","language":"ms"},
            "output":{"width":720,"height":1280,"fps":30},
            "video":{"duration_ms":9000},
            "segments":[
                {"segment_id":"seg_01","clip_id":"clip_01","start_ms":0,"end_ms":4500,"text":"Intro and misconception"},
                {"segment_id":"seg_02","clip_id":"clip_02","start_ms":4500,"end_ms":9000,"text":"Final response and payoff"}
            ],
            "assets":[{"asset_id":"asset_01","license_status":"VERIFIED","source_url":"https://example.com"}],
            "media":[{"path":str(self.media)}],
            "frames":[]
        }
        self.persist()
    def persist(self):
        self.source.write_text(json.dumps(self.record),encoding="utf-8")
    def open_job(self):
        prepared=prepare(self.source,self.runtime)
        d=Path(prepared["folder"])
        return prepared,d
    def response(self,d):
        r=read(d/"response_template.json")
        b=r["beats"][0]
        b["meaning"]="Viewer expects one answer but speaker reveals another"
        b["headline"]={"text":"INGATKAN BARANG MEWAH?","style_hint":"OUTLINE",
                       "reason":"Creates relevant prediction; layout pending"}
        b["story_role"]="TAPI"
        r["beats"].append({
            "beat_id":"beat_02","start_segment_id":"seg_02","end_segment_id":"seg_02",
            "evidence_segment_ids":["seg_02"],"story_role":"PAYOFF",
            "meaning":"Spoken answer directly resolves the setup from previous segment",
            "headline":{"text":None,"style_hint":"NONE","reason":"Source reveal needs no overlay"},
            "broll":{"asset_id":None,"reason":"A-roll is enough to show speaker"},
            "motion":{"mode":"SUBTLE","reason":"Light emphasis on reveal"},
            "cut_guidance":"REVIEW"})
        return r
    def test_prepare_idempotent_and_lineage(self):
        x,d=self.open_job()
        self.assertEqual(x["status"],"PREPARED")
        self.assertEqual(prepare(self.source,self.runtime)["status"],"REUSED")
        lineage=read(d/"lineage.json")
        self.assertIn(str(self.media),lineage["evidence_sha256"])
        self.assertTrue((d/"analysis_prompt.md").exists())
        self.assertEqual(read(d/"state.json")["status"],"PENDING_CHATGPT")
    def test_submit_idempotency_revision_conflict(self):
        x,d=self.open_job()
        r=self.response(d)
        f=self.p/"response.json"; f.write_text(json.dumps(r),encoding="utf-8")
        self.assertEqual(submit(x["job_id"],f,self.runtime)["status"],"VALIDATED_FOR_PRIVATE_PREVIEW")
        self.assertEqual(submit(x["job_id"],f,self.runtime)["status"],"REUSED_VALIDATED")
        r["beats"][0]["meaning"]="Completely different edited text that needs a new revision"
        f.write_text(json.dumps(r),encoding="utf-8")
        with self.assertRaisesRegex(ValueError,"Revision conflict"):
            submit(x["job_id"],f,self.runtime)
        r["revision"]=2
        f.write_text(json.dumps(r),encoding="utf-8")
        self.assertEqual(submit(x["job_id"],f,self.runtime)["revision"],2)
        self.assertEqual(read(d/"state.json")["latest_revision"],2)
    def test_asset_hallucination_and_uncovered_transcript(self):
        x,d=self.open_job()
        r=self.response(d)
        r["beats"][0]["broll"]={"asset_id":"invented","reason":"Reference to fake asset"}
        with self.assertRaisesRegex(ValueError,"Hallucinated"):
            check_response(r,read(d/"request.json"))
        r["beats"][0]["broll"]={"asset_id":None,"reason":"Speaker sufficient"}
        r["beats"].pop()
        with self.assertRaisesRegex(ValueError,"Every transcript segment"):
            check_response(r,read(d/"request.json"))
        r["excluded_segments"]=[{"segment_id":"seg_02",
                                 "reason":"Omitted for a justified private test cut"}]
        self.assertEqual(check_response(r,read(d/"request.json"))["status"],"PASS")
    def test_changed_source_or_media_blocks_stale(self):
        x,d=self.open_job()
        r=self.response(d)
        f=self.p/"response.json"; f.write_text(json.dumps(r),encoding="utf-8")
        self.media.write_bytes(b"CHANGED_MEDIA")
        with self.assertRaisesRegex(ValueError,"Media changed"):
            submit(x["job_id"],f,self.runtime)
        self.assertEqual(read(d/"state.json")["status"],"PENDING_CHATGPT")
        self.assertNotEqual(prepare(self.source,self.runtime)["job_id"],x["job_id"])
    def test_720p_hard_gate(self):
        self.record["output"]["width"]=1080
        self.persist()
        with self.assertRaisesRegex(ValueError,"720x1280"):
            prepare(self.source,self.runtime)

if __name__=="__main__":
    unittest.main()
