# Video Editor Mang ? Staging Studio

ChatGPT-directed video production powered by Remote Desktop Commander -> GitHub CLI -> GitHub Codespace.

## Current state (2026-11-22)
- Repo is public. NEVER commit source creator videos, credentials, private audio, generated exports, or copyrighted stock.
- Development branch: `staging/video-studio-v2`, not production-ready.
- Codespace: `psychic-space-winner-p7gr9q5vj4gq27rq7`; Ubuntu 24.04, Node 24, ~8 GiB RAM.
- `remotion-app/`: Remotion 4.0.545, npm dependencies installed, lint and composition discovery passed.
- `motion-assets/demo/`: HyperFrames 0.9.80 scaffold, lint + Chrome runtime validation passed, with expected static-composition warning.
- `ffmpeg`: available in this running Codespace from Ubuntu package 6.1.1.
- Achieved: first 37.7-second private motion pilot, HyperFrames animated MP4 imported into Remotion, seven dialogue clips, illustrative vector B-roll, audio mix and FFmpeg loudness normalization. See docs/KAUTHAR_PREMIUM_DRYTEST_REPORT.md.
- Not yet done: transparent-alpha WebM handoff, licensed live-action stock B-roll, publication clearance, 1080p export, human full listening QA.
- See `docs/V2_IMAN_INSPIRED_PRODUCTION_ARCHITECTURE.md` for design and acceptance criteria.

## Workflow
1. Build story map: hook question/payoff, emotion, WTS beats.
2. Verify clip selection and rights. Create EDL + visual scene plan.
3. Render purpose-built motion assets in HyperFrames; save locally outside Git.
4. Compose A-roll, licensed B-roll, motion, captions and sound in Remotion.
5. Review 720p preview with audio and sampled frames before 1080x1920 final export.
6. Keep user assets outside the public Git repository, and track exact licensing/attribution.

## Useful Commands (in Codespace)
```bash
cd /workspaces/video_editor_mang/remotion-app
npm ci
npm run lint
npx remotion compositions src/index.ts

cd /workspaces/video_editor_mang/motion-assets/demo
mkdir -p "$HOME/.hf-cache-private" && chmod 700 "$HOME/.hf-cache-private"
export HYPERFRAMES_CACHE_DIR="$HOME/.hf-cache-private"
export HYPERFRAMES_NO_TELEMETRY=1 HYPERFRAMES_NO_UPDATE_CHECK=1
npm run check
```

To connect from the user's Windows PC:
```powershell
gh codespace list -R luqmanmang/video_editor_mang
gh codespace ssh -c psychic-space-winner-p7gr9q5vj4gq27rq7
```

## Limits
- Codespaces compute/storage can incur charges and stop when inactive. Do not assume it is faster than a local workstation.
- Never run HyperFrames and Remotion renders concurrently on this 8-GiB VM.
- Generated template has no actual Iman Gadzhi-style motion yet; technical CLI success is not finished editing.
- `npm install` initial audit reported 9 moderate advisories; investigate before production, do not apply breaking `npm audit fix --force` blindly.
