"""Real transcript routing must never silently rewrite ASR or invent verification."""
import unittest
from framework.production_pipeline.prepare_semantic import normalize_asr

class SemanticSourceTests(unittest.TestCase):
    def test_unchanged_wording_and_stable_segment_fk(self):
        raw={"segments":[
            {"start_ms":0,"end_ms":1200,"text":"Pertama: contoh ayat."},
            {"start_ms":1200,"end_ms":2900,"text":"Kedua: satu lagi ayat."}
        ]}
        got=normalize_asr(raw,3000)
        self.assertEqual([s["segment_id"] for s in got],["s0001","s0002"])
        self.assertEqual(got[0]["text"],raw["segments"][0]["text"])
        self.assertEqual(got[1]["clip_id"],"original_01")
    def test_reject_overlapping_or_out_of_video_speech(self):
        with self.assertRaisesRegex(ValueError,"Overlapping"):
            normalize_asr({"segments":[
                {"start_ms":0,"end_ms":1500,"text":"intro"},
                {"start_ms":1400,"end_ms":2200,"text":"overlap"}]},3000)
        with self.assertRaisesRegex(ValueError,"Overlapping"):
            normalize_asr({"segments":[
                {"start_ms":0,"end_ms":3200,"text":"invalid"}]},3000)
    def test_empty_asr_must_stop_not_invent_words(self):
        with self.assertRaisesRegex(ValueError,"No ASR"):
            normalize_asr({"segments":[]},3000)
if __name__=="__main__":unittest.main()
