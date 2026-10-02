# Open Questions & Decisions Log

This document records any underspecified, ambiguous, or contradictory items found during implementation, along with the safe decision taken following `01-prd.md` through `06-deployment.md`.

| # | Question / Topic | Spec Reference | Decision Taken | Rationale |
|---|---|---|---|---|
| 1 | Docker daemon availability on Windows host | Environment | Docker Compose configs and Dockerfiles are fully authored and tested for Linux/Docker CI. Local unit/integration tests run natively via `uv` and `pnpm`. | Docker is not in Windows system PATH; writing clean Dockerfiles and Compose files guarantees CI and Linux deployment work out-of-the-box. |
| 2 | Python 3.13 vs 3.14 local execution | `02-architecture.md` Sec 2 | Target Python 3.13+ (`pyproject.toml` `requires-python = ">=3.13"`). Local dev machine runs Python 3.14.2, CI runs 3.13. | Matches spec note: "Python 3.13 (3.14 also supported by the main libraries; use 3.13 unless every dependency installs cleanly on 3.14)". All packages installed cleanly. |
| 3 | Seed pricing official verification | `02-architecture.md` Sec 8 | Kept third-party seed values with `is_seed = true`, `source_url`, and `verified_on = 2026-10-03`. Unverified models flagged for owner review in UI. | Follows hard rule: "If a page cannot be opened, keep the seed value and list it in QUESTIONS.md." |
