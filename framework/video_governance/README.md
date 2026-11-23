# Video Studio Governance — STAGING

## Architecture
ChatGPT → Remote Desktop Commander → Windows GitHub CLI → Codespace.
Original MrPaidSocial skill pack is a pinned separate checkout under
/workspaces/_video_edit_upstream/mrpaidsocial-video-editor-agent.
Keep existing Video Studio v3 editorial skills, semantic bridge and Remotion.
No upstream editing implementation is copied into our public repo.

## Mandatory state transitions
SOURCE → STORY_LOCK → EDIT_PLAN → EDIT → RENDER → TECH_QA → STORY_QA →
HUMAN_REVIEW → DELIVERY.

The command entrypoint is engine.py --db <private-db> run <project> <stage> <artifact> -- <command>.
Executable exit code zero is not success: the output must exist, match the
current input fingerprint and pass the stage-specific validation.
Every completed stage is immutable. No silent skip. If content changes, register a
new asset ID / story version and re-execute invalidated downstream stages.

## Receipts
SOURCE: registered source asset(s).
STORY_LOCK: story_map fields hook_promise, viewer_prediction, want, tapi, so,
payoff and a beats array (beat_id + story role).
EDIT_PLAN: story_sha256, selected_skills and beat_ids covering the approved story.
EDIT: JSON receipt with plan_sha256, beat_ids (all approved beats), and
executed_skills covering every non-master selected skill. Each executed_skills
entry includes name, proof_path and proof_sha256 of the real native output.
This prevents silently selecting a skill and then omitting its execution.
The master video-edit-pipeline skill is an instruction-level orchestrator, not an
executable process; it is required in EDIT_PLAN and verified via the pinned registry.
RENDER: actual FFprobe-readable video containing video + audio.
TECH_QA: render_sha256, status PASS and checks decode/video/audio/captions PASS.
STORY_QA: story_sha256, render_sha256, status PASS and checks hook_payoff,
wts_causality, beat_coverage, factual_integrity PASS (reviewer evidence required).
HUMAN_REVIEW: render_sha256, human_approved true, reviewer, reviewed_at.
DELIVERY: exact same bytes as approved render, complete PRIMARY frame coverage,
all critical story beats mapped, no overlaps/gaps.

These are strict *structure* gates; semantic truth is NOT proved by a JSON PASS.

## Compact lineage
Asset ID + SHA-256 + event_time + ingested_at + rights.
Clip FK → source asset; source milliseconds.
Beat FK → approved story version.
Render ID + SHA-256 + actual fps + frame count.
Output spans FK → render, beat, clip; source interval and output frame interval;
transform_id, transform_version and layer.
Optional individual frame evidence for QA; no row explosion for every frame.
Fan-out: bounded variants, unique body+hook pair and idempotent registration.

## Private durable state
Codespace framework/.runtime/governance.sqlite (ignored by Git).
Windows D:\Thread Automation\Video_Clipping_Studio\semantic_runtime\ for
explicit snapshot / database backups. Codespace deletion can lose raw footage
unless separately backed up. No live creator video or credentials in public Git.

## Status
All 21 upstream SKILL.md files discoverable and mapped via router.py.
Not all 21 are runnable on Linux or without external services.
Codespace adapter is manual execution through ChatGPT/RDC, NOT a native
ChatGPT installed plugin, background agent or guarantee of complete edit quality.
Follow docs/MRPAIDSOCIAL_GOVERNANCE_ADOPTION.md for limitations and gates.

## Basic verification
python3 -m unittest framework.video_governance.test_engine -v
python3 framework/video_governance/router.py --upstream /workspaces/_video_edit_upstream/mrpaidsocial-video-editor-agent --output framework/.runtime/mrpaidsocial_skills_manifest.json
python3 -m framework.video_governance.engine --db framework/.runtime/governance.sqlite init pilot_01 --story-version v1
