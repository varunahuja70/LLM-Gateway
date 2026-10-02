# 01 - Product Requirements (PRD)

Working name: **LLM Gateway**
Status: Draft for review
Track: Full (login, database, multiple projects). No payments.

> Rule for this document: behaviour only. No technology names here. The stack is chosen in `02-architecture.md`.

## One-liner

An open-source gateway that sits between an app and its AI model providers. It records the tokens, speed, cost and errors of every AI call, per project, and adds budget limits, automatic fallback and caching, with a dashboard to see it all.

## Problem

Developers who use AI models in several apps cannot easily answer simple questions:

- How much did each app spend this week?
- Which model is slow or failing?
- Why did the bill suddenly jump?
- What happens to my app when one provider goes down?

Today they read separate provider dashboards, write their own logging, and find out about overspending after the bill arrives.

## Target user

**Primary:** A solo developer, indie founder or small team running one or more apps that call AI model providers.

**Secondary:** Open-source contributors and engineers who want to read or extend a clean gateway codebase.

**Not for:** Large companies needing enterprise single sign-on, billing to end customers, or a hosted multi-company service. V1 is self-hosted by one owner.

## Core features (V1)

### 1. One entry point for AI calls
- The app sends its AI requests to the gateway instead of directly to the provider.
- The request format follows the common chat-completion format that most apps already use, so switching needs only a changed address and key.
- Streaming responses work the same as non-streaming ones.
- Supports at least three providers in V1 (for example OpenAI, Anthropic, Google Gemini).

### 2. Projects and keys
- The owner creates **projects** (one per app).
- Each project gets its own gateway key. Keys are shown once, can be revoked, and can be rotated.
- The owner adds provider keys once in the gateway. Apps never need to hold them. Stored provider keys are never shown again in full.

### 3. Logging of every call
For each request the gateway records: project, time, provider, model requested, model actually used, input tokens, output tokens, latency (total and time to first token for streams), cost, status, error type, whether it came from cache, and whether a fallback was used.
- Prompt and response text are **not stored by default**. The owner can switch on content logging per project.
- Old logs are removed automatically after a retention period the owner sets.

### 4. Cost calculation
- Cost is worked out from a price list per model.
- The price list ships with sensible defaults and the owner can edit it or add new models.
- Cost shown is an estimate and is labelled as such.

### 5. Budgets and alerts
- Each project can have a daily and a monthly budget.
- The owner sets warning levels (for example 50%, 80%, 100%).
- When a warning level is crossed, the owner is notified in the dashboard and by a webhook message.
- Each project chooses what happens at 100%: **only alert**, or **block new calls** until the period resets.

### 6. Model fallback
- Each project can define an ordered list of models to try.
- If the first model fails, times out or is rate limited, the gateway tries the next one automatically.
- The log shows which model finally answered and why the fallback happened.
- Each project sets a limit on how many fallbacks are allowed per request.

### 7. Caching
- When the same request arrives again, the gateway can return the saved answer without calling the provider.
- Caching is off by default and switched on per project, with a time-to-live the owner sets.
- The dashboard shows how many calls and how much money the cache saved.
- V1 matches only identical requests. Similar-meaning matching is a later feature.

### 8. Quality signals
- Quality is tracked with things the gateway can measure: error rate, fallback rate, latency percentiles, and empty or cut-off answers.
- The app can also send a simple **thumbs up / thumbs down** score for a past request. The dashboard shows score by model.

### 9. Rate limits
- Each project has a limit on requests per minute so one app cannot starve the others or run up cost by mistake.

### 10. Dashboard
Screens the owner can use:
- **Overview:** total spend, calls, error rate, average speed, savings from cache, trend over time.
- **Project page:** the same numbers for one project, plus budget progress.
- **Request explorer:** a searchable, filterable list of calls with a detail view.
- **Models:** compare models by cost, speed, errors and score.
- **Budgets and alerts:** set and view them.
- **Settings:** providers, price list, keys, retention, notification address.

### 11. Owner login
- The dashboard needs a login. V1 has one owner account created during first setup. Optional extra team members are a later feature.

### 12. Open-source packaging
- Starts with a single command on a fresh machine.
- Comes with sample data and a demo mode so a visitor can see a working dashboard without any provider key.
- Clear documentation, contribution guide and licence.

## Non-goals (V1)

- No billing or charging of end customers.
- No hosted multi-company (SaaS) version.
- No similar-meaning (semantic) cache.
- No prompt library or prompt versioning.
- No content filtering, personal-data redaction or guardrails.
- No team roles beyond the single owner.
- No image, audio or video model support. Text chat and embeddings only.

## Main user flows

**First setup**
1. Owner starts the gateway and opens the dashboard.
2. Owner creates the owner account.
3. Owner adds one or more provider keys.
4. Owner creates a project and copies its gateway key.
5. Owner changes the app to use the gateway address and key. First call appears in the dashboard within seconds.

**Normal call**
1. App sends a request with its project key.
2. Gateway checks key, rate limit and budget.
3. Gateway checks cache. If found, returns it and logs a cache hit.
4. Otherwise it calls the provider, streams the answer back, and logs the result.

**Provider failure**
1. Provider returns an error or times out.
2. Gateway moves to the next model in the project's list.
3. App still receives an answer. Log records the fallback and the reason.

**Budget crossed**
1. Spend passes a warning level.
2. Owner sees an alert in the dashboard and receives a webhook message.
3. At 100%, the project either keeps running (alert only) or new calls are refused with a clear message.

## Success criteria

- A new user goes from start to first logged call in under 10 minutes.
- The gateway adds very little delay: under 50 ms extra on a typical request, not counting the provider's own time.
- Logged tokens match the provider's reported usage on every successful call.
- Fallback works in a test where the first provider is made to fail.
- Budget block works: calls are refused after the limit and resume at the next period.
- No provider key or gateway key ever appears in logs, error messages or the dashboard.
- The project has working automated tests and a clean install guide that another developer can follow without help.

## Open questions

1. Which providers are mandatory for V1 besides the three listed?
2. Should the owner be able to add any provider that uses the common chat format (for example local or self-hosted models) in V1?
3. Is the webhook enough for alerts in V1, or is email also required?
4. Which open-source licence: MIT or Apache 2.0?
5. Final project name for the repository.
