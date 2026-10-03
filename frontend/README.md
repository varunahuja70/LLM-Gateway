# LLM Gateway — Dashboard Frontend

The frontend is a modern, real-time analytics dashboard and administrative control panel for the LLM Gateway, built with **Next.js 15 (App Router)**, **React 19**, **TypeScript**, and **Tailwind CSS**.

---

## Features

- **Executive & Analytics Overview**:
  - Live KPIs: Total requests, aggregate spend (USD), p95 latency, error rates, and cache hit ratios.
  - Timeseries charts: Spend over time, request volume, and model distribution.
  - Latency breakdown: p50, p90, p95, and p99 percentiles across models.
- **Request Log Explorer**:
  - Filterable by project, model, status, and date range.
  - Inspection drawer displaying headers, tokens, costs, TTFT, and payload hashes.
- **Project & Key Management**:
  - Create and manage projects.
  - Issue and revoke scoped gateway API keys.
- **Provider Key Vault**:
  - Configure provider credentials (OpenAI, Anthropic, Google Gemini) securely encrypted at rest.
- **Budgeting & Alerts**:
  - Daily and monthly spend thresholds.
  - Webhook alert endpoints with live test delivery and HMAC verification.
- **Demo Mode**:
  - Built-in mock data mode configurable via settings to demonstrate full functionality without requiring live production traffic.

---

## Tech Stack

- **Framework**: Next.js 15 (App Router)
- **UI Library**: React 19, Tailwind CSS, Lucide React
- **Language**: TypeScript (strict mode)
- **Package Manager**: `pnpm`

---

## Getting Started

### 1. Prerequisites
- Node.js 20+
- `pnpm` (version 9+)

### 2. Environment Configuration

Create `.env.local` if custom backend host is needed:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 3. Install Dependencies

```bash
pnpm install
```

### 4. Run Development Server

```bash
pnpm dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## Quality Checks & Building

```bash
# Type check TypeScript
pnpm type-check

# Lint check
pnpm lint

# Production build
pnpm build
```
