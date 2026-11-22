"""Remote path/decision isolation tests. No network access in unit tests."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from chatgpt_semantic.desktop_bridge import check_path, get_cs, pull, push_decision

class BridgeTests(unittest.TestCase):
    def test_safe_remote_repo_path_only(self):
        value="/workspaces/video_editor_mang/framework/.runtime/studio/runtime/jobs/sem_123"
        self.assertEqual(check_path(value),value)
        for invalid in (
            "/etc/passwd",
            "/workspaces/video_editor_mang/../../etc/passwd",
            "/workspaces/video_editor_mang/x;rm",
            "/workspaces/other_repo/private",
        ):
            with self.assertRaises(ValueError):
                check_path(invalid)

    def test_codespace_name_rejects_command_injection(self):
        self.assertEqual(get_cs("psychic-space-winner-p7gr9q5vj4gq27rq7"),
                         "psychic-space-winner-p7gr9q5vj4gq27rq7")
        with self.assertRaises(ValueError):
            get_cs("bad';rm -rf /")

    def test_pull_rejects_unsafe_remote_job_without_network(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                pull("valid-codespace-name",
                     "/workspaces/video_editor_mang/framework/.runtime/../../secret",
                     Path(d))

    def test_synthetic_response_rejected_before_remote_submit(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d)
            (folder/"bridge_state.json").write_text(json.dumps({
                "codespace":"valid-codespace-name",
                "remote_job_dir":"/workspaces/video_editor_mang/framework/.runtime/x/runtime/jobs/sem_"+"a"*20,
                "input_fingerprint":"d"*64}),encoding="utf-8")
            reply=folder/"response.json"
            reply.write_text(json.dumps({
                "job_id":"sem_"+"a"*20,"input_fingerprint":"d"*64,
                "decision_source":"SYNTHETIC_TEST"}),encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"real manually authored"):
                push_decision(folder,reply)

if __name__=="__main__":unittest.main()
