# ChatGPT Semantic Handoff v1

**Purpose:** Feed curated transcript/asset/frame facts to the current ChatGPT
conversation through Remote Desktop Commander, then accept a constrained
semantic decision returned by ChatGPT. No external model, API key, background
task, artificial autonomous-agent claim or hidden LLM call.

## Storage layout

Public code only (this GitHub repo):
- chatgpt_semantic/handoff.py — prepare, submit, inspect, deterministic DQ
- chatgpt_semantic/editorial_policy.md — versioned editorial rules and input fingerprint
- chatgpt_semantic/README.md — operator contract

Private Windows runtime OUTSIDE the public Git repo:
- D:\Thread Automation\Video_Clipping_Studio\semantic_runtime\jobs\sem_<fingerprint>\
  - request.json — immutable input (private brief, transcript, asset/frame refs)
  - lineage.json — source/policy/media SHA-256, origin paths, timestamp
  - source_dq.json — input validation results and warnings
  - analysis_prompt.md — instructions for the ChatGPT analyst
  - response_template.json — structurally valid starting response; replace dummy meaning
  - events.jsonl — append-only actions and timestamps
  - state.json — atomic latest status/pointer, not append-only
  - decisions\revision_001.json — immutable candidate returned by ChatGPT
  - decisions\revision_001_dq.json — corresponding validation report
- A sample file/user footage must never be committed into this public repo.

## Input schema (source.json, private)

Required:
- project_id: stable unique project slug
- task: EDITORIAL_PLAN
- brief: viewer, goal, platform, language (all nonempty strings)
- output: width=720, height=1280, fps=30
- video: duration_ms as integer
- segments: ordered contiguous or gapped transcript segments, each with
  segment_id, clip_id, start_ms, end_ms, text (source timestamps)
Optional:
- story: existing documented WANT/TAPI/SO, credibility limits
- assets: [{asset_id, license_status, source_url, ...}]
- media: [{path: absolute existing file path}]
- frames: [{path: absolute existing image path, at_ms: integer}]

Source frame paths and file hashes are evidence references, not a claim that
the model saw those frames. Read them through Remote Desktop Commander as needed.

## Manual ChatGPT workflow

1. An authorized local Python job creates the source.json input using recorded
   transcript segments, verified source media/frames and approved video brief.
2. Trigger:
   py -3 "D:\Thread Automation\Video_Clipping_Studio\repo\framework\chatgpt_semantic\handoff.py" prepare --source "D:\some-private-source.json"
3. Assistant uses Remote Desktop Commander to read generated analysis_prompt.md,
   request.json and actual frame files, then reasons in THIS chat.
4. Assistant writes a new response.json alongside the job based on
   response_template.json. Each beat references real segment IDs and may choose
   NONE for headline/B-roll/zoom. An omitted segment needs an explicit
   excluded_segments entry with a reason.
5. Assistant triggers:
   py -3 "D:\Thread Automation\Video_Clipping_Studio\repo\framework\chatgpt_semantic\handoff.py" submit --job-id sem_... --response "D:\...\response.json"
6. The validator verifies schema, source/media/policy hashes, evidence references,
   non-overlapping segments, exclusions, asset license, revision, idempotency.
7. Only status VALIDATED_FOR_PRIVATE_PREVIEW is output. Another execution step
   converts this validated decision to the canonical timeline.json and passes
   face-safe positioning, waveform cut and render checks (NOT implemented here).
8. When source, media, frames or policy change, prepare a NEW job. When ChatGPT
   deliberately revises a decision on the same input, increment revision by 1.

## Idempotency, RCA and edge cases

- job_id = SHA-256(version + source bytes hash + policy hash + media/frame hashes)
- Identical prepare => REUSED, no loss of decisions.
- Identical response same revision => REUSED_VALIDATED.
- Different response same revision => HARD FAIL (revision conflict).
- New response revision must be last revision + 1.
- Source, policy or evidence changed before submit => HARD FAIL (stale).
- Hallucinated asset/segment IDs, unlicensed selected B-roll, missing dialogue
  coverage and time overlap => HARD FAIL.
- Append-only events, atomic state writes, best-effort exclusive lock file.
  Interrupted writes retain old state; stale lock after process crash requires
  operator inspection rather than unsafe automatic deletion.
- User rights, full video review, face positioning, and final publication are
  NOT implied by the validator's semantic PASS.

## Progress scope

This module is a working **handoff and validation foundation**, not yet
connected to the Remotion timeline generator or the dashboard. It does not
guarantee every future ChatGPT session will automatically call the connector:
the current user must direct ChatGPT and the connector must be available.
