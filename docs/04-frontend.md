# 04 - Frontend

Reads: `01-prd.md`, `02-architecture.md`. The dashboard is a Next.js app that talks to the admin API through the same origin (Caddy routes `/admin/*` to the backend), so the session cookie works without CORS.

## 1. Design direction

Premium, minimal, calm. The reference quality bar is Linear and Vercel dashboards. Dark theme first, light theme supported. Lots of whitespace, thin borders, one accent colour, restrained motion. Numbers are the hero: large, tabular, easy to scan. No decorative gradients, no emoji icons, no stock illustrations.

## 2. Design tokens (in `src/styles/tokens.css`, used through Tailwind v4 theme variables)

| Token | Dark | Light |
|---|---|---|
| background | `#0A0A0B` | `#FFFFFF` |
| surface | `#111113` | `#FAFAFA` |
| surface-raised | `#17171A` | `#FFFFFF` |
| border | `#26262B` | `#E7E7EA` |
| text | `#EDEDEF` | `#0B0B0C` |
| text-muted | `#8B8B93` | `#6B6B73` |
| accent | `#6E6AFF` | `#4F46E5` |
| success | `#3DD68C` | `#16A34A` |
| warning | `#F5A524` | `#D97706` |
| danger | `#F5555D` | `#DC2626` |

- Font: Inter for UI, JetBrains Mono for keys, IDs and code. Load both with `next/font` (self-hosted by Next, no external requests). All numbers use `font-variant-numeric: tabular-nums`.
- Type scale: 12 / 13 / 14 / 16 / 20 / 28 / 36 px. Radius: 8 px cards, 6 px inputs, full for pills. Spacing on a 4 px grid.
- Motion: 150 ms ease-out for hover and focus, 200 ms for panels. All motion respects `prefers-reduced-motion`.
- Chart colours come from a fixed 6-colour palette that works for colour-blind users; the series are also distinguished by legend labels, never by colour alone.

## 3. Screens

1. **First-run setup** (`/setup`): create owner (email, password with strength hint). Only reachable when no owner exists.
2. **Login** (`/login`).
3. **Overview** (`/`): date range picker (24h, 7d, 30d, custom). KPI row: total spend, calls, error rate, p95 latency, cache savings. A spend-over-time chart, a calls-and-errors chart, a "top projects" list, a "top models" list, and a recent alerts strip.
4. **Projects list** (`/projects`): table with spend (period), budget bar, calls, error rate. "New project" button.
5. **Project detail** (`/projects/[id]`): tabs: **Usage** (KPIs + charts), **Requests** (filtered list), **Keys** (create, revoke, rotate, show-once dialog), **Config** (budget, thresholds, block toggle, fallback chain editor with drag to reorder, cache, rate limit, content logging with warning, webhook), **Quick start** (copy-paste snippets for curl, Python and JavaScript pointing to the gateway).
6. **Request explorer** (`/requests`): filters (project, model, provider, status, cache hit, fallback used, date range, text search by request id or user tag), cursor-paginated table, row click opens a side panel with the full detail (timings, tokens, cost, fallback story, feedback, content if stored).
7. **Models** (`/models`): comparison table (cost per 1K calls, average tokens, p50/p95 latency, TTFT, error rate, fallback rate, feedback score) with sortable columns and a small bar visual per metric.
8. **Budgets and alerts** (`/alerts`): history of alerts with status of the webhook, and a per-project budget overview.
9. **Settings** (`/settings`): Providers (add, test connection, disable), Prices (editable table, seed rows flagged "seed price - verify", import JSON), Retention, Account (change password), About (version, demo-mode badge).

## 4. Component inventory

Built on shadcn/ui primitives: Button, Input, Select, Dialog, Sheet (side panel), Tabs, Table, Badge, Tooltip, Toast, Skeleton, DropdownMenu, Switch, Calendar and DateRangePicker, Command palette (optional).
Custom: `KpiCard`, `SpendChart`, `CallsChart`, `BudgetBar` (colour changes at warning thresholds), `ModelTable`, `RequestTable`, `RequestDetailSheet`, `FallbackChainEditor`, `SecretRevealDialog` (show once, copy button, "I saved it" checkbox before close), `EmptyState`, `ErrorState`, `ConfirmDialog` (type project name to confirm destructive actions), `CodeSnippet` (copy button), `DemoBanner`.

## 5. States (every screen and component must define all four)

| State | Behaviour |
|---|---|
| Loading | Skeleton shapes that match the final layout. No spinners for page-level loads. |
| Empty | Short sentence plus the single next action (for example "Create your first project"). On a fresh install with demo mode, offer a "Load demo data" button. |
| Error | Plain message, "Try again" button, request id shown in muted text for debugging. 401 redirects to login. |
| Success | Subtle toast for saves. Never block the screen. |

Money is shown in USD with 2 decimals above $1, up to 6 decimals below, and an "estimated" tooltip. Unknown cost shows "unpriced" with a link to the price settings. Latency shows ms below 1 s and seconds above.

## 6. Responsive behaviour

Desktop first, usable down to 360 px wide. Sidebar collapses to a top bar with a menu sheet below 768 px. Tables become horizontally scrollable inside their container (page never scrolls sideways). Charts resize to the container. Touch targets at least 44 px on mobile.

## 7. Accessibility floor

- WCAG 2.2 AA colour contrast in both themes.
- Full keyboard use: visible focus ring (2 px accent), logical tab order, dialogs trap focus and return it, Escape closes sheets and dialogs.
- All icons that carry meaning have text labels or `aria-label`. Charts have a text summary and a "view as table" toggle.
- Forms: labels tied to inputs, errors linked with `aria-describedby`, errors announced politely.
- Respect `prefers-reduced-motion` and `prefers-color-scheme` (with a manual theme switch stored in a cookie).

## 8. Frontend rules

- TypeScript strict. No `any`. API types generated from the backend OpenAPI schema (`openapi-typescript`) so the two cannot drift.
- All server data goes through TanStack Query hooks in `src/lib/queries`. No fetch calls inside components.
- CSRF token read from a non-httpOnly companion cookie or the `/admin/auth/me` response and sent as `X-CSRF-Token` by the API client.
- Secrets (new keys) live only in component state while the dialog is open. Never in URL, storage or query cache.
- No third-party scripts, analytics or external fonts. The strict CSP depends on this.
- Unit tests for formatters and the fallback chain editor. One Playwright smoke test: setup, login, create project, create key, send a mock call, see it in the explorer.
