# Studio 3.0 Implementation Runbook — Nov 22, 2026
Status: FEATURE BRANCH / PRIVATE DRY-RUN; not approved for public release.
## Invariants
- The user requests minimalist talking head: source A-roll, no headline/tags/progress cards, natural cuts; B-roll only where story meaning benefits; complex animation OFF.
- Source Kauthar includes burned-in captions. Never overlay duplicate subtitles on these shots. Face-aware subtitle repositioning needs a clean-caption source and human review, NOT possible with CSS on baked captions.
- All stock assets have verifiable source page, CC0/Pexels/Pixabay license, creator credit, SHA256. Original Kauthar footage rights remain UNKNOWN / private test only.
- Only Studio V3 new composition modified; V2 remains intact as rollback.
## Use
From repository root:
python3 -m unittest discover -s framework/tests -v
python3 framework/studio.py validate framework/projects/kauthar_v3/scene_plan.json
python3 framework/studio.py search pexels "family having dinner" --count 4
python3 framework/studio.py search pixabay "people travel" --count 4
python3 framework/studio.py catalog --output framework/.cache/remotionui.json
python3 framework/fetch_pilot_assets.py  # verify CC0 then download, no unapproved stock crawling
cd remotion-app && npm run lint
npx remotion render src/index.ts KautharMinimalV3 out/kauthar_minimal_v3.mp4 --concurrency=1
Then ffprobe and full FFmpeg decode; inspect contact sheet; listen to every dialogue cut.
## Agent workflow
ChatGPT is the chat interface; after retrieving project state from Remote Desktop:
Story contract → blind independent review submissions → Judge (max 3 rounds) → Lead Editorial Director visual decision → asset discovery → QA → human preview → optional promotion of anonymized style improvements.
The deterministic framework/studio.py implements contracts and gates, not actual isolated LLM agent API calls. Autonomous debate can be added only with proper model runtime and tests.
## Gates requiring human action
1. Rights for Kauthar original — private-only until cleared.
2. B-roll candidate visual relevance and narration timing.
3. Source burned captions cannot be repositioned. Need clean footage for newly generated caption system.
4. Pexels/Pixabay API credentials are not available in local environment as of setup inspection; adapters remain guarded.
5. RemotionUI and HyperFrames catalogs are optional. Do not install all effect packages nor add to Kauthar unless justified.
## Sources
https://remotionui.com/docs/cli
https://hyperframes.app/docs/5-packages/cli
https://www.pexels.com/api/documentation/
https://pixabay.com/api/docs/
https://commons.wikimedia.org/wiki/Commons:Machine-readable_data
