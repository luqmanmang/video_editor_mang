# MrPaidSocial + REN/WTS — Integration and audit contract

## Physical topology
ChatGPT → Remote Desktop Commander → Windows gh codespace ssh → Codespace.
Editing native skills remain in upstream checkout, separate from the public
video_editor_mang Git repo. Existing 4 editorial skills, semantic handoff and
Remotion workflows remain untouched.

## Responsibilities
ChatGPT: creative planning, factual reasoning and manual editorial review.
MrPaidSocial: original editing/caption/audio/B-roll/QA workflow skills.
Governance: stage order, hashed immutable artifacts, exact output-frame lineage,
clip/source asset FKs, event/ingest times, fan-out bounds, duplicate protection.
Codespace: compute with private media and private SQLite state.
Windows: authorized gateway and explicit backup destination.

## Mandatory stages
SOURCE, STORY_LOCK, EDIT_PLAN, EDIT, RENDER, TECH_QA, STORY_QA,
HUMAN_REVIEW, DELIVERY. All are mandatory. No approved-skip route.
Selected optional *skills* may be N/A with reason, not whole pipeline stages.

## Error and recovery mapping
- Out-of-order invocation → BLOCKED_DEPENDENCY.
- Missing or false output → failed stage; no self-reported completion.
- Duplicate same ID/same hash → idempotent; different hash → conflict.
- Late B-roll → plan onward invalidated; source/transcript → source onward.
- Edited asset → SHA mismatch; stale source prevents new stages.
- False/stale QA → receipt must match actual render SHA.
- Too many variants → FANOUT_LIMIT_EXCEEDED.
- Overlapping primary spans → fail; missing output-frame coverage → fail delivery.
- Human review missing → block delivery.
- Concurrent same stage → transactional SQLite RUNNING reservation.
- Interrupted RUNNING → not PASS; manual recovery after checking worker stopped.
- Captions/sound/visual quality require real QA, not just receipts.
- Attribution/rights and licensing of source footage require independent clearance.

## Skill availability
All 21 original skills are registered from exact upstream files.
Registration does NOT prove live execution. Linux Codespace limitations:
iPhone Edits overlay and macOS AVFoundation tests are not portable as written;
CapCut export WIP. ElevenLabs/OpenArt/Arcads/here.now may require keys,
credits or special connectors. Never silently claim all 21 working.

## Production readiness gates
1. 21/21 registry and pinned SHA.
2. Governance negative tests pass.
3. Existing Video Studio tests unaffected.
4. Upstream setup/demo/integration tests pass on Codespace.
5. Native actual source video edited through approved WTS, inspected,
   independently QA'd, reviewed by real human and traced to each output frame.
6. Interrupted job recovery, cross-device backup and versioned release tested.
Until all six have evidence, mark STAGING not production-ready.
