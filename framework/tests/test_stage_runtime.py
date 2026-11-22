import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stage_runtime import step

class StageRuntimeTests(unittest.TestCase):
    def test_pass_skip_modified_input_and_output_corruption(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            source=root/"source.txt"
            source.write_text("input v1",encoding="utf-8")
            artifact=root/"result.txt"
            checkpoint=root/"checkpoint.json"
            script="from pathlib import Path; import sys; Path(sys.argv[1]).write_text(Path(sys.argv[2]).read_text())"
            cmd=[sys.executable,"-c",script,str(artifact),str(source)]
            def run():
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    result=step(checkpoint,"RENDERED",cmd,[str(source)],[str(artifact)])
                return result,output.getvalue()
            self.assertEqual(run()[0],0)
            self.assertEqual(artifact.read_text(),"input v1")
            self.assertIn("CACHE_HIT",run()[1])
            source.write_text("input v2",encoding="utf-8")
            self.assertNotIn("CACHE_HIT",run()[1])
            self.assertEqual(artifact.read_text(),"input v2")
            artifact.write_text("CORRUPT",encoding="utf-8")
            self.assertNotIn("CACHE_HIT",run()[1])
            self.assertEqual(artifact.read_text(),"input v2")
            self.assertEqual(json.loads(checkpoint.read_text())["stages"]["RENDERED"]["status"],"PASS")

    def test_failure_and_resume_without_skip(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            checkpoint=root/"checkpoint.json"
            artifact=root/"out.txt"
            fail=[sys.executable,"-c","import sys; sys.exit(4)"]
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code=step(checkpoint,"RENDERED",fail,[],[str(artifact)])
            self.assertEqual(code,4)
            self.assertEqual(json.loads(checkpoint.read_text())["stages"]["RENDERED"]["status"],"FAILED")
            ok=[sys.executable,"-c",f"from pathlib import Path; Path({str(artifact)!r}).write_text('ok')"]
            with contextlib.redirect_stdout(io.StringIO()) as printed:
                code=step(checkpoint,"RENDERED",ok,[],[str(artifact)])
            self.assertEqual(code,0)
            self.assertNotIn("CACHE_HIT",printed.getvalue())

    def test_interrupted_marked_running_is_rerun(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            checkpoint=root/"checkpoint.json"
            artifact=root/"out.txt"
            cmd=[sys.executable,"-c",f"from pathlib import Path; Path({str(artifact)!r}).write_text('recovered')"]
            checkpoint.write_text(json.dumps({"stages":{"ASSET_VERIFIED":{"status":"RUNNING"}}}))
            with contextlib.redirect_stdout(io.StringIO()) as output:
                code=step(checkpoint,"ASSET_VERIFIED",cmd,[],[str(artifact)])
            self.assertEqual(code,0)
            self.assertNotIn("CACHE_HIT",output.getvalue())
            self.assertEqual(artifact.read_text(),"recovered")

    def test_missing_input_hard_fails_without_pass(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            with contextlib.redirect_stdout(io.StringIO()) as output, contextlib.redirect_stderr(io.StringIO()):
                code=step(root/"state.json","SOURCE_REVIEW",[sys.executable,"-c","pass"],
                          [str(root/"missing.mp4")],[str(root/"out.mp4")])
            self.assertEqual(code,2)
            self.assertIn("GATE:source_integrity=FAIL",output.getvalue())

if __name__=="__main__":
    unittest.main()
