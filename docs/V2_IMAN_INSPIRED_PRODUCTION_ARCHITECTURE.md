# Video Clipping Studio v2 ? Motion-First Production Architecture (STAGING)
Date: 2026-11-22
Status: DESIGN ONLY ? HyperFrames and Remotion NOT YET INSTALLED, INTEGRATION NOT TESTED.
Reference tutorial: user-provided "Pasted text.txt" ? ~39m55s Iman Gadzhi-inspired recreation tutorial, third-party analysis not Iman's official editing playbook.
Target: Clip multiple third-party, rights-cleared source videos into a coherent, well-produced 30?60s short; ChatGPT controls tools on Windows via Remote Desktop Commander.

## Root decision
REMOTION = ONE master timeline/compositor/audio/captions/final export.
HYPERFRAMES = pre-renderable, reusable motion-graphic scenes and alpha overlays.
FFMPEG + Python = ingest/probe/transcode/proxy/extract frames/audio analysis/QA/optional final mux.
REMOTE DESKTOP COMMANDER = command+filesystem bridge between ChatGPT conversation and PC.
EXISTING FASTER-WHISPER + GOLD = transcript/timestamps, selection evidence and story context.
Do not create parallel timelines or use HyperFrames and Remotion to independently encode entire finished video.
Motion sequences from HyperFrames should be written to cached local files (WebM alpha for overlays or MP4 for full-frame animated scenes), and then placed on the Remotion timeline.

## Official references verified at design time
- HyperFrames GitHub: https://github.com/heygen-com/hyperframes
- HyperFrames core skill: https://github.com/heygen-com/hyperframes/blob/main/skills/hyperframes/SKILL.md
- HyperFrames rendering: https://github.com/heygen-com/hyperframes/blob/main/docs/guides/rendering.mdx
- Remotion docs: https://www.remotion.dev/docs
- Remotion transparency: https://www.remotion.dev/docs/transparent-videos
- Remotion license: https://www.remotion.dev/docs/license/pricing
Remotion license is conditional: individuals/small organizations may use a Free License, but commercial automated video products / bigger teams can require a paid plan. Confirm use case BEFORE SaaS or volume deployment.
HyperFrames' CLI has direct skills and frame checks; optional skills loaded narrowly, not all en masse.

## Tutorial-derived key techniques
- 00:48?03:46 controlled dark lighting, red/blue practicals, rim+key, white shirt contrast; relevant when recording new A-roll, NOT possible to recreate original creator's lighting exactly.
- 03:47?06:05 A-roll rough cut, optional alternate angles every ~15?20s in the tutorial's observed example, subtle zoom/push and match-cut masking; NOT a mandatory 15s rule.
- 06:08?10:28 lower-third gradient/grid, animated typography, color transitions/glow.
- 10:33?23:16 layered parallax background, 3D-like camera moves, frosted glass cards, animated sectional titles.
- 23:41?32:25 planned vector-animation beats, separated assets/body parts, simple movements tied to words.
- 33:20?35:03 controlled texture/grain, flicker and occasional glitch transitions.
- 35:05?36:35 music bed + whoosh/ding/glitch/foley tied to animation and narrative changes.
Specific AE keyframe settings do not map 1:1 to HyperFrames/Remotion; reproduce the visible behavior with HTML/SVG/CSS/GSAP and React compositions. Avoid copying source graphics or unlicensed assets.

## Pipeline, contracts and gates
0. RIGHTS: log original URL, creator, permissible use/asset license. UNKNOWN rights = private sandbox only; no publication.
1. SOURCE INGEST: do not overwrite original MP4; ffprobe structured metadata, SHA256 and audio specs; produce proxies if needed.
2. UNDERSTAND: multilingual transcript timestamps (human corrections), scene thumbnails and candidate shot cuts; link text+speaker+visual evidence.
3. STORY LOCK: creative objective, viewer, hook question and payoff, title, emotion, optional REN, WANT/TAPI/SO causal map. Editor must not manufacture evidence or conversational continuity.
4. PAPER EDIT: select original in/out fragments with verified dialogue; create scene list, notes on what each visual proves/explains; record original quotation context.
5. VISUAL PLAN: for each beat select ONE PRIMARY visual mode: original A-roll, licensed B-roll, data/chart, animated metaphor, text emphasis, chapter card. Each graphic gets a 'why' note, visual type, asset source and motion spec.
6. B-ROLL: local original/legally licensed source, verified match to narration, shot durations; prefer meaningful rather than decorative B-roll. Never imply unrelated footage is factual evidence.
7. MOTION: generate 2?3 reusable HyperFrames assets for pilot (kinetic hook text; numbers/cards; parallax process diagram). Preview specific frames and export local WebM alpha or full-frame MP4.
8. MASTER EDIT: Remotion loads scene manifest, video clips, HyperFrames assets, audio, background music, captions; use consistent timings and easing; 1 central timeline.
9. SOUND: clean/normalize voice, duck music during speech, design restrained whooshes/dings/foley only at motivated beats; short fades at cuts.
10. PREVIEW/QA: 540p/720p preview at 30fps, controlled frame snapshots at hook/motion transition/payoff, frame-by-frame inspect alpha and cropping, watch through with sound, human revision.
11. FINAL: export portrait 1080x1920 H.264/AAC after approved preview; decode check, audio presence/sync, loudness, duration, caption readability, licensing clearance, accurate wording.
12. LEARN: editorial notes + true analytics after publishing; no claims of guaranteed virality.

