#!/usr/bin/env python3
"""Assistant-authored editorial decision from the actual Mixue 42-segment ASR.

The prose is authored by ChatGPT in this active project conversation; Python
only serializes and validates the human-in-the-loop decision. No model API.
Audio/ASR fact checking and creator rights remain separate PENDING gates.
"""
from pathlib import Path
import json
import sys
from .runner import RUN_ROOT,atomic,require,read
from framework.chatgpt_semantic.handoff import submit

VIDEO_ID="7481158062057770258"
BASE=RUN_ROOT/("semantic_"+VIDEO_ID)/"pilot_stock_v1"
JOB="sem_a34e26d4fdcf1aa172a7"
FOLDER=BASE/"runtime"/"jobs"/JOB

def decision(req):
    def beat(n,start,end,role,meaning,evidence,asset=None,headline=None):
        headline=(
           {"text":headline,"style_hint":"BOXED",
            "reason":"Source already has a baked opening title; replace with a factual question that the raw-material payoff answers. Geometry still requires render-frame QA."}
           if headline is not None else
           {"text":None,"style_hint":"NONE",
            "reason":"Source subtitles are baked; avoid redundant text overlay."})
        return {
          "beat_id":f"mixue_{n:02d}",
          "start_segment_id":f"s{start:04d}",
          "end_segment_id":f"s{end:04d}",
          "evidence_segment_ids":[f"s{k:04d}" for k in evidence],
          "story_role":role,"meaning":meaning,
          "headline":headline,
          "broll":{"asset_id":asset,
                   "reason":(
                       "Licensed, actually inspected illustrative stock of the named ingredient, not proof of any real Mixue supplier."
                       if asset else "Talking head and embedded source visuals are more truthful than unrelated stock.")},
          "motion":{"mode":"STATIC",
                    "reason":"Avoid automatic repeating zoom; retain source captions and speaker's natural expression."},
          "cut_guidance":"KEEP"
        }
    return {
       "schema_version":req["schema_version"],"job_id":req["job_id"],
       "input_fingerprint":req["input_fingerprint"],"revision":1,
       "decision_source":"CHATGPT_MANUAL",
       "review_ref":"CHATGPT_PROJECT_MIXUE_STORY_BROLL_PILOT_20261123",
       "story_map":{
         "hook_promise":"How can Mixue price drinks so cheaply and still sustain a profitable franchise system?",
         "viewer_prediction":"Low prices normally mean low margins or a loss-leader, so the audience expects the chain to struggle.",
         "want":"Mixue wants to expand while keeping its drinks and ice cream affordable for customers.",
         "tapi":"Selling cheaply seems to constrain margins and makes the expansion economics hard to understand.",
         "so":"Speaker connects procurement scale, own ingredient manufacturing, affordable franchise opening and selling supplies to franchisees.",
         "payoff":"The stated advantage comes from combining cheap products and a lower-cost franchise network supported by supply revenue.",
         "causal_reason":"Cheap selling prices provoke the question; upstream purchasing and franchise supply economics offer the answer, which returns in the closing beat.",
         "factual_limitations":"All company figures, lemon discount, number of factories, royalties, revenue and global branch ranking are unverified statements in Malaysian Whisper ASR. No actual Mixue factory footage or official claims are proven by illustrative B-roll."
       },
       "beats":[
          beat(1,1,4,"HOOK",
               "Opens on the reported large branch count and frames low selling price as the unusual growth strategy; headline asks the profit question.",
               [1,2,4],headline="MIXUE JUAL MURAH, UNTUNG DARI MANA?"),
          beat(2,5,9,"WANT",
               "Creator establishes local and China price comparisons and argues that adequate taste plus low pricing support market capture.",
               [5,7,9]),
          beat(3,10,12,"TAPI",
               "States the genuine mystery: how can such low prices work? Speaker points the explanation upstream to the supply chain.",
               [10,11,12]),
          beat(4,13,18,"SO",
               "Links purported bulk lemon purchases, cheaper procurement and manufacturing ingredients for franchisees to lower costs.",
               [13,14,15,16,17,18],asset="mixkit_yellow_lemon_3709"),
          beat(5,19,29,"TAPI",
               "Raises a new scaling obstacle: even a low-price concept must be economical for franchise owners. Discusses smaller space and setup cost.",
               [19,22,23,27,28,29]),
          beat(6,30,32,"TAPI",
               "Transitions from franchise fees to the next question: how does the business generate income if royalty contributions are low or absent?",
               [30,31,32]),
          beat(7,33,35,"SO",
               "Speaker answers that selling raw materials such as milk, coffee and boba to franchise owners generates revenue.",
               [33,34,35],asset="mixkit_coffee_42944"),
          beat(8,36,42,"PAYOFF",
               "Combines cheap consumer pricing with lower franchise setup costs, potential wider reach and claimed competitive advantage; returns to original cheap-but-viable question.",
               [36,37,38,39,40,41,42]),
       ],
       "excluded_segments":[]
    }

def main():
    require(sys.platform.startswith("linux") and
            Path("/workspaces/video_editor_mang").is_dir(),"Codespace only")
    req=read(FOLDER/"request.json")
    require(req["job_id"]==JOB and len(req["source"]["segments"])==42,
            "Mixue provenance/job mismatch")
    ids={a["asset_id"] for a in req["source"]["assets"]}
    require({"mixkit_yellow_lemon_3709","mixkit_coffee_42944"}<=ids,
            "Approved visual stock not in semantic source packet")
    response=decision(req)
    path=BASE/"chatgpt_authored_response.json"
    if path.exists():
        require(read(path)==response,
                "Manual editorial revision changed; requires new revision")
    else:atomic(path,response)
    outcome=submit(JOB,path,BASE/"runtime")
    print("GATE:chatgpt_42_segment_semantic_validation=PASS",flush=True)
    print("GATE:story_factual_claims=PENDING_INDEPENDENT_VERIFICATION",flush=True)
    print("GATE:actual_video_audio_listening=PENDING_HUMAN",flush=True)
    print(json.dumps({"job_id":JOB,"decision":outcome,"file":str(path)},
                     ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":
    try:main()
    except (ValueError,OSError,KeyError) as e:
        print("GATE:mixue_semantic_decision=FAIL",flush=True)
        print("ERROR:"+repr(e),file=sys.stderr,flush=True)
        raise SystemExit(2)
