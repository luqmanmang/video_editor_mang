"""Delivery transport is fail-closed and never encodes any video on Windows."""
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from production_pipeline import windows_dispatch as dispatch
from production_pipeline import broll_search

class TransportTests(unittest.TestCase):
    def test_reject_invalid_job_and_codespace(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,"Invalid run ID"):
                dispatch.deliver("valid-codespace-123","oops",tmp)
            with self.assertRaisesRegex(ValueError,"Codespace ID"):
                dispatch.deliver("bad';rm -rf /","cs_"+"a"*18,tmp)
    def test_copy_only_verified_mp4_then_reuse(self):
        with TemporaryDirectory() as tmp:
            payload=b"\x00synthetic-binary-not-real-media"*6000
            sha=hashlib.sha256(payload).hexdigest()
            run="cs_"+"a"*18
            remote=dispatch.RUNS+"/"+run
            descriptor={
              "run_id":run,"status":"TECHNICAL_PASS_PRIVATE",
              "rights":"UNCLEARED","creative_review":"PENDING",
              "outputs":{"fixture":{"path":remote+"/outputs/fixture.mp4",
                                    "sha256":sha,"bytes":len(payload),
                                    "technical_status":"PASS"}}
            }
            def fake_copy(cs,remote_path,local):
                dst=Path(local)
                if remote_path.endswith("/delivery_manifest.json"):
                    dst.write_text(json.dumps(descriptor),encoding="utf-8")
                else:
                    dst.write_bytes(payload)
            with patch.object(dispatch,"remote_copy",side_effect=fake_copy):
                outcome=dispatch.deliver("test-codespace-12",run,Path(tmp)/"deliver",1)
                self.assertEqual(outcome["count"],1)
                self.assertEqual(list((Path(tmp)/"deliver").glob("*.mp4"))[0].read_bytes(),payload)
                # No QA report, source, logs or transcript may be written locally.
                self.assertEqual([p.suffix for p in (Path(tmp)/"deliver").iterdir()],[".mp4"])
                reused=dispatch.deliver("test-codespace-12",run,Path(tmp)/"deliver",1)
                self.assertEqual(reused["status"],"DELIVERED_VERIFIED_MP4_ONLY")
            descriptor["outputs"]["fixture"]["sha256"]="0"*64
            with patch.object(dispatch,"remote_copy",side_effect=fake_copy):
                with self.assertRaisesRegex(ValueError,"Existing local output"):
                    dispatch.deliver("test-codespace-12",run,Path(tmp)/"deliver",1)
    def test_missing_api_key_cannot_fake_stock_license(self):
        with patch.dict("os.environ",{},clear=True):
            with self.assertRaisesRegex(ValueError,"PEXELS_API_KEY"):
                broll_search.search("pexels","distant relationship conflict",5)
        payload={"videos":[{"id":101,"duration":5,"image":"https://img.example/a.jpg",
                            "url":"https://www.pexels.com/video/example",
                            "width":1080,"height":1920,
                            "video_files":[{"file_type":"video/mp4","height":1280,
                                           "link":"https://video.example/a.mp4"}]}]}
        with patch.dict("os.environ",{"PEXELS_API_KEY":"fake_key"}),\
             patch.object(broll_search,"fetch",return_value=payload):
            results=broll_search.search("pexels","people sitting apart",3)
        self.assertEqual(results["may_render"],False)
        self.assertEqual(results["candidates"][0]["license_status"],
                         "PENDING_LICENSE_EVIDENCE")
        self.assertEqual(results["candidates"][0]["semantic_status"],
                         "PENDING_CHATGPT_REVIEW")
if __name__=="__main__":unittest.main()