## Minimal data contract
project_manifest.json -> creative, source_ids, rights, assets, target format
source_catalog.json -> source_id, immutable original_path, sha256, duration, fps, license/permission
segments.json -> segment_id, source_id, in_sec, out_sec, speaker, exact text, role, context QA
story_map.json -> hook/payoff, wants, tapi/so, emotional direction, factual limitations
scene_plan.json -> start_sec, duration, audio_line_id, base_visual, broll_asset_id, motion_asset_id, caption spec, SFX, beat role, visual-why
assets_manifest.json -> path, producer (original|licensed stock|HF generated), license, SHA256, transparency, fps, resolution
qa.json -> schema validation + per-frame screenshots + media decode + audio/caption/human gates
Cache by content hash + scene config so identical animation is not rerendered when changing clip order.

## Pilot story: two existing Kauthar videos (private only)
Story angle: "Banyak belanja, tapi kenapa tak puas?"
WANT: viewer wants money choices that support security and meaningful experience.
TAPI: consumer pleasure is transient (creator's statement) and spending without an emergency buffer is risky.
SO: distinguish money for safety (emergency reserve) from money for experiences, regained time and generosity.
Payoff: purposeful financial choices differ from chasing another possession.
No guarantee or causally proven happiness outcomes; creator study references not fact-checked.
Scene variants:
- 0?4s A-roll Kauthar "keseronokan yang sementara" + animated words "SEKEJAP" and subtle emphasis hit.
- 4?10s licensed shopping/purchase B-roll; animated looping spike/fade graph; contextual, not fake proof.
- 10?19s emergency fund footage + transparent savings card rising; text "SAFETY BUFFER" (not unsupported percentages).
- 19-24s animated glass-card bridge "SEKARANG, MACAM MANA GUNA DUIT?"
- 24?42s three alternatives: people/travel B-roll, clock/time reclaimed graphic, shared meal/gift B-roll; short purposeful motion.
- 42?55s return to Kauthar talking head with 3-card summary, brief punch-in and payoff text.
- 55?58s calm branded conclusion; SFX fade, music tail.
These are proposed edit beats; exact timing and footage must be revised against dialogue and source permissions. Existing v2 rough cut remains intact as baseline.

## Real-world constraints
- Current Windows PC: ~8GB RAM + AMD integrated GPU. Run HyperFrames and Remotion sequentially, one headless Chromium render at a time, worker/concurrency=1 first; 540/720p proxies and high-quality final only on pass.
- Both frameworks may use Chromium and ffmpeg behind the scenes; 8GB risks render stalls/OOM and software rendering on GPU. Test performance before promising scale.
- No additional cloud SaaS, paid stock or API implied by installation. Use only approved licensing and providers.
- Avoid caching full raw-video duplicates; cache short intermediates and generated graphics.
- Third-party videos are UNKNOWN rights until cleared. Private internal test only.
- No actual source assets or HyperFrames/Remotion integration installed by this document.

## Acceptance tests (priority order)
A. Remotion alone: video clip + captions + 1 B-roll + music preview end-to-end; 10?15s test.
B. HyperFrames alone: 2s kinetic typography and 3s parallax with frame snapshot / rendered alpha.
C. Handoff: import HF alpha WebM into Remotion; verify transparency in final composite and no flicker.
D. Full Kauthar private pilot: 45?60s, at least 3 meaningful B-roll inserts, 2 animation classes, 3 sound cues; WTS remains coherent; QA.
E. Stabilize: repeat render from same JSON on a new session; changes via EDL+scene_plan, never editing raw sources.
F. Production rollout only after human QC and legitimate usage-rights plan.

## Install decision deferred pending build request
- Node.js is already installed; do not install packages globally.
- Scaffold isolated Remotion project in video studio only; pin exact package versions with package-lock.
- Install HyperFrames in isolated motion project, read core skill/CLI; run 'doctor', 'check', 'snapshot', 'preview' prior to render.
- Separate build folders and outputs from existing Gold and Thread Automation pipelines.
- Record install commands and QA output in docs/INSTALL_LOG.md when actually run.

## Why this architecture
One authoritative timeline avoids duplicated trims and drifting audio between two full video editors; reusable motion assets allow better design without rebuilding the whole video; a deterministic scene manifest lets ChatGPT reliably revise across sessions and the user review visual changes directly.
