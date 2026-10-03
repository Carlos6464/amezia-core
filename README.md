<div align="center">
  <img src="apps/web/public/assets/imagens/logo.png" alt="Amezia" width="96" />

  # Amezia

  **Personal finance, on autopilot.**
  Web dashboard + WhatsApp bot + AI agent that log, understand, and explain your expenses for you.

  [![Status](https://img.shields.io/badge/status-in%20development-orange)](#-project-status)
  [![API](https://img.shields.io/badge/api-FastAPI%20%2B%20Python%203.12-009688)](#-tech-stack)
  [![Frontend](https://img.shields.io/badge/frontend-Angular%2019%20PWA-DD0031)](#-tech-stack)
  [![Database](https://img.shields.io/badge/database-PostgreSQL%2016%20%2B%20pgvector-336791)](#-tech-stack)
  [![License](https://img.shields.io/badge/license-private-lightgrey)](#)

  [Overview](#-overview) · [Features](#-key-differentiators) · [Tech stack](#-tech-stack) · [Getting started](#-getting-started) · [Docs](#-documentation)
</div>

---

## 📖 Overview

Tell Amezia *"spent 50 on groceries"* — by text, voice, or WhatsApp — and it categorizes, saves, and confirms the expense automatically. The AI agent knows the user's real financial history and answers with context, without ever needing to be re-explained who they are.

> 📄 Full product spec: [`prd.md`](./prd.md)

## ✨ Key differentiators

| | Feature | Description |
|---|---|---|
| 💬 | **Natural language logging** | Say or type the expense — AI extracts amount, category, and date |
| 📱 | **Native WhatsApp bot** | Log and query expenses without opening the app |
| 🧠 | **AI with memory** | Agent knows the user's real history via RAG over embeddings |
| 🔀 | **Multi-provider AI** | Gemini as primary, Grok as fallback — no single point of failure |
| 🎙️ | **Voice on WhatsApp** | Log expenses via voice message, transcribed and interpreted by AI |
| 📊 | **Smart dashboard** | Monthly trend, category breakdown, weekly bars |
| 📝 | **AI-generated reports** | Narrative summary with top categories, trends, and recommendations |
| ⚡ | **PWA experience** | Installable, fast-loading, app-like — no app store |

## 🛠 Tech stack

| Layer | Technology |
|---|---|
| Monorepo | Turborepo (`apps/web`, `apps/api`, `packages/*`) |
| API | Python 3.12 + FastAPI + Uvicorn |
| Architecture | Clean Architecture + DDD |
| ORM / Migrations | SQLAlchemy async (asyncpg) + Alembic |
| Database | PostgreSQL 16 + `pgvector` (Docker) |
| Auth | JWT HS256 (python-jose) + Google OAuth2 |
| Job queue | ARQ (async) + Redis |
| WebSocket | FastAPI native |
| Frontend | Angular 19 + PrimeNG + Tailwind (PWA) + Transloco (runtime i18n) |
| AI primary / fallback | Google Gemini / Grok (xAI) |
| WhatsApp | Evolution API (self-hosted) |
| Email | Resend |
| Infra | Docker Compose + Nginx |

## 🗂 Monorepo structure

```
amezia/
├── apps/
│   ├── web/               # Angular 19 + PrimeNG + Tailwind
│   └── api/                # FastAPI + Uvicorn (Python 3.12)
├── packages/
│   ├── shared-types/       # Contracts/types shared between web and api
│   └── config/             # Shared configs (lint, tsconfig, etc.)
├── infra/
│   ├── nginx/               # nginx.conf, routing for /api, /ws, /*
│   └── docker/               # Dockerfiles for api/worker/frontend
├── docker-compose.yml
├── turbo.json
└── package.json
```

`apps/api` follows Clean Architecture (`domain/` → `application/` → `infrastructure/` → `presentation/`). `apps/web` follows a feature-based architecture (`core/`, `shared/`, `layout/`, `features/*`) where each feature maps 1:1 to a backend bounded context. Details in [`memory-bank/systemPatterns.md`](./memory-bank/systemPatterns.md).

## 🚀 Getting started

**Prerequisites:** Node.js ≥ 20, [pnpm](https://pnpm.io) 10+, [uv](https://docs.astral.sh/uv/), Docker + Docker Compose.

```bash
# copy the env template and adjust as needed
cp .env.example .env

# install workspace dependencies (apps/web + packages/*)
pnpm install

# run api/web in dev mode locally (outside Docker)
pnpm dev

# or run the full stack in Docker (postgres, redis, api, worker, frontend, nginx)
docker compose up --build
```

The Docker stack serves everything through `nginx` on `http://localhost:${NGINX_PORT:-8080}` (`/api/*` and `/ws` → API, `/*` → frontend). The default port is `8080`, not `80`, to avoid clashing with a system-level web server — override `NGINX_PORT` in `.env` if you want a different one.

## 📜 Available scripts

Root scripts fan out to every workspace via Turborepo:

| Script | Description |
|---|---|
| `pnpm build` | Build all apps/packages (`turbo run build`, cached) |
| `pnpm lint` | Lint all apps/packages (`turbo run lint`, cached) |
| `pnpm test` | Test all apps/packages (`turbo run test`, cached) |
| `pnpm dev` | Run all apps in dev mode (`turbo run dev`, not cached) |

## 📈 Project status

All 9 MVP1 modules are complete end-to-end (backend + frontend + tests + browser validation):

| # | Module | Spec | Status |
|---|---|---|---|
| 6.1 | Foundation (monorepo, Docker, Nginx, Clean Architecture) | [`build-context-00`](./build-contexts/build-context-00-foundation.md) | ✅ Done |
| 6.2 | Auth (JWT, Google OAuth2, profile language) | [`build-context-01`](./build-contexts/build-context-01-auth.md) | ✅ Done |
| 6.3 | Categories (global + private) | [`build-context-02`](./build-contexts/build-context-02-categories.md) | ✅ Done |
| 6.4 | Transactions (CRUD, budget cap, installments, receipts) | [`build-context-03`](./build-contexts/build-context-03-transactions.md) | ✅ Done |
| 6.5 | AI Agent / Chat (RAG via pgvector) | [`build-context-04`](./build-contexts/build-context-04-agent.md) | ✅ Done |
| 6.6 | Reports (CSV + AI narrative) | [`build-context-05`](./build-contexts/build-context-05-reports.md) | ✅ Done |
| 6.7 | Admin + Evolution API | [`build-context-06`](./build-contexts/build-context-06-admin-evolution.md) | ✅ Done |
| 6.8 | WhatsApp bot (5 conversational states) | [`build-context-07`](./build-contexts/build-context-07-whatsapp-bot.md) | ✅ Done |
| 6.9 | Feedback (web + bot) | [`build-context-08`](./build-contexts/build-context-08-feedback.md) | ✅ Done |

Plus a guided onboarding flow (spotlight tour + first-steps checklist) shipped outside the original 9 build-contexts.

Full module-by-module status: [`memory-bank/progress.md`](./memory-bank/progress.md).

## 📚 Documentation

| Document | Purpose |
|---|---|
| [`prd.md`](./prd.md) | Full product requirements document |
| [`memory-bank/`](./memory-bank/) | Living architecture/context docs (brief, product, system patterns, tech context, progress, active context) |
| [`build-contexts/`](./build-contexts/) | Per-module implementation specs (00–08), each with a task checklist |
| [`DIARIO.md`](./DIARIO.md) | Chronological log of technical decisions and lessons learned — written to teach, not just record: entries covering new tech/architecture include an in-depth "concepts and technologies" walkthrough (what it is, why it was chosen, how it's used in the actual code), not just a summary of what changed |
| [`GUIA_TECNICO.md`](./GUIA_TECNICO.md) | Subject-organized technical reference (architecture, infra, security, etc.) |
| [`CLAUDE.md`](./CLAUDE.md) | Project rules for AI-assisted development |

> Documentation, `prd.md`, `build-contexts/`, `memory-bank/`, and `DIARIO.md` are written in Portuguese (PT-BR) — see the language convention in `prd.md` §4.1. Source code, logs, and the database stay in English regardless.

---

<div align="center">
  <sub>Built with FastAPI, Angular, and a bit of pgvector magic.</sub>
</div>
