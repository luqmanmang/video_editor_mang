#!/usr/bin/env python3
"""Create an independently reviewable V3.1 hook variant, preserving V3 baseline.
No new footage is fabricated: 00_prediction_setup.mp4 must be extracted from
the same Kauthar source at source 00:00.02–00:14.58 (private rights only).
"""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "remotion-app" / "src"
F = ROOT / "framework" / "projects" / "kauthar_v3"

def main():
    old = (SRC / "KautharMinimalV3.tsx").read_text(encoding="utf-8")
    assert '{file:"01_hook.mp4", duration:5.92}' in old
    new = old.replace("KautharMinimalV3", "KautharMinimalV31")
    new = new.replace('{file:"01_hook.mp4", duration:5.92}',
                      '{file:"00_prediction_setup.mp4", duration:14.56}')
    new = new.replace("from:8.20", "from:16.84").replace("from:27.60", "from:36.24")
    # Source clip includes a baked upper headline. Uniform crop zoom hides it
    # while preserving face and lower subtitle; no new headline is introduced.
    old_video = """<OffthreadVideo src={staticFile("media/"+seg.file)} muted
          style={{width:"100%",height:"100%",objectFit:"cover"}}/>"""
    new_video = """<OffthreadVideo src={staticFile("media/"+seg.file)} muted
          style={{width:"100%",height:"100%",objectFit:"cover",
            ...(i===0 ? {transform:"scale(1.17)", transformOrigin:"center bottom"} : {})}}/>"""
    if old_video not in new:
        raise RuntimeError("MISSING_AROLL_RENDER_MARKER")
    new = new.replace(old_video, new_video)
    (SRC / "KautharMinimalV31.tsx").write_text(new, encoding="utf-8")
    rootpath=SRC/"Root.tsx"
    root=rootpath.read_text(encoding="utf-8")
    if 'KautharMinimalV31' not in root:
        root=root.replace('import { KautharMinimalV3 } from "./KautharMinimalV3";',
                 'import { KautharMinimalV3 } from "./KautharMinimalV3";\nimport { KautharMinimalV31 } from "./KautharMinimalV31";')
        root=root.replace("      <KautharMinimalV3 />", "      <KautharMinimalV3 />\n      <KautharMinimalV31 />")
        rootpath.write_text(root,encoding="utf-8")
    plan=json.loads((F/"scene_plan.json").read_text(encoding="utf-8"))
    plan["project_id"]="kauthar_minimal_v31_prediction_hook"
    plan["story"].update({
      "hook_promise":"What are the three less-obvious types of spending the speaker associates with happiness?",
      "viewer_prediction":"Luxury house, sports car or expensive goods may be presumed as answers",
      "want":"The viewer wants to discover three spending categories beyond status possessions",
      "tapi":"The speaker explicitly contrasts these ideas with luxury home, car and physical goods",
      "so":"The speaker outlines experiences together, buying back time and spending on others",
      "payoff":"The three categories are not simply new material possessions",
      "source_factual_limits":"Original speaker says there is a study but study is not verified; preserve speech as attribution, not empirical proof."
    })
    for i, scene in enumerate(plan["scenes"]):
        if i == 0:
            scene["duration"]=14.56
            scene["source"]="00_prediction_setup.mp4"
            scene["story_beat"]="HOOK_PREDICTION_AND_COUNTERARGUMENT"
            scene["visual_reason"]="Original speaker sets up three unexpected spending categories; baked upper headline is cropped without cutting face or source captions"
            scene["render_reframe"]={"scale":1.17,"origin":"center bottom","reason":"remove baked upper headline from original source"}
        else:
            scene["start"]=round(scene["start"]+8.64,2)
    (F/"scene_plan_31.json").write_text(json.dumps(plan,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    # A private verified plan is regenerated from the same checksum-proven selected stock.
    selected=ROOT/"framework"/".cache"/"kauthar_v3_verified.json"
    if selected.exists():
        verified=json.loads(selected.read_text(encoding="utf-8"))
        stocks={s["asset"]["file"]:s["asset"] for s in verified["scenes"] if s["type"]=="b_roll"}
        for s in plan["scenes"]:
            if s["type"]=="b_roll":
                s["asset"]=stocks[s["asset"]["file"]]
        (ROOT/"framework"/".cache"/"kauthar_v31_verified.json").write_text(
           json.dumps(plan,indent=2,ensure_ascii=False)+"\n", encoding="utf-8")
    print(json.dumps({"status":"GENERATED","new_composition":"KautharMinimalV31",
          "hook_duration_sec":14.56,"total_expected_sec":46.29,
          "story_lock":"PENDING_HUMAN","source_rights":"PRIVATE_ONLY"}))
if __name__=="__main__": main()
