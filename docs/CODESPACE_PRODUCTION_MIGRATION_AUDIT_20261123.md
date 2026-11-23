# Codespace Production Migration Audit — 2026-11-23

**Decision:** Codespace is the ONLY video processing plane. Windows is a
dashboard/transport/review endpoint and stores newly delivered MP4 outputs only.

## Actual executed evidence

- Source migration: 5 distinct real Kauthar TikTok IDs copied from the existing
  Windows research library into gitignored Codespace private runtime, roughly
  40 MiB. Original source SHA256 cross-checked against individual source
  manifests. Windows research archive was NOT deleted.
- Codespace preflight: 5/5 SHA+ASR cut-boundary checks PASS.
- Real Codespace job: run_id cs_6a106ea792b5f9f6a0
- FFmpeg render 720x1280@30 H264/AAC: 5/5 PASS.
- Full video/audio decode and objective loudness QA: 5/5 PASS.
- Source/transcript/checkpoint/log/QA/intermediates live inside
  framework/.runtime/production_runs/cs_6a106ea792b5f9f6a0/
- Only five checksum-verified MP4s copied into Windows:
  D:\Thread Automation\Video_Clipping_Studio\outputs\review\codespace_cs_6a106ea792b5f9f6a0\
- Dashboard execution 20261123_085541_12d2e99: PASS, exit 0, error 0.
- Idempotent replay 20261123_085842_1db1c44: 5/5 remote source outputs
  reused, 5/5 local MP4 files reused, exit 0; no transcoding/overwriting.
- Python regression suite: 50 tests PASS, including missing API key, pending
  B-roll semantics, wrong source hashes, no public rights, output size,
  duplicate/unsafe paths, source cut constraints and verified MP4-only delivery.
- ChatGPT manual handoff preparation: one real Kauthar input
  TikTok ID 7436261904798076178; 41 ASR segments, sampled source frames,
  immutable fingerprints. Job sem_763cc00c8aca3304ccd1. Status
  PENDING_CHATGPT (NOT a reviewed/approved semantic decision).

## Legacy cleanup (after successful migration)

- Obsolete local scratch render pipeline and asset bootstrap utilities removed.
  15 temporary items, about 45.7 MB freed (render_kauthar_batch5.py removed).
- Old ad-hoc Kauthar A/B Codespace shell renderer and A/B Remotion root
  compositions removed from active Git branch; old revisions remain in Git.
- Existing V3/V31 baseline source and previously delivered private-review MP4
  preserved for rollback; existing research library is read-only.
- Local dashboard rejects known Windows FFmpeg/video-render commands and the
  old batch renderer. Worker source and QA evidence remain in Codespace.

## Explicit NOT DONE / NOT APPROVED

- All five migrated clips are PRIVATE_REGRESSION, not ChatGPT-validated
  semantic edits. Prior ASR timings and headlines are not new expert QA.
- Semantic handoff itself creates a PENDING_CHATGPT job but still needs manual
  ChatGPT review for WTS/cuts/headline/B-roll decisions.
- Pexels/Pixabay adapters can search candidates after an API key is supplied.
  No paid service is connected and no stock candidate has been licensed,
  visually inspected or approved in this migration.
- The producer's original creator footage rights remain UNCLEARED.
- Human full-video listening, exact audio cut verification and creative
  approval are PENDING.
- Publishing, public distribution, merge-to-main and destructive deletion
  of source archives are NOT authorized by technical QA.

## User-facing checkpoint

The next real-semantic production job can start from the Codespace source
packet: semantic_7436261904798076178/runtime/jobs/
sem_763cc00c8aca3304ccd1. Use Remote Desktop Commander + GH Codespace
CLI to read packets and submit human/ChatGPT decisions. Keep everything
private; only approved review MP4s return to Windows.
