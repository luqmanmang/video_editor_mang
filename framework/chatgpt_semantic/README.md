# ChatGPT-in-the-loop Semantic Production v1.1

ChatGPT **in this conversation** makes semantic editorial decisions. Python is
a deterministic packet builder, lineage checker, validator, compiler, and
render guard. No API key, no other LLM, no autonomous ChatGPT background call.

## Code (GitHub feature branch)

- handoff.py — private request, WTS decision validation, immutable revisions.
- packet_builder.py — true transcript + clip/source documents -> deterministic
  context packets. Does NOT infer any word, dialogue, evidence or story beat.
- desktop_bridge.py — Windows pulls private context packets from Codespace,
  ChatGPT reads with Remote Desktop Commander, and the bridge pushes the authored
  response back for validation on the original Codespace media.
- timeline_compiler.py — validated semantic beats -> Remotion inputProps JSON.
- render_guard.py — preflight hash/clip/audio/B-roll checks and enforced native
  720x1280@30fps H.264/AAC + full decode/QA.
- smoke.py — synthetic-only integration smoke. Its outputs are not real speech
  or evidence of creative-quality approval.
- editorial_policy.md, source.schema.json, response.schema.json — contracts.
- remotion-app/src/Semantic720.tsx — 720p renderer, speaking-video timing,
  optional controlled zoom, spoken-text cues over B-roll in private preview.

## Private storage

- Windows: D:\Thread Automation\Video_Clipping_Studio\semantic_runtime\
- Codespace: /workspaces/video_editor_mang/framework/.runtime/<project>/
- Do not commit source media, transcript, prompts or response decisions.
- Local bridge snapshot + remote job lineage can survive closing the browser.
- Codespace stop interrupts active render; deletion loses remote data if not
  backed up. Windows bridge copy does NOT replicate full source videos.

## Canonical spec (private, verified source required)

The --spec JSON must contain:
- project_id, brief {viewer,goal,platform,language},
- video {duration_ms,source_rights},
- transcript_path pointing to transcript JSON with
  transcript_origin=HUMAN_VERIFIED or ASR_UNVERIFIED and segments:
  {segment_id,clip_id,start_ms,end_ms,text}, globally sorted.
  TEST_FIXTURE is only for projects beginning smoke_.
- clips: {clip_id,path,static_src,timeline_start_ms,source_in_ms,
  duration_ms,base_scale,captions_burned}
- optional stock_manifest path, static_root, story_plan path and sampled
  frames [{path,at_ms}].
The builder hashes source videos, transcript, stock, frame evidence and the
versioned packet builder itself. No transcript -> BLOCKED_TRANSCRIPT.

## Manual workflow (ChatGPT + Remote Desktop Commander)

Commands run on the authorized device, not inside a public GitHub issue.

1. In Codespace repo root:
   python3 -m framework.chatgpt_semantic.packet_builder --spec framework/.runtime/<project>/spec.json --out framework/.runtime/<project>/context

2. Generate job from the exact source packet (one run_id/fingerprint):
   python3 -m framework.chatgpt_semantic.handoff --runtime framework/.runtime/<project>/runtime prepare --source framework/.runtime/<project>/context/source.json

3. On Windows, pull from Codespace via Remote Desktop Commander:
   py -3 -m framework.chatgpt_semantic.desktop_bridge pull --codespace <codespace-name> --remote-job-dir /workspaces/video_editor_mang/framework/.runtime/<project>/runtime/jobs/sem_<fingerprint-prefix>

   Run from D:\Thread Automation\Video_Clipping_Studio\repo.
   Context arrives in D:\Thread Automation\Video_Clipping_Studio\semantic_runtime\jobs\<job_id>\
   Read analysis_prompt.md, request.json, local_read_index.json,
   context_packets/*.json and actual frame images (when available).

4. ChatGPT manually reasons over complete dialogue and frames, then writes a
   new response.json inside that local job folder with:
   - schema_version 1.1.0, job_id and exact input_fingerprint
   - decision_source CHATGPT_MANUAL, review_ref trace label
   - story_map: hook_promise, viewer_prediction, want, tapi, so, payoff,
     causal_reason, factual_limitations
   - ordered, fully covered semantic beats with real evidence_segment_ids,
     headline choice, broll asset ID (optional), motion (optional), cut guidance
   - excluded_segments only with explicit justified reasons.
   The template contains deliberately invalid placeholders and MUST be filled.

5. Submit local response to the original Codespace and mirror validated result:
   py -3 -m framework.chatgpt_semantic.desktop_bridge submit --local-job "<local-job-dir>" --response "<local-job-dir>\response.json"

6. In Codespace, after source lineage still matches:
   python3 -m framework.chatgpt_semantic.timeline_compiler --job-dir framework/.runtime/<project>/runtime/jobs/<job_id>

7. Only when compile says render_ready=true:
   python3 -m framework.chatgpt_semantic.render_guard --props "<path-returned-by-compiler>" --app remotion-app --out framework/.runtime/<project>/review_720.mp4

Use the local studio_dashboard.py tracked runner to launch/monitor remote stages
where possible. Existing browser tab refreshes every 2 seconds; new jobs must
not open additional dashboard tabs.

## QA & recovery behavior

- Input SHA-256 includes source JSON, policy, validator/schema, source documents,
  all referenced media, frames and context packets. Changed data => new job.
- Repeated prepare with identical fingerprint => REUSED.
- Repeated identical semantic decision revision => REUSED_VALIDATED.
- Different contents at same revision => HARD FAIL; increment revision.
- File changed after ChatGPT analysis but before submit => HARD FAIL.
- Frame geometry not measured => headline request marked PENDING and render
  blocked. No masking over embedded source headline by default.
- TRIM_SILENCE without waveform and independently reviewed boundaries =>
  render blocked. Semantic suggestions are NOT sample-accurate cuts.
- B-roll uses actual verified asset IDs and entire semantic beat. Rendering
  with B-roll requires human-verified short source captions; long captions,
  unverified ASR or missing speech cues => render blocked.
- Motion beyond already tight >110% base crop is suppressed, otherwise preview
  motion stays pending face-framing review. Never force a zoom on every sentence.
- Excluded source speech requires a separately approved cut plan; otherwise
  render blocked (do not silently drop or keep content differently than planned).
- No empty final folder is populated until publication rights + human review.
- Render guard refuses wrong bitrate-independent pixel size, source-media hash
  drift, missing audio, insufficient source duration, 1080p props, or full
  decode failures. Full encode is checked, not treated as creative approval.

## Known limitations (do not claim as DONE)

- ChatGPT invocation is manual per user prompt. This module never wakes or
  sends work to ChatGPT on its own.
- No verified Kauthar word-level transcript was found in current local studio.
  The actual Kauthar semantic pilot is BLOCKED_TRANSCRIPT until evidence exists.
- ASR_UNVERIFIED transcripts require human verification for B-roll captions;
  do not use a scene summary as actual spoken text.
- Headline pixel positions, background clutter scores, face/skin safe zones,
  source burned-in captions and true audio millisecond cut boundaries still
  require separate measured QA modules and/or human checks.
- Automatic WTS causal logic is NOT provable merely by JSON schema. ChatGPT
  and a human reviewer assess relevance and credibility separately.
- Publishing remains blocked for uncleared original creator footage.
