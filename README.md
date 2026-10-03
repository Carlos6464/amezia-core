<div align="center">
  <img src="apps/web/public/assets/imagens/logo.png" alt="Amezia" width="96" />

  # Amezia

  **Personal finance, on autopilot.**
  Web dashboard + WhatsApp bot + AI agent that log, understand, and explain your expenses for you.

  [![Edition](https://img.shields.io/badge/edition-public%20showcase-blueviolet)](#-about-this-repository)
  [![API](https://img.shields.io/badge/api-FastAPI%20%2B%20Python%203.12-009688)](#-tech-stack)
  [![Frontend](https://img.shields.io/badge/frontend-Angular%2019%20PWA-DD0031)](#-tech-stack)
  [![Database](https://img.shields.io/badge/database-PostgreSQL%2016%20%2B%20pgvector-336791)](#-tech-stack)
  [![License](https://img.shields.io/badge/license-all%20rights%20reserved-lightgrey)](#-license)

  [Overview](#-overview) · [Features](#-key-differentiators) · [Tech stack](#-tech-stack) · [Architecture](#-architecture) · [Getting started](#-getting-started) · [License](#-license)
</div>

---

## 📖 Overview

Tell Amezia *"spent 50 on groceries"* — by text, voice, or WhatsApp — and it categorizes, saves, and confirms the expense automatically. The AI agent knows the user's real financial history and answers with context, without ever needing to be re-explained who they are.

### 📌 About this repository

This is the **public showcase edition** of Amezia, a personal-finance platform that runs in production. It is a simplified copy of the codebase, published so the architecture and engineering decisions can be reviewed: Clean Architecture/DDD on the API, RAG over pgvector embeddings, an async job queue, and a feature-based Angular PWA. Deployment pipelines and internal documentation are intentionally not included.

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
├── screem/                  # HTML prototypes of the main screens
├── docker-compose.yml
├── turbo.json
└── package.json
```

## 🧱 Architecture

`apps/api` follows Clean Architecture, with one package per bounded context (auth, categories, transactions, conversations, reports, subscriptions, WhatsApp bot, admin, ...):

```
presentation/   →   application/   →   domain/   ←   infrastructure/
(routers, schemas)  (use cases)        (entities,     (SQLAlchemy repos, AI clients,
                                        value objects, Redis, Stripe, Evolution,
                                        ports)         security)
```

- **Routers hold no business logic.** They validate input with Pydantic and call a use case.
- **Use cases orchestrate the domain** and depend only on ports (interfaces), never on HTTP or SQLAlchemy directly.
- **Everything is async:** `AsyncSession` with `asyncpg`, plus an ARQ worker for AI calls, WhatsApp and other heavy I/O.
- **RAG with pgvector:** transactions, categories and conversation messages are embedded and indexed; the agent retrieves the most relevant context by similarity before answering.
- **Webhooks answer immediately** and push the real work to the queue; message processing is idempotent.
- **Data isolation and privacy:** every query on user data is filtered by `user_id`; sensitive fields (phone, descriptions, titles, summaries) are encrypted at rest with Fernet, and phones are indexed through a keyed HMAC.
- **Stateless auth:** short-lived JWT access tokens and a refresh token in an `HttpOnly` cookie.
- **Schema is owned by Alembic:** a single linear migration chain for the whole project.

`apps/web` follows a feature-based architecture (`core/`, `shared/`, `layout/`, `features/*`), where each feature maps 1:1 to a backend bounded context and uses standalone components with Signals.

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

Before starting, fill in the secrets in `.env`. The template documents how to generate each one (`JWT_SECRET`, `AES_ENCRYPTION_KEY`, `PHONE_HASH_SECRET`). AI, WhatsApp, e-mail and storage keys are optional for local development and enable the matching features when provided.

The Docker stack serves everything through `nginx` on `http://localhost:${NGINX_PORT:-8080}` (`/api/*` and `/ws` → API, `/*` → frontend). The default port is `8080`, not `80`, to avoid clashing with a system-level web server — override `NGINX_PORT` in `.env` if you want a different one.

## 📜 Available scripts

Root scripts fan out to every workspace via Turborepo:

| Script | Description |
|---|---|
| `pnpm build` | Build all apps/packages (`turbo run build`, cached) |
| `pnpm lint` | Lint all apps/packages (`turbo run lint`, cached) |
| `pnpm test` | Test all apps/packages (`turbo run test`, cached) |
| `pnpm dev` | Run all apps in dev mode (`turbo run dev`, not cached) |

Backend tests live in [`apps/api/tests`](./apps/api/tests) and cover auth, categories, transactions, conversations, reports, subscriptions, feedback, admin and the WhatsApp bot.

## 📈 Included modules

| # | Module | Highlights |
|---|---|---|
| 1 | Foundation | Monorepo, Docker, Nginx, Clean Architecture |
| 2 | Auth | JWT, Google OAuth2, profile language |
| 3 | Categories | Global + private categories |
| 4 | Transactions | CRUD, budget cap, installments, receipts |
| 5 | AI Agent / Chat | RAG via pgvector |
| 6 | Reports | CSV export + AI narrative |
| 7 | Admin + Evolution API | Back-office and WhatsApp instance management |
| 8 | WhatsApp bot | Five conversational states |
| 9 | Feedback | Web + bot |

Plus a guided onboarding flow (spotlight tour + first-steps checklist).

## 📜 License

Copyright © 2026 Carlos Adriano Sodré Araújo. **All rights reserved.**

The source code is published for evaluation and educational reading. It may not be copied, redistributed, or used commercially without written permission. See [`LICENSE`](./LICENSE).

---

<div align="center">
  <sub>Built with FastAPI, Angular, and a bit of pgvector magic.</sub>
  <br/>
  <sub>By <a href="https://www.linkedin.com/in/carlosadrianosodrearaujo6464">Carlos Adriano Sodré Araújo</a></sub>
</div>
