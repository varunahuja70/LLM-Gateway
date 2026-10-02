# 03 - Security

Reads: `01-prd.md`, `02-architecture.md`. Security is a V1 requirement, not a later phase. Every rule here must have a test (see tickets).

## 1. What we protect

1. Provider API keys (they cost real money if stolen).
2. Gateway keys (they let someone spend the owner's money through the gateway).
3. Prompt and response content (may hold private data).
4. The owner's dashboard session.
5. Availability: one noisy or malicious client must not take the gateway down.

## 2. Actors and permissions

| Actor | Auth | Can do |
|---|---|---|
| App (project key) | `Authorization: Bearer lgw_...` | Call `/v1/*` for its own project only. Send feedback for its own requests only. Cannot read logs, stats or config. |
| Owner | Session cookie + CSRF header | Everything under `/admin/*`. |
| Anonymous | none | `GET /healthz`, `GET /admin/setup/status`, `POST /admin/auth/login`, and `POST /admin/setup` only while no owner exists. |
| Internal monitor | network-level | `GET /metrics`, only from the internal Docker network. |

A gateway key is bound to one project. A request that names another project's data gets `404`, never `403`, so IDs cannot be probed.

## 3. Authentication

**Owner login**
- Passwords hashed with Argon2id (library defaults or stronger). Minimum 12 characters, checked against a short list of common passwords.
- First-run setup creates the owner. After one owner exists, the setup endpoint returns `404`.
- Login failures: rate limit 5 attempts per 15 minutes per IP and per account (Redis). Same error message for unknown email and wrong password. Constant-time comparison. A small delay on failure.
- Session: random 256-bit token in an `httpOnly`, `Secure`, `SameSite=Lax` cookie named `__Host-session`. Only the hash of the token is stored. Idle timeout 8 hours, absolute timeout 7 days. New session on login (no session fixation). Logout deletes the row. Changing the password revokes all sessions.
- CSRF: every state-changing admin request (POST, PUT, PATCH, DELETE) must carry `X-CSRF-Token` matching the session's token, and the `Origin` header must match the configured public URL.

**Gateway keys**
- 256 bits of randomness, format `lgw_` + token. Stored as SHA-256 hash only. Lookup by hash. Prefix (first 8 chars) kept for display.
- Shown once on creation or rotation. Revoke takes effect immediately (the Redis auth cache entry is deleted on revoke; cache TTL is at most 60 seconds as a safety net).
- Optional expiry date. `last_used_at` updated at most once per minute.

## 4. Secrets handling

- Provider keys are encrypted with AES-256-GCM before saving. A random 96-bit nonce per record. The record's id is used as associated data so ciphertexts cannot be swapped between rows.
- The master key comes from the environment variable `GATEWAY_MASTER_KEY` (32 random bytes, base64). The app refuses to start without it, or if it is weak or still the example value.
- `key_version` supports rotation: `scripts/rotate_master_key.py` re-encrypts all rows with a new key.
- Provider keys are decrypted only in memory at call time, and cached in memory for a short time (60 s max). They are never logged, never returned by any API (only `key_last4`), and never put in exception messages.
- `.env` is git-ignored. `.env.example` has no real values. CI runs a secret scanner (gitleaks) on every push.
- Webhook secrets are stored encrypted the same way.

## 5. Input validation and limits

- All request bodies are validated by Pydantic models with strict types, maximum string lengths and maximum list sizes.
- Maximum request body size on the gateway: 4 MB by default (configurable), enforced before parsing. Admin: 1 MB.
- Maximum `max_tokens`, `n`, and message count per project are configurable, with safe defaults, so one bad request cannot run up a huge bill.
- Query parameters for lists have page size caps (max 200) and use cursor pagination. Sort fields come from an allow-list.
- All database access uses the ORM or bound parameters. No string-built SQL anywhere. A test greps for raw SQL strings with formatting.
- Provider response bodies are treated as untrusted: size-capped, parsed defensively, and never reflected into HTML.
- Error messages returned to apps never include internal stack traces, provider keys, or raw provider payloads. Provider error text is passed through a scrubber that removes anything that looks like a key.

## 6. Network safety (SSRF)

Two places let the owner supply a URL: `openai_compatible` provider base URL, and the project webhook URL.
- Allow only `https` (and `http` only for `localhost` when the explicit setting `ALLOW_PRIVATE_PROVIDER_URLS=true` is on, meant for local models).
- Resolve the host and **block** loopback, private (RFC 1918), link-local (including 169.254.169.254 cloud metadata), multicast and reserved ranges, for both IPv4 and IPv6, unless the allow setting is on.
- Check again at connect time (DNS rebinding), and do not follow redirects for webhooks. Provider calls follow no redirects either.
- Timeouts on every outbound call: connect 5 s, total from project config (default 60 s). Webhooks: 5 s total, response body ignored.

## 7. Transport and browser hardening

- HTTPS only in production (Caddy, automatic certificates). HSTS enabled. HTTP redirects to HTTPS.
- Security headers on the dashboard: `Content-Security-Policy` (no inline scripts, nonce-based where needed), `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`, `Permissions-Policy` locked down, `frame-ancestors 'none'`.
- CORS: closed by default on both gateway and admin. A project may add allowed origins in settings only if browser apps call the gateway directly (not recommended; the docs say keep the key server-side).
- No secrets in URLs or query strings.
- The frontend never stores tokens in local storage. It relies on the httpOnly cookie.
- Admin responses carry `Cache-Control: no-store`.

## 8. Logging and privacy

- Prompt and response bodies are **not stored by default** (`log_content = false`).
- When content logging is on, the project page shows a clear warning, and content rows follow the same retention period as logs.
- A logging filter redacts: `Authorization` headers, any string starting with `lgw_`, `sk-`, `sk-ant-`, `AIza`, cookie values, and fields named `password`, `key`, `secret`, `token`. Tests prove redaction.
- `error_message_safe` in request logs is the scrubbed text only.
- Audit trail: a small `audit_event` table records owner actions (login, key created/revoked/rotated, provider added/removed, config changed, price changed) without secret values.
- Retention: default 30 days, configurable, enforced nightly. A "delete all data for a project" admin action exists.

## 9. Rate limiting and abuse cases

| Abuse case | Defence |
|---|---|
| Stolen gateway key spams the gateway | Per-project requests-per-minute limit; budget block; owner revokes key; `last_used_at` and logs show misuse |
| Attacker guesses gateway keys | 256-bit keys; failed auth rate limited per IP (Redis); same response for unknown and revoked keys |
| Login brute force | Per-IP and per-account limits, Argon2id cost, delay on failure |
| Huge prompts or `max_tokens` to burn money | Body size cap, per-project `max_tokens` cap, budget block |
| Cache poisoning between projects | Project id is part of the cache key |
| Cache returns another user's private answer | Cache is per project and off by default; UI warns that identical requests share answers inside a project |
| Webhook used to hit internal services | SSRF rules above, no redirects, signed payloads |
| Malicious provider response (huge or malformed) | Size caps, strict parsing, timeouts |
| Slow-loris style clients | Server timeouts in Uvicorn and Caddy |
| Dependency vulnerability | Dependabot, `pip-audit` and `npm audit` in CI (fail on high severity) |
| Log injection | Structured JSON logs; user-supplied strings are escaped by the logger |
| Header injection through `X-Gateway-User` | Length cap, allow-list of characters |
| Mass assignment on admin APIs | Explicit Pydantic input models, no passing raw dicts to the ORM |

## 10. Container and deployment security

- Containers run as a non-root user, with a read-only root filesystem where possible, and no extra capabilities.
- Postgres and Redis are not exposed on public ports. Redis requires a password.
- Only Caddy publishes ports 80 and 443.
- `/metrics` and `/admin/docs` are not reachable through the public proxy.
- Base images pinned by version and rebuilt regularly. An image vulnerability scan (Trivy) runs in CI.
- Backups: documented `pg_dump` routine in `06-deployment.md`. Backups hold encrypted provider keys, so they are useless without the master key. Store the master key separately.

## 11. Required security tests

1. Gateway: missing key, malformed key, revoked key, expired key, key of another project all fail correctly.
2. Gateway key and provider key never appear in logs, errors, API responses (scan test over captured logs and responses).
3. Provider key round trip: encrypt, store, decrypt works; tampered ciphertext fails; swapping ciphertext between rows fails.
4. Login: rate limit works; session cookie flags are right; CSRF missing or wrong fails; origin mismatch fails.
5. Setup endpoint returns `404` after the first owner exists.
6. SSRF: loopback, private ranges, metadata address, IPv6 variants, decimal and hex IP forms, and redirect to private IP are all blocked.
7. Cache isolation: same request in two projects never shares an entry.
8. Budget block and rate limit cannot be bypassed by changing header case or sending concurrent requests (concurrency test).
9. Request size limit and `max_tokens` cap enforced.
10. Admin endpoints return `401` without a session, and gateway keys never work on `/admin/*`.
