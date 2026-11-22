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
        self.write(self.transcript,{"transcript_origin":"HUMAN_VERIFIED","segments":self.segments})
        self.spec=self.base/"spec.json"
        self.write(self.spec,{
            "project_id":"synthetic_test","brief":{"viewer":"Private QA","goal":"Test contract",
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

if __name__=="__main__":unittest.main()
