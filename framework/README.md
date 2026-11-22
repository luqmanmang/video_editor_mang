# Video Studio 3.0 — Editorial Intelligence (STAGING)
Master interface: ChatGPT session + Remote Desktop Commander; Codespace is the deterministic execution worker.
Not an autonomous LLM swarm: independent review submissions are orchestrated by ChatGPT, with explicit separate-pass evidence and a judge decision contract. Requires an external LLM runtime/API only if unattended isolated agents are later authorized.
## Order
1. Source rights + true dialogue; 2. Hook / viewer prediction / WTS / payoff; 3. independent creative challenge; 4. Story Lock; 5. Lead Editorial Director chooses A-roll first, B-roll if genuinely helpful, complex motion last; 6. render; 7. QA; 8. human preview; 9. versioned feedback.
No minimum number of cuts, B-roll, effects or motion clips. No change is a valid decision.
Use python3 framework/studio.py validate framework/projects/kauthar_v3/scene_plan.json; then npm run lint, Remotion render, ffprobe decode check.
B-roll provider keys (if available): PEXELS_API_KEY, PIXABAY_API_KEY. No keys in Git, never log them.
Commons API can verify individual CC0 footage as a separate dry-run fallback; do not scrape stock sites.
Source clips / media / outputs / actual user feedback remain outside public Git. See docs/STUDIO3_RUNBOOK.md.
