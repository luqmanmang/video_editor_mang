# MrPaidSocial FULL visual pilot — Mixue (2026-11-23)
Status: **PRIVATE PREVIEW RENDERED / PRODUCTION RELEASE BLOCKED**.

## Why the prior Kauthar 5-video dry run wasn't accepted
The first batch executed only original reel-recut raw cut mode. No new b-roll, motion
composition, or audio mastering; master orchestrator was merely named in the plan.
This new pilot must prove the actual rendered pixels and audio.

## Scope / physical output
- Input: Kauthar video ID 7481158062057770258; original MP4 and ASR transcript
  in private Codespace folder framework/.runtime/production_assets/kauthar/.
- Source transcript: human_verbatim_verified=false. No fact verification.
- Source video publishing rights: not cleared, preview only.
- New visual assets: two Mixkit lemon video clips: 42948 and 3709; illustrative,
  not actual Mixue procurement/fact evidence.
- License pages: https://mixkit.co/free-stock-video/lemons-rotating-in-a-cluster-at-a-leisurely-pace-42948/
  and https://mixkit.co/free-stock-video/yellow-lemon-slices-in-detail-3709/.
  Source filenames/hashes are recorded in private governance SQLite.
- Native editor: original .claude/skills/reel-recut/scripts/build_reel.py.
- Motion workflow: original branded-ad-edit/index-template-starter.html and
  HyperFrames v0.9.84 HTML/GSAP render. Branded-ad-edit SKILL.md is an instruction
  workflow, not a single executable binary; the authorized work is authored
  composition following that original skill contract.
- SFX / ElevenLabs sound-design was NOT executed. Audio-only loudness normalization
  was applied via FFmpeg before HyperFrames composition. No new music bed.
- Frame-synced word karaoke captions were NOT generated; original baked
  subtitles + five new timed semantic/motion cards were used.

## Evidence
- Complete video: 43.57s / 1308 frames / 1080×1920 / 30fps.
- MP4 SHA-256:
  2f2e1e6dc4b32781686638ac503ce7a02f4bc44c1856b475f283b385fb0a7c9f
- Actual observed visual contact sheet: full_VISUAL_AUDIT.jpg,
  with frames at 2, 7, 19, 22, 28 and 38 seconds.
- Native video-qa technical layer: PASS, zero detected technical issues,
  integrated loudness -14.2 LUFS, true peak -1.2 dB.
- Native overall verdict: PASS_WITH_WARNINGS because transcript word-boundary
  QA degraded, Gemini semantic and optional frame-model verification skipped.
- Composition lint: zero errors, six structural warnings about dense/nested cards.
- Private video + reports delivered on Windows:
  D:\Thread Automation\Video_Clipping_Studio\outputs\kauthar5_full_engine_v2\01_mixue_full\
  Start at OPEN_TO_WATCH.html.

## Anti-drift controls added
- EDIT_PLAN can now declare edit_tier=FULL and must list all four real
  capabilities NEW_BROLL, MOTION_GRAPHICS, SEMANTIC_CARDS, AUDIO_MASTER.
- EDIT receipt must prove native skill artifacts, two registered verified
  b-roll assets, hashed actual composition HTML, hashed audio master,
  storyboard with >=3 cards and >=3 motion selectors present in HTML.
- TECH_QA for FULL tier requires native QA + separate creative QA evidence
  tied to the exact render SHA, including actual frame snapshots.
- Existing stage ordering, immutable receipts, upstream instruction hashing,
  output-frame/source-beat mapping and delivery block remain.
- Governance regression suite: 19/19 PASS in Windows and Codespace.
- Real strict gate negative test: TECH_QA refused a fake PASS receipt whose
  underlying native report had PASS_WITH_WARNINGS:
  TECH_QA_NATIVE_REPORT_NOT_PASS. The FAILED state was saved.

## Proven and NOT proven
- Proven: actual original recut, HyperFrames motion/visual composition,
  two inserted stock b-roll clips seen in rendered frames, audio normalized,
  source/render hashing, stage PASS/FAIL and release block.
- Not proven: exact source-output frame-level alignment (spans are EDL estimates),
  factual accuracy of narrated Mixue claims, human transcript verification,
  complete story causality, source footage distribution rights, new SFX/music,
  word-synced karaoke captions, 21/21 skills executed, throughput scaling,
  multi-skill cross-lane compatibility beyond reel-recut+branded-ad-edit.

## Why NOT scale to the other four yet?
The acceptance policy for a 5-video batch is pilot-first and fail-closed.
Full TECH_QA couldn't pass due degraded transcript/semantic coverage.
The other four require their own story maps, verified asset candidates and
real edited visual evidence. Do not silently reuse old recuts, mark a skill
selected as if executed, or claim 5/5. Current milestone is **1/5 full visual pilot**.

## Next work items (not silently completed)
1. Human-verbatim correction and word-level time alignment for Mixue.
2. Visual spot-check all cut seams and reconcile exact EDL/frame mapping
   from native .qa-manifest.json and HyperFrames clip timeline.
3. Add proof-backed caption and SFX workflow, or explicitly approve N/A.
4. Complete semantic WTS/REN/payoff review and source rights.
5. Once pilot meets agreed acceptance, process four other Kauthar videos
   independently, with same full-edit gate and individual media hashes.
6. Benchmark cost, memory and per-video wall time before production scaling.

Runbook: original private script in
D:\Thread Automation\Video_Clipping_Studio\scratch\mixue_full_edit_pilot.py
Codespace: framework/.runtime/mixue_full_edit_pilot.py.
This is a private prototype, not a general production editing script.
