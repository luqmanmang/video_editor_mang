"""Fail-closed tests for Codespace-only private editing infrastructure."""
from pathlib import Path
import hashlib
import json
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from production_pipeline.runner import validate_job,ffmpeg_graph,Batch

class ProductionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.id="7436261904798076178"
        d=self.root/self.id
        d.mkdir()
        self.src=d/"original.mp4"
        self.src.write_bytes(b"QA_FAKE_SOURCE_BYTES")
        self.hash=hashlib.sha256(self.src.read_bytes()).hexdigest()
        self.asr={"human_verbatim_verified":False,
                  "segments":[{"start_ms":0,"end_ms":1500,"text":"Test one"},
                              {"start_ms":1500,"end_ms":3000,"text":"Test two"}]}
        (d/"transcript.json").write_text(json.dumps(self.asr),encoding="utf-8")
        (d/"source_manifest.json").write_text(json.dumps({
            "video_id":self.id,"uploader":"kautharrozmal",
            "original_mp4_sha256":self.hash,
            "media_probe":{"duration_ms":3000}}),encoding="utf-8")
        self.job={
            "key":"source_test","video_id":self.id,
            "output":{"width":720,"height":1280,"fps":30},
            "mode":"PRIVATE_REGRESSION","semantic_status":"NOT_VERIFIED",
            "source_rights":"UNCLEARED_PRIVATE_ONLY",
            "cut_ranges_seconds":[[0,1.5],[1.5,3.0]],
            "headline_lines":["CONTEXT-TEST","HEADLINE SAMPLE"],
            "headline_card":{"bottom":280},
            "headline_seconds":2,
            "motion":"STATIC","broll":[]
        }
    def test_preflight_source_sha_and_cut_boundaries(self):
        info=validate_job(self.job,self.root)
        self.assertEqual(info["source_sha256"],self.hash)
        self.assertEqual(info["duration_sec"],3.0)
    def test_source_sha_drift_rejected(self):
        self.src.write_bytes(b"TAMPERED_AFTER_MANIFEST")
        with self.assertRaisesRegex(ValueError,"Source hash changed"):
            validate_job(self.job,self.root)
    def test_1080_and_unapproved_rights_rejected(self):
        self.job["output"]["height"]=1920
        with self.assertRaisesRegex(ValueError,"720x1280"):
            validate_job(self.job,self.root)
        self.job["output"]["height"]=1280
        self.job["source_rights"]="CLEARED_FOR_PUBLIC"
        with self.assertRaisesRegex(ValueError,"private review"):
            validate_job(self.job,self.root)
    def test_mismatched_cut_and_overlaps_rejected(self):
        self.job["cut_ranges_seconds"]=[[0,1.5],[1.4,3]]
        with self.assertRaisesRegex(ValueError,"non-overlapping"):
            validate_job(self.job,self.root)
        self.job["cut_ranges_seconds"]=[[0,1.53],[1.9,3]]
        with self.assertRaisesRegex(ValueError,"transcript boundary"):
            validate_job(self.job,self.root)
    def test_selected_broll_must_be_human_semantic_and_licensed(self):
        file=self.root/"stock.mp4";file.write_bytes(b"fake_stock")
        self.job["broll"]=[{"path":"stock.mp4","sha256":hashlib.sha256(file.read_bytes()).hexdigest(),
            "license_status":"VERIFIED","semantic_approved":False,
            "visual_approved":True,"caption_verified":True,
            "timeline_start_sec":0.4,"duration_sec":0.7}]
        with self.assertRaisesRegex(ValueError,"rights \\+ semantic"):
            validate_job(self.job,self.root)
        self.job["broll"][0]["semantic_approved"]=True
        self.assertEqual(len(validate_job(self.job,self.root)["brolls"]),1)
    def test_visual_headline_cannot_overflow_rules(self):
        self.job["headline_card"]["bottom"]=600
        with self.assertRaisesRegex(ValueError,"bounded"):
            validate_job(self.job,self.root)
    def test_chatgpt_plan_must_pass_handoff(self):
        self.job["mode"]="CHATGPT_VALIDATED"
        with self.assertRaisesRegex(ValueError,"ChatGPT job"):
            validate_job(self.job,self.root)
        self.job["semantic_job_dir"]=str(self.root/"not_a_real_handoff")
        with self.assertRaisesRegex(ValueError,"private Codespace runtime"):
            validate_job(self.job,self.root)
    def test_graph_shortest_duration_no_looped_png(self):
        with TemporaryDirectory() as tmp:
            filtergraph=ffmpeg_graph(self.job,Path(tmp))
            self.assertIn("trim=start=0.000:end=1.500",filtergraph)
            self.assertIn("drawbox=",filtergraph)
            self.assertIn("loudnorm=I=-16",filtergraph)
            self.assertNotIn("loop=1",filtergraph)
    def test_local_video_processing_forbidden(self):
        if sys.platform.startswith("win"):
            with self.assertRaisesRegex(ValueError,"Codespace worker"):
                Batch(self.root/"plan.json")
if __name__=="__main__":
    unittest.main()
