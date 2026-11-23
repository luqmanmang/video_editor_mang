# Video Studio v1 — Codespace execution, verified MP4-only Windows delivery

## Locked architecture

- CODESPACE processes original videos, transcripts, B-roll search and asset QA,
  scene plans, editing, FFmpeg, checkpoints, technical QA and temporary files.
- WINDOWS only runs the local dashboard and transport controller. The output
  review directory receives only verified .mp4 files from the Codespace worker.
- The original Windows research library is an existing read-only source backup,
  not a new processing destination. Do not delete originals without explicit
  backup/retention approval.
- The feature branch holds source code only. All real footage, private job plans,
  media, ASR, logs and outputs reside under gitignored framework/.runtime.
- Export gate: native maximum 720x1280 at 30fps, H264/AAC. Private only until
  human creative review and creator rights are separately approved.

## Canonical worker

Source:
  framework/production_pipeline/runner.py
  framework/production_pipeline/broll_search.py
  framework/production_pipeline/windows_dispatch.py

Codespace private runtime:
  framework/.runtime/production_assets/kauthar/<video_id>/original.mp4
  framework/.runtime/production_assets/kauthar/<video_id>/transcript.json
  framework/.runtime/production_assets/kauthar/<video_id>/source_manifest.json
  framework/.runtime/production_assets/kauthar/batch5_private.json
  framework/.runtime/production_runs/cs_<hash>/checkpoint.json
  framework/.runtime/production_runs/cs_<hash>/events.jsonl
  framework/.runtime/production_runs/cs_<hash>/qa/<job>.json
  framework/.runtime/production_runs/cs_<hash>/work/<job>/...
  framework/.runtime/production_runs/cs_<hash>/outputs/<job>.mp4
  framework/.runtime/production_runs/cs_<hash>/delivery_manifest.json

Windows delivered output ONLY:
  D:\Thread Automation\Video_Clipping_Studio\outputs\review\codespace_cs_<hash>\<job>_720p_private.mp4

## Running the migrated Kauthar regression

Bootstrap the five original MP4 + ASR + source manifest into Codespace using
the SHA-verifying one-time asset bundle. Preserve the original source archive.

Codespace:
  cd /workspaces/video_editor_mang
  python3 -m framework.production_pipeline.runner --plan framework/.runtime/production_assets/kauthar/batch5_private.json --preflight-only
  python3 -m framework.production_pipeline.runner --plan framework/.runtime/production_assets/kauthar/batch5_private.json

Windows dashboard worker (NO Windows transcoding):
  py -3 -m framework.production_pipeline.windows_dispatch --remote-plan /workspaces/video_editor_mang/framework/.runtime/production_assets/kauthar/batch5_private.json --expected-count 5

Or retry only delivery after an already-successful remote run:
  py -3 -m framework.production_pipeline.windows_dispatch --deliver-run cs_<fingerprint> --expected-count 5

The Codespace runner hashes source and transcript, validates ASR cut evidence,
applies PRIVATE_REGRESSION editorial plan, performs bounded parallel FFmpeg
encoding (max 2 concurrent renders), QA H264/AAC/full-decode/loudness and
writes an immutable delivery manifest only after the entire batch succeeds.
Its checkpoint and append-only events support deterministic retries.
No MP4 is promoted on Windows until size and SHA-256 match remote receipts.

## Story and B-roll approval

The prior Kauthar batch plan is tagged PRIVATE_REGRESSION with semantic
NOT_VERIFIED; it is only a technical migration proof, NOT a claim that AI
selected/edit every cut. New CHATGPT_VALIDATED plans require the actual
unchanged semantic handoff job with real input fingerprint and decision hash.
Semantic reasoning stays in this ChatGPT conversation via Remote Desktop Commander.
A human must approve precision cuts where speech fidelity is uncertain.

Stock provider discovery (Codespace ONLY):
  python3 -m framework.production_pipeline.broll_search --provider pexels --query "two people sitting apart after an argument" --out framework/.runtime/stock_queries/relationship_001.json

Requires user-provided PEXELS_API_KEY or PIXABAY_API_KEY in secure environment.
All candidates remain pending ChatGPT visual, relevance and license validation.
No automatic asset selection or downloading; unapproved B-roll is blocked.

## Cleanup policy

Once a Codespace run has a complete QA manifest and verified Windows delivery,
delete the obsolete LOCAL scratch/render_kauthar_batch5.py and one-time transfer
bundles/staging scripts. Keep original research footage, existing Windows review
MP4s and QA evidence until a user-approved retention/backup plan exists.
Do not delete source files from the public repo (there should be none).
Do not allow dashboard local FFmpeg/remotion render fallback.
