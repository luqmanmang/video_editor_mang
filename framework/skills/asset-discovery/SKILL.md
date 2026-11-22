# Asset Discovery & Licensing
Search local approved footage first. Then Pexels API (when key set), Pixabay API (when key set), manual Mixkit (license-specific), and optionally Wikimedia Commons CC0 for private tests.
Search by meaning of narration, not keyword alone. Rank relevance and clarity before aesthetic polish.
Any selected candidate must have source URL, creator, license, license-status VERIFIED, duration, dimensions, direct local file, SHA256 and a statement that it is illustrative not actual creator footage.
If no asset is licensed/available, return BROLL_ASSET_MISSING; do not substitute an unapproved full-screen animation automatically.
Motion catalog: RemotionUI CLI search/list; HyperFrames CLI catalog. Discover metadata without bulk installation. Install individual effect only when Lead Editorial Director gives specific justification.
Generative video/Runway/LTX: optional, explicitly requested and separately licensed; NOT dependency for minimalist pilot.
