"""End-to-end packet -> manual decision -> compiler contract tests."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chatgpt_semantic.packet_builder import build_source
from chatgpt_semantic.handoff import prepare, submit, read
from chatgpt_semantic.timeline_compiler import compile_job

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.base=Path(self.t.name)
        self.media=self.base/"media"
        self.media.mkdir()
        self.clip=self.media/"test.mp4"
        self.clip.write_bytes(b"synthetic-bytes-not-real-media")
        self.transcript=self.base/"transcript.json"
        self.segments=[
            {"segment_id":"s1","clip_id":"c1","start_ms":0,"end_ms":1300,
             "text":"Synthetic setup for contract test."},
            {"segment_id":"s2","clip_id":"c1","start_ms":1300,"end_ms":3000,
             "text":"Synthetic payoff for contract test."}
        ]
        self.write(self.transcript,{"transcript_origin":"TEST_FIXTURE","segments":self.segments})
        self.spec=self.base/"spec.json"
        self.write(self.spec,{
            "project_id":"smoke_synthetic_test","brief":{"viewer":"Private QA","goal":"Test contract",
            "platform":"TikTok","language":"ms"},
            "video":{"duration_ms":3000,"source_rights":"UNCLEARED"},
            "transcript_path":str(self.transcript),
            "clips":[{"clip_id":"c1","path":str(self.clip),"static_src":"media/test.mp4",
                      "timeline_start_ms":0,"duration_ms":3000,"source_in_ms":0}],
            "frames":[]
        })
    def write(self,p,obj): p.write_text(json.dumps(obj),encoding="utf-8")
    def build(self):
        out=self.base/"packets"
        result=build_source(self.spec,out,chunk_chars=500)
        self.assertEqual(result["status"],"PACKET_PASS")
        self.assertEqual(result["segments"],2)
        return out
    def job(self):
        out=self.build()
        prep=prepare(out/"source.json",self.base/"runtime")
        return Path(prep["folder"]),self.base/"runtime",prep
    def decision(self,folder,headline=False,cut="KEEP"):
        t=read(folder/"response_template.json")
        t["decision_source"]="SYNTHETIC_TEST"
        t["review_ref"]="unit_test_synthetic_not_chatgpt"
        t["story_map"]={
            "hook_promise":"Synthetic setup poses an editorial example question",
            "viewer_prediction":"A test viewer would predict the wrong next answer",
            "want":"The fixture needs to demonstrate complete beat traceability",
            "tapi":"The first line leaves the supposed conclusion unresolved",
            "so":"The second line closes the placeholder test story",
            "payoff":"The test ending supplies the synthetic conclusion",
            "causal_reason":"The second cue was created to complete the first cue",
            "factual_limitations":"No generated test transcript is a quotation from a human"}
        t["beats"]=[
            {"beat_id":"b1","start_segment_id":"s1","end_segment_id":"s1",
             "evidence_segment_ids":["s1"],"story_role":"HOOK",
             "meaning":"Synthetic opening creates a question about the claimed answer",
             "headline":{"text":"BENDA NI PENTING?","style_hint":"BOXED","reason":"Test title"} if headline
             else {"text":None,"style_hint":"NONE","reason":"No duplicate title"},
             "broll":{"asset_id":None,"reason":"Original visual provides adequate context"},
             "motion":{"mode":"SUBTLE","reason":"Gentle introduction movement"},
             "cut_guidance":cut},
            {"beat_id":"b2","start_segment_id":"s2","end_segment_id":"s2",
             "evidence_segment_ids":["s2"],"story_role":"PAYOFF",
             "meaning":"Synthetic payoff answers the opening in this contract fixture",
             "headline":{"text":None,"style_hint":"NONE","reason":"No extra overlay"},
             "broll":{"asset_id":None,"reason":"A-roll sufficient"},
             "motion":{"mode":"STATIC","reason":"No movement necessary"},
             "cut_guidance":"KEEP"}
        ]
        return t
    def submit_decision(self,folder,runtime,decision):
        output=self.base/"response.json"
        self.write(output,decision)
        return submit(folder.name,output,runtime)
    def test_compiles_720p_and_reuses_identical_output(self):
        folder,runtime,prep=self.job()
        self.submit_decision(folder,runtime,self.decision(folder))
        result=compile_job(folder)
        self.assertEqual(result["status"],"COMPILED_PREVIEW")
        self.assertTrue(result["render_ready"])
        props=read(result["path"])
        t=props["timeline"]
        self.assertEqual((t["export"]["width"],t["export"]["height"],t["export"]["fps"]),(720,1280,30))
        self.assertEqual(t["duration_in_frames"],90)
        self.assertEqual(len(t["clips"]),1)
        self.assertEqual(len(t["motions"]),1)
        self.assertEqual(compile_job(folder)["status"],"REUSED")
    def test_heading_requires_visual_qa_and_precision_cut_blocked(self):
        folder,runtime,_=self.job()
        self.submit_decision(folder,runtime,self.decision(folder,headline=True,cut="TRIM_SILENCE"))
        result=compile_job(folder)
        self.assertFalse(result["render_ready"])
        self.assertIn("UNPLACED_HEADLINE:b1",result["blocked_reasons"])
        self.assertIn("UNVERIFIED_PRECISION_CUT:b1",result["blocked_reasons"])
        self.assertEqual(read(result["path"])["timeline"]["publish_allowed"],False)
    def test_transcript_changes_after_packaging_are_detected(self):
        out=self.build()
        t=read(self.transcript)
        t["segments"][0]["text"]="Altered transcript after context packet generation"
        self.write(self.transcript,t)
        with self.assertRaisesRegex(ValueError,"Evidence changed after packet build"):
            prepare(out/"source.json",self.base/"runtime")
    def test_no_transcript_fails_closed(self):
        spec=read(self.spec); del spec["transcript_path"]
        self.write(self.spec,spec)
        with self.assertRaisesRegex(ValueError,"BLOCKED_TRANSCRIPT"):
            build_source(self.spec,self.base/"packets")
    def test_user_excluded_speech_cannot_silently_render(self):
        folder,runtime,_=self.job()
        d=self.decision(folder)
        d["beats"]=d["beats"][:1]
        d["excluded_segments"]=[{"segment_id":"s2","reason":"Explicit exclusion in test"}]
        self.submit_decision(folder,runtime,d)
        t=compile_job(folder)
        self.assertIn("EXCLUDED_SPEECH_REQUIRES_APPROVED_CUT_PLAN",t["blocked_reasons"])
        self.assertFalse(t["render_ready"])

    def stock_fixture(self,verified=True):
        from chatgpt_semantic.handoff import file_sha
        stock_dir=self.media/"stock"
        stock_dir.mkdir(exist_ok=True)
        clip=stock_dir/"experience.mp4"
        clip.write_bytes(b"STOCK_VIDEO_TEST")
        manifest=self.base/"stock.json"
        self.write(manifest,{"assets":[{
            "role":"experience","file":"stock/experience.mp4",
            "page":"https://www.pexels.com/video/example",
            "sha256":file_sha(clip),
            "license_status":"VERIFIED" if verified else "UNVERIFIED",
            "description":"synthetic stock fixture"
        }]})
        spec=read(self.spec)
        spec["stock_manifest"]=str(manifest)
        spec["static_root"]=str(self.media)
        self.write(self.spec,spec)
        return clip

    def test_broll_captions_bound_to_real_segment_ids(self):
        self.stock_fixture()
        t=read(self.transcript)
        t["transcript_origin"]="HUMAN_VERIFIED"  # hypothetical trusted-text contract fixture
        self.write(self.transcript,t)
        folder,runtime,_=self.job()
        d=self.decision(folder)
        d["decision_source"]="CHATGPT_MANUAL"
        d["review_ref"]="synthetic_unit_test_manual_contract"
        d["beats"][0]["broll"]={"asset_id":"experience",
                                 "reason":"Whole short opening idea is represented"}
        self.submit_decision(folder,runtime,d)
        result=compile_job(folder)
        self.assertTrue(result["render_ready"])
        cues=read(result["path"])["timeline"]["brolls"][0]["caption_cues"]
        self.assertEqual(cues[0]["segment_id"],"s1")
        self.assertEqual(cues[0]["text"],"Synthetic setup for contract test.")

    def test_unverified_transcript_blocks_broll_export(self):
        self.stock_fixture()
        folder,runtime,_=self.job()
        d=self.decision(folder)
        d["beats"][0]["broll"]={"asset_id":"experience",
                                 "reason":"Whole context test asset"}
        self.submit_decision(folder,runtime,d)
        result=compile_job(folder)
        self.assertFalse(result["render_ready"])
        self.assertTrue(any("BROLL_CAPTIONS_NOT_HUMAN_VERIFIED" in x
                            for x in result["blocked_reasons"]))

    def test_render_guard_detects_media_hash_drift_before_render(self):
        from chatgpt_semantic.render_guard import validate
        folder,runtime,_=self.job()
        self.submit_decision(folder,runtime,self.decision(folder))
        props=compile_job(folder)["path"]
        app=self.base/"app"
        public=app/"public"/"media"
        public.mkdir(parents=True)
        media=public/"test.mp4"
        media.write_bytes(b"CHANGED_AFTER_SEMANTIC_APPROVAL")
        with self.assertRaisesRegex(ValueError,"media content changed"):
            validate(Path(props),app,self.base/"out.mp4")

    def test_mutated_compiled_timeline_is_rejected(self):
        from chatgpt_semantic.render_guard import validate
        folder,runtime,_=self.job()
        self.submit_decision(folder,runtime,self.decision(folder))
        compiled=Path(compile_job(folder)["path"])
        content=read(compiled)
        content["timeline"]["export"]["width"]=1080
        self.write(compiled,content)
        with self.assertRaisesRegex(ValueError,"Compiled timeline conflict"):
            validate(compiled,self.base/"app",self.base/"preview.mp4")

    def test_missing_story_map_cannot_be_validated(self):
        from chatgpt_semantic.handoff import check_response
        folder,runtime,_=self.job()
        decision=self.decision(folder)
        del decision["story_map"]
        with self.assertRaisesRegex(ValueError,"story_map"):
            check_response(decision,read(folder/"request.json"))

    def test_changed_stock_is_detected_by_packet_builder(self):
        stock=self.stock_fixture()
        stock.write_bytes(b"MUTATED_STOCK_AFTER_MANIFEST_SHA")
        with self.assertRaisesRegex(ValueError,"B-roll checksum mismatch"):
            build_source(self.spec,self.base/"packets")

if __name__=="__main__":unittest.main()

