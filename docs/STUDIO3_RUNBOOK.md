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

## Verified implementation update
- Task routing and resume: python3 framework/orchestrator.py route PRODUCE ; python3 framework/orchestrator.py resume PATH_TO_PRIVATE_PROJECT_STATE_JSON. Windows private state: D:\Thread Automation\Video_Clipping_Studio\projects\kauthar_v3\project_state.json.
- Unit tests now: 11. Independent LLM reviewer API calls are NOT configured; review state machine rejects ungrounded verdicts.
- RemotionUI initialized with remotion-app/remotion-ui.json. Vendor search command fails schema parsing on atlas.lane items; use local catalog metadata and python3 framework/motion_catalog.py framework/.cache/remotionui_catalog_verified.json caption. 254 catalog entries discovered, NOT individually installed.
- Two selected Pexels clips downloaded and checksum verified on Windows and Codespace. Original Kauthar creator source rights remain unverified. Pexels/Pixabay API adapters block live API searches without credentials.
- Kauthar V3 output on Windows: outputs/kauthar_minimal_v3_720p.mp4 ; 37.653s, 720x1280 H264/AAC, full decode PASS. Burned-in source captions unchanged; illustrative stock captions need listening check.
- Critical creative correction: V3 starts mid-argument on 'Tapi keseronokan yang sementara'. V3.1 uses original 0.00-14.58s footage to establish the three-category prediction and contrast luxury goods before revealing categories. Source clip is private-only, not in public Git.
- Run technical QA: python3 framework/qa_render.py VIDEO --out-dir QA_DIR . Human creative approval remains mandatory.
