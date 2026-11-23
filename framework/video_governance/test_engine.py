"""Offline negative + positive tests. Mock render probe only in these unit tests."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from framework.video_governance.engine import (
    GateError, STAGES, add_asset, add_clip, add_span, add_variant, audit,
    connection, run_stage, sha, stage_row, trace_frame, recover,
)
from framework.video_governance.router import SKILLS


def story_json():
    return {
        "story_map": {
            "hook_promise":"Apa jadi selepas benda ni berubah?",
            "viewer_prediction":"Penonton expect solusi cepat tapi ada halangan",
            "want":"Creator nak selesaikan masalah yang jelas",
            "tapi":"Masalah utama masih belum diselesaikan",
            "so":"Creator uji penyelesaian dan lihat akibat",
            "payoff":"Bukti yang menjawab janji awal diberi"
        },
        "beats":[{"beat_id":x,"role":x} for x in
                 ("HOOK","WANT","TAPI","SO","PAYOFF")]
    }


class TestGovernance(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.con=connection(self.root/"governance.sqlite")
        self.addCleanup(self.con.close)
        self.con.execute("INSERT INTO projects VALUES (?,?,?,?)",
                         ("p","2026-11-23T00:00:00Z","v1",2))
        self.source=self.root/"source.mp4"
        self.source.write_bytes(b"synthetic source fixture")
        self.assertEqual("REGISTERED",add_asset(self.con,"p","source","SOURCE",
                         self.source,"UNCLEARED_PRIVATE_ONLY"))
        add_clip(self.con,"p","clip_1","source",0,10000)
        self.skill_file=self.write("skill_fixture.md","test-only original skill")
        self.registry=self.write("registry.json",{"skills":[{
            "name":name,"status":"REGISTERED_NEEDS_SMOKE_TEST",
            "instruction_path":str(self.skill_file),
            "instruction_sha256":sha(self.skill_file)
        } for name in SKILLS]})
        add_asset(self.con,"p","editor_skill_pack","REFERENCE",
                  self.registry,"LICENSE_SCOPE_USER_REPORTED")

    def write(self, name, value):
        path=self.root/name
        path.write_text(json.dumps(value,ensure_ascii=False) if isinstance(value,dict)
                        else str(value), encoding="utf-8")
        return path

    def stage(self, name, artifact):
        return run_stage(self.con,"p",name,artifact,
                         [sys.executable,"-c","pass"])

    def establish_to_render(self):
        self.stage("SOURCE",self.write("source_receipt.json",{"assets":["source"]}))
        story=self.write("story.json",story_json())
        self.stage("STORY_LOCK",story)
        plan=self.write("plan.json",{
            "story_sha256":sha(story),"selected_skills":["video-edit-pipeline","reel-recut"],
            "beat_ids":["HOOK","WANT","TAPI","SO","PAYOFF"]
        })
        self.stage("EDIT_PLAN",plan)
        native_proof=self.write("recut_proof.json",{"fixture":"synthetic native output"})
        self.stage("EDIT",self.write("edit.json",{
            "plan_sha256":sha(plan),"beat_ids":["HOOK","WANT","TAPI","SO","PAYOFF"],
            "executed_skills":[{"name":"reel-recut","proof_path":str(native_proof),
                                "proof_sha256":sha(native_proof)}]
        }))
        video=self.root/"render.mp4"
        video.write_bytes(b"synthetic render fixture")
        with patch("framework.video_governance.engine.inspect_video",
                   return_value=(30,1,20)):
            self.stage("RENDER",video)
        return video, story

    def map_all(self, render):
        render_id="render_"+sha(render)[:20]
        for i,name in enumerate(("HOOK","WANT","TAPI","SO","PAYOFF")):
            add_span(self.con,"p",render_id,"span_"+name,name,"clip_1",
                     "PRIMARY",i*200,(i+1)*200,i*4,(i+1)*4,
                     "keep","v1")
        return render_id

    def tech_receipt(self,video):
        native=self.write("native_qa.json",{
            "videoSha256":sha(video),"verdict":"PASS",
            "layers":{"technical":{"status":"pass"}},
            "coverage":{"completed":["technical"],"missingRequired":[]}
        })
        return {"render_sha256":sha(video),"status":"PASS",
                "checks":{x:"PASS" for x in ("decode","video","audio","captions")},
                "qa_report_path":str(native),"qa_report_sha256":sha(native)}

    def qa_to_release(self, video, story):
        self.stage("TECH_QA",self.write("tech.json",self.tech_receipt(video)))
        self.stage("STORY_QA",self.write("story_qa.json",{
            "render_sha256":sha(video),"story_sha256":sha(story),"status":"PASS",
            "checks":{x:"PASS" for x in ("hook_payoff","wts_causality",
                                         "beat_coverage","factual_integrity")}
        }))
        self.stage("HUMAN_REVIEW",self.write("review.json",{
            "render_sha256":sha(video),"human_approved":True,"reviewer":"real reviewer",
            "reviewed_at":"2026-11-23T12:00:00+08:00","visibility":"PRIVATE_REVIEW"
        }))
        self.stage("DELIVERY",video)

    def test_missing_dependency_blocks_skip(self):
        with self.assertRaisesRegex(GateError,"BLOCKED_DEPENDENCY:SOURCE"):
            self.stage("RENDER",self.write("not_render.mp4","data"))
        self.assertIsNone(stage_row(self.con,"p","RENDER"))

    def test_failed_command_not_pass(self):
        with self.assertRaisesRegex(GateError,"COMMAND_EXIT_7"):
            run_stage(self.con,"p","SOURCE",self.root/"will_not_exist",
                      [sys.executable,"-c","raise SystemExit(7)"])
        self.assertEqual("FAILED",stage_row(self.con,"p","SOURCE")["status"])

    def test_asset_content_drift(self):
        self.stage("SOURCE",self.write("source_receipt.json",{"ok":True}))
        self.source.write_bytes(b"changed source")
        with self.assertRaisesRegex(GateError,"STALE_ASSET:source"):
            self.stage("STORY_LOCK",self.write("story.json",story_json()))

    def test_late_broll_invalidates_plan_not_story(self):
        self.stage("SOURCE",self.write("source_receipt.json",{"ok":True}))
        self.stage("STORY_LOCK",self.write("story.json",story_json()))
        broll=self.root/"broll.mp4"
        broll.write_bytes(b"late broll")
        self.assertEqual("REGISTERED",add_asset(self.con,"p","broll_1",
                         "BROLL",broll,"VERIFIED","2026-11-01T00:00:00Z"))
        self.assertEqual("PASS",stage_row(self.con,"p","SOURCE")["status"])
        self.assertEqual("PASS",stage_row(self.con,"p","STORY_LOCK")["status"])
        self.assertEqual("REGISTERED" if False else "IDEMPOTENT",
                         add_asset(self.con,"p","broll_1","BROLL",broll,"VERIFIED"))
        self.assertNotIn("SOURCE",audit(self.con,"p")["issues"][0])

    def test_fanout_limit_and_idempotency(self):
        body="a"*64
        self.assertEqual("REGISTERED",add_variant(self.con,"p","v1",body,"b"*64))
        self.assertEqual("IDEMPOTENT",add_variant(self.con,"p","v1",body,"b"*64))
        self.assertEqual("REGISTERED",add_variant(self.con,"p","v2",body,"c"*64))
        with self.assertRaisesRegex(GateError,"FANOUT_LIMIT_EXCEEDED"):
            add_variant(self.con,"p","v3",body,"d"*64)

    def test_immutable_asset_and_variant_identity(self):
        newer=self.write("other.mp4","another source")
        with self.assertRaisesRegex(GateError,"ASSET_ID_IMMUTABLE"):
            add_asset(self.con,"p","source","SOURCE",newer,"VERIFIED")
        add_variant(self.con,"p","v1","a"*64,"b"*64)
        with self.assertRaisesRegex(GateError,"VARIANT_ID_IMMUTABLE"):
            add_variant(self.con,"p","v1","a"*64,"c"*64)

    def test_native_qa_warning_cannot_be_forged_as_pass(self):
        video,_=self.establish_to_render()
        self.map_all(video)
        receipt=self.tech_receipt(video)
        native=self.write("native_qa.json",{
            "videoSha256":sha(video),"verdict":"PASS_WITH_WARNINGS",
            "layers":{"technical":{"status":"warn"}},
            "coverage":{"completed":["technical"],"missingRequired":[]}
        })
        receipt["qa_report_sha256"]=sha(native)
        with self.assertRaisesRegex(GateError,"TECH_QA_NATIVE_REPORT_NOT_PASS"):
            self.stage("TECH_QA",self.write("tech.json",receipt))

    def test_qa_receipt_stale_render_blocks(self):
        video,story=self.establish_to_render()
        self.map_all(video)
        with self.assertRaisesRegex(GateError,"QA_OR_REVIEW_STALE_RENDER"):
            self.stage("TECH_QA",self.write("tech.json",{
                "render_sha256":"0"*64,"status":"PASS",
                "checks":{x:"PASS" for x in ("decode","video","audio","captions")}
            }))
        self.assertEqual("FAILED",stage_row(self.con,"p","TECH_QA")["status"])

    def test_lineage_gap_blocks_delivery(self):
        video,story=self.establish_to_render()
        self.qa_to_review_only(video,story)
        with self.assertRaisesRegex(GateError,"INCOMPLETE_FRAME_LINEAGE"):
            self.stage("DELIVERY",video)

    def qa_to_review_only(self,video,story,visibility="PRIVATE_REVIEW"):
        self.stage("TECH_QA",self.write("tech.json",self.tech_receipt(video)))
        self.stage("STORY_QA",self.write("story_qa.json",{
            "render_sha256":sha(video),"story_sha256":sha(story),"status":"PASS",
            "checks":{x:"PASS" for x in ("hook_payoff","wts_causality",
                                         "beat_coverage","factual_integrity")}
        }))
        self.stage("HUMAN_REVIEW",self.write("review.json",{
            "render_sha256":sha(video),"human_approved":True,
            "reviewer":"verified reviewer","reviewed_at":"2026-11-23T12:00:00+08:00","visibility":visibility
        }))

    def test_no_human_approval_blocks(self):
        video,story=self.establish_to_render()
        self.map_all(video)
        self.stage("TECH_QA",self.write("tech.json",self.tech_receipt(video)))
        self.stage("STORY_QA",self.write("story_qa.json",{
            "render_sha256":sha(video),"story_sha256":sha(story),"status":"PASS",
            "checks":{x:"PASS" for x in ("hook_payoff","wts_causality",
                                         "beat_coverage","factual_integrity")}
        }))
        with self.assertRaisesRegex(GateError,"HUMAN_APPROVAL_NOT_RECORDED"):
            self.stage("HUMAN_REVIEW",self.write("review.json",{
                "render_sha256":sha(video),"human_approved":False,
                "reviewer":"no one","reviewed_at":None
            }))

    def test_overlap_blocks(self):
        video,_=self.establish_to_render()
        render_id="render_"+sha(video)[:20]
        add_span(self.con,"p",render_id,"first","HOOK","clip_1","PRIMARY",
                 0,200,0,5,"keep","v1")
        with self.assertRaisesRegex(GateError,"PRIMARY_FRAME_OVERLAP"):
            add_span(self.con,"p",render_id,"second","WANT","clip_1","PRIMARY",
                     200,400,4,8,"keep","v1")

    def test_selected_native_skill_cannot_be_skipped(self):
        self.stage("SOURCE",self.write("source_receipt.json",{"ok":True}))
        story=self.write("story.json",story_json())
        self.stage("STORY_LOCK",story)
        plan=self.write("plan.json",{
            "story_sha256":sha(story),
            "selected_skills":["video-edit-pipeline","reel-recut"],
            "beat_ids":["HOOK","WANT","TAPI","SO","PAYOFF"]
        })
        self.stage("EDIT_PLAN",plan)
        with self.assertRaisesRegex(GateError,"EDIT_SKILL_EXECUTION_COVERAGE_MISSING"):
            self.stage("EDIT",self.write("edit.json",{
                "plan_sha256":sha(plan),
                "beat_ids":["HOOK","WANT","TAPI","SO","PAYOFF"],
                "executed_skills":[]
            }))
        self.assertEqual("FAILED",stage_row(self.con,"p","EDIT")["status"])

    def test_trace_returns_source_and_beat_for_a_frame(self):
        video,_=self.establish_to_render()
        rid=self.map_all(video)
        value=trace_frame(self.con,"p",rid,7)
        self.assertEqual("WANT",value["source_spans"][0]["role"])
        self.assertEqual("source",value["source_spans"][0]["asset_id"])
        with self.assertRaisesRegex(GateError,"TRACE_FRAME_NOT_IN_RENDER"):
            trace_frame(self.con,"p",rid,20)

    def test_manual_recovery_requires_worker_stopped(self):
        self.con.execute("""INSERT INTO stages(project_id,stage,status)
                            VALUES(?,?,?)""",("p","SOURCE","RUNNING"))
        with self.assertRaisesRegex(GateError,"WORKER_STOP_CONFIRMATION_REQUIRED"):
            recover(self.con,"p","SOURCE",False)
        recover(self.con,"p","SOURCE",True)
        self.assertEqual("FAILED",stage_row(self.con,"p","SOURCE")["status"])

    def test_uncleared_footage_blocks_public_delivery(self):
        video,story=self.establish_to_render()
        self.map_all(video)
        self.qa_to_review_only(video,story,visibility="PUBLIC")
        with self.assertRaisesRegex(GateError,"PUBLIC_RIGHTS_NOT_CLEARED"):
            self.stage("DELIVERY",video)

    def test_skill_bridge_cli_parser(self):
        from framework.video_governance.skill_bridge import main as bridge_main
        import io
        from contextlib import redirect_stdout
        from unittest.mock import patch as patch_fn
        manifest={"skills":[{"name":"video-edit-pipeline","owner":"MASTER",
                             "status":"REGISTERED_NEEDS_SMOKE_TEST","lane":"orchestration"}]}
        with patch_fn("framework.video_governance.skill_bridge.load_manifest",
                      return_value=manifest):
            out=io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(0,bridge_main(["--registry","dummy","list"]))
        self.assertIn("video-edit-pipeline",out.getvalue())

    def test_full_pipeline_and_stale_output(self):
        video,story=self.establish_to_render()
        self.map_all(video)
        self.qa_to_release(video,story)
        with patch("framework.video_governance.engine.inspect_video",
                   return_value=(30,1,20)):
            report=audit(self.con,"p")
        self.assertEqual("PASS",report["status"],report)
        with self.assertRaisesRegex(GateError,"IMMUTABLE_STAGE_ALREADY_PASSED"):
            self.stage("DELIVERY",video)
        video.write_bytes(b"corrupted render")
        with patch("framework.video_governance.engine.inspect_video",
                   return_value=(30,1,20)):
            report=audit(self.con,"p")
        self.assertEqual("BLOCKED",report["status"])
        self.assertTrue(any("HASH" in x or "STALE" in x for x in report["issues"]))


if __name__=="__main__":
    unittest.main()
