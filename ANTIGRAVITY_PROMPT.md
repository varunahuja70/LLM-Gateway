# Prompt for Google Antigravity

Paste everything inside the box into Antigravity. Attach either the whole `llm-gateway` folder, or the single file `LLM-Gateway-FULL-SPEC.md`.

```
You are the lead engineer building an open-source project called LLM Gateway. It is going on my public GitHub as a flagship portfolio project, so quality matters more than speed: clean architecture, real security, real tests, and a README another developer can follow.

INPUT
I attached the complete spec. It is either the folder `llm-gateway/` (CLAUDE.md, AGENTS.md, docs/01 to 06) or one file, LLM-Gateway-FULL-SPEC.md, where each file starts with a marker line like `<!-- FILE: docs/01-prd.md -->`. If it is the single file, first split it into the real files and folders named in the markers. Then create the git repo.

SOURCE OF TRUTH
Read ALL of the spec completely before writing any code. The spec decides the stack, data model, API, folder structure, security rules and build order. If something is unclear, contradictory or impossible, do not guess silently: write the question into `QUESTIONS.md`, pick the safest option that matches the spec, and continue.

WHAT TO DO
Build the whole project by executing tickets T01 to T21 in docs/05-tickets.md, in order, without stopping to ask me between tickets. For each ticket:
1. Implement it fully (no stubs, no TODO placeholders, no fake data in real code paths).
2. Write the tests the ticket and docs/03-security.md require.
3. Run lint, type checks and tests. Fix every failure.
4. Check the ticket's "done when" condition and prove it (run the command or test).
5. Commit with the message `ticket NN: <title>`.
6. Add one line per ticket to `PROGRESS.md` (ticket, result, anything notable).

HARD RULES
- Versions: never write a dependency version from memory. Install the latest stable release with the package manager, then record the real version in docs/versions.lock.md. Follow the "verified" versus "pin at setup" notes in docs/02-architecture.md. Do not use SQLAlchemy 2.1 beta.
- Provider adapters: before coding OpenAI, Anthropic and Google adapters, open each provider's current official API reference (links in docs/02-architecture.md section 9) and follow it.
- Prices: open each official pricing page and correct backend/data/prices.seed.json. Keep source_url and verified_on. If a page cannot be opened, keep the seed value and list it in QUESTIONS.md.
- Security: every rule in docs/03-security.md is mandatory, including all 10 required tests. No secret may ever appear in logs, errors, API responses or git.
- Performance: logging and stats stay off the request path as the architecture says.
- Numbers: benchmarks and README claims must come from real measurements you run. Never invent numbers or screenshots.
- Design: the dashboard must follow docs/04-frontend.md (premium, minimal, Linear/Vercel quality, dark first, all four states on every screen, accessible).
- Do not add features, services or dependencies that are not in the spec.
- Everything must run with `docker compose up` and demo mode must work with no provider keys.

IF YOU GET STUCK
If a ticket still fails after 3 serious attempts, write the details in `BLOCKERS.md` (what failed, what you tried, the error) and move on to tickets that do not depend on it. Return to blocked tickets at the end.

FINISH
After T21, do a final verification pass and write `FINAL_REPORT.md` containing:
1. A checklist of every PRD feature with pass or fail and the evidence (test name or command).
2. A checklist of every security test with pass or fail.
3. The real benchmark numbers.
4. The result of: fresh clone, follow README only, reach a working demo dashboard.
5. Open questions, blockers, and known limitations, stated honestly.
Do not claim anything is working unless you ran it.
```

## Notes for Varun
- Ek hi baar mein poora 100% perfect nahi aayega. 21 tickets hain, isliye Antigravity ko beech mein rukna padega ya kuch fail hoga. Prompt mein `BLOCKERS.md` aur `FINAL_REPORT.md` isi liye hain: aakhir mein dekho kya pass hua, kya fail.
- Agar Antigravity beech mein ruk jaye ya context bhar jaye, nayi chat mein yeh bolo: "Read CLAUDE.md, PROGRESS.md and BLOCKERS.md, then continue from the next unfinished ticket with the same rules."
- Provider API keys (OpenAI, Anthropic, Gemini) sirf real testing ke liye chahiye. Demo aur tests mock provider se chalte hain, bina key ke.
- Seed prices third-party sites se hain. Release se pehle official pricing pages se ek baar khud verify kar lena.
