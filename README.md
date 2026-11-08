# Wildcatter Ventures — Recruiting Platform MVP

> Connecting Mumbai college students (batches 2027 & 2028) with companies via an AI-powered conversational interface.

---

## Monorepo Structure

```
.
├── apps/
│   ├── api/          # FastAPI backend — Gemini agent, Supabase JWT auth
│   ├── web/          # Next.js 14 (App Router) — Supabase auth, chat UI
│   └── mobile/       # Expo (expo-router) — mobile-identical flow
├── packages/
│   └── shared/       # TypeScript types + API client (shared by web & mobile)
├── supabase/
│   └── migrations/
│       └── 001_init.sql   # Full DB schema + RLS policies
├── turbo.json
└── pnpm-workspace.yaml
```

---

## Quick Start

### Prerequisites

| Tool         | Version |
| ------------ | ------- |
| Node.js      | ≥ 20    |
| pnpm         | ≥ 9     |
| Python       | 3.12    |
| Supabase CLI | latest  |

### 1. Install dependencies

```bash
pnpm install
```

### 2. Configure environment variables

Copy each `.env.example` to `.env.local` (web/mobile) or `.env` (api):

```bash
# API
cp apps/api/.env.example apps/api/.env

# Web
cp apps/web/.env.example apps/web/.env.local

# Mobile
cp apps/mobile/.env.example apps/mobile/.env
```

Fill in the values:

| App        | Variable                                                          | Description                                                   |
| ---------- | ----------------------------------------------------------------- | ------------------------------------------------------------- |
| api        | `SUPABASE_URL`                                                    | Your Supabase project URL                                     |
| api        | `SUPABASE_ANON_KEY`                                               | Supabase anon/public key                                      |
| api        | `SUPABASE_SERVICE_KEY`                                            | Supabase service-role key (**server-side only**)              |
| api        | `GEMINI_API_KEY`                                                  | Google AI Studio API key                                      |
| api        | `LLM_PROVIDER`                                                    | LLM provider (default: `gemini`, swappable via env)           |
| api        | `LLM_AGENT_MODEL`                                                 | Agent loop reasoning model (pinned: `gemini-2.5-flash`)       |
| api        | `LLM_FAST_MODEL`                                                  | Fast structured extraction model (pinned: `gemini-1.5-flash`) |
| api        | `EXA_API_KEY` / `TAVILY_API_KEY`                                  | Public web search provider keys (Day 3 search)                |
| web/mobile | `NEXT_PUBLIC_SUPABASE_URL` / `EXPO_PUBLIC_SUPABASE_URL`           | Same Supabase URL                                             |
| web/mobile | `NEXT_PUBLIC_SUPABASE_ANON_KEY` / `EXPO_PUBLIC_SUPABASE_ANON_KEY` | Same anon key                                                 |
| web/mobile | `NEXT_PUBLIC_API_BASE_URL` / `EXPO_PUBLIC_API_BASE_URL`           | URL of `apps/api` (e.g. `http://localhost:8000`)              |

### 3. Apply the database migration

```bash
supabase db push
# or against a local Supabase instance:
supabase start
supabase db reset
```

### 4. Run everything locally

```bash
# API (Python)
cd apps/api
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Web (in another terminal)
pnpm --filter @recruiting/web dev

# Mobile (in another terminal)
pnpm --filter @recruiting/mobile start   # then press 'i' for iOS, 'a' for Android
```

---

## Run locally (CI parity)

To run the exact checks that run in GitHub Actions CI:

### 1. API checks (FastAPI)

```bash
cd apps/api
# Lint & formatting verification
ruff check .
ruff format --check .

# Run test suite
pytest -v
```

### 2. Web & Mobile checks (Next.js & Expo)

```bash
# Build shared types
pnpm --filter @recruiting/shared build

# Linting
pnpm --filter @recruiting/web lint
pnpm exec eslint apps/mobile packages/shared

# Typecheck all packages
pnpm --filter @recruiting/shared exec tsc --noEmit
pnpm --filter @recruiting/web exec tsc --noEmit
pnpm --filter @recruiting/mobile exec tsc --noEmit

# Production web build
pnpm --filter @recruiting/web build
```

---

## Build

```bash
# Build shared types + web (turbo handles dependency order)
pnpm build

# API tests
cd apps/api && python -m pytest -v
```

---

## Deployment

### API → Docker / Railway / Render

The `apps/api/Dockerfile` is production-ready.

```bash
docker build -t recruiting-api apps/api
docker run -p 8000:8000 --env-file apps/api/.env recruiting-api
```

Health probe: `GET /health` → `{ "status": "ok" }`

For Railway/Render: set the `Start Command` to `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.

**Required Environment Variables for Railway / Render:**

- `SUPABASE_URL` — Supabase project URL
- `SUPABASE_ANON_KEY` — Supabase anon key
- `SUPABASE_SERVICE_KEY` — Supabase service-role secret key
- `GEMINI_API_KEY` — Google AI Studio API key (Gemini is default due to free-tier limits)
- `LLM_PROVIDER` — `gemini` (swappable via env)
- `LLM_AGENT_MODEL` — `gemini-2.5-flash` (pinned stable agent model)
- `LLM_FAST_MODEL` — `gemini-1.5-flash` (pinned fast extraction model)
- `EXA_API_KEY` or `TAVILY_API_KEY` — search provider key
- `TRANSCRIPTION_API_KEY` — Whisper transcription key (optional if using voice)

### Web → Vercel

`apps/web/vercel.json` is included. In Vercel project settings:

- **Framework Preset:** Next.js
- **Root Directory:** `apps/web`
- **Build Command:** `cd ../.. && pnpm --filter @recruiting/shared build && pnpm --filter @recruiting/web build`
- **Environment Variables:** `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_API_BASE_URL`

### Mobile → Expo EAS

```bash
npm install -g eas-cli
cd apps/mobile
eas build --platform all
```

---

## Architecture

```
Browser / Mobile App
        │  Supabase JWT (Bearer token)
        ▼
   apps/api  (FastAPI)
        │  verify JWT → load profile → run Gemini agent loop (≤5 turns)
        │  tool: upsert_record(table, data)  [allow-listed tables only]
        ▼
   Supabase Postgres  ←─── RLS enforces row-level ownership
        │
        └── Realtime → web & mobile receive new raw_events live
```

### Agent Roles

| Role                  | Can do via chat                        |
| --------------------- | -------------------------------------- |
| **Student**           | Update own profile, view opportunities |
| **Placement Officer** | Manage college contacts & students     |
| **Company**           | Update company profile, contacts       |
| **Recruiter**         | Query across companies and students    |

---

## Tech Stack

| Layer     | Technology                                     |
| --------- | ---------------------------------------------- |
| API       | FastAPI 0.111, Python 3.12, Uvicorn            |
| LLM       | Google Gemini 2.5 Flash (`google-genai`)       |
| Auth / DB | Supabase (Postgres + RLS + Realtime + Auth)    |
| Web       | Next.js 14, React 18, Tailwind CSS, TypeScript |
| Mobile    | Expo 51, expo-router 3.5, React Native         |
| Monorepo  | pnpm workspaces, Turborepo                     |
| Types     | `packages/shared` (`@recruiting/shared`)       |

---

## Security Notes

- `SUPABASE_SERVICE_KEY` **never** leaves the API server
- All log output passes through `SafeLogFilter` — bearer tokens and API keys are redacted
- RLS policies ensure users can only read/write their own rows
- `upsert_record` tool enforces an explicit allow-list of tables and Pydantic-validated schemas
- `batch_year` is restricted to 2027 or 2028 at the API layer
