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

| App        | Variable                                                          | Description                                                           |
| ---------- | ----------------------------------------------------------------- | --------------------------------------------------------------------- |
| api        | `SUPABASE_URL`                                                    | Your Supabase project URL                                             |
| api        | `SUPABASE_ANON_KEY`                                               | Supabase anon/public key                                              |
| api        | `SUPABASE_SERVICE_KEY`                                            | Supabase service-role key (**server-side only**)                      |
| api        | `GEMINI_API_KEY`                                                  | Google AI Studio API key                                              |
| api        | `LLM_PROVIDER`                                                    | LLM provider (default: `gemini`, swappable via env)                   |
| api        | `LLM_AGENT_MODEL`                                                 | Agent loop reasoning model (pinned: `gemini-3.5-flash`)               |
| api        | `LLM_FAST_MODEL`                                                  | Fast structured extraction model (pinned: `gemini-3.5-flash-lite`)    |
| api        | `EXA_API_KEY` / `TAVILY_API_KEY`                                  | Public web search provider keys (Day 3 search)                        |
| api        | `DEMO_SHOW_SAMPLE`                                                | Show sample/seed data in lake by default (default: `false`)           |
| api        | `DEMO_LOGIN_ENABLED`                                              | Enable instant demo-account logins on auth screens (default: `false`) |
| api        | `DEMO_USER_PASSWORD`                                              | Password for pre-seeded demo accounts (optional in dev, env-gated)    |
| web        | `NEXT_PUBLIC_DEMO_ENABLED`                                        | Enable /demo persona picker & 'Try the demo' button (default: `true`) |
| web/mobile | `NEXT_PUBLIC_SUPABASE_URL` / `EXPO_PUBLIC_SUPABASE_URL`           | Same Supabase URL                                                     |
| web/mobile | `NEXT_PUBLIC_SUPABASE_ANON_KEY` / `EXPO_PUBLIC_SUPABASE_ANON_KEY` | Same anon key                                                         |
| web/mobile | `NEXT_PUBLIC_API_BASE_URL` / `EXPO_PUBLIC_API_BASE_URL`           | URL of `apps/api` (e.g. `http://localhost:8000`)                      |

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
- `LLM_AGENT_MODEL` — `gemini-3.5-flash` (pinned stable agent model)
- `LLM_FAST_MODEL` — `gemini-3.5-flash-lite` (pinned fast extraction model)
- `EXA_API_KEY` or `TAVILY_API_KEY` — search provider key
- `TRANSCRIPTION_API_KEY` — Whisper transcription key (optional if using voice)

**Model Verification:**
The API performs an automated startup verification making a cheap 1-token real call per configured model (skipped in CI/tests). You can also run the pre-flight check manually:

```bash
cd apps/api
python scripts/check_models.py
```

### Admin Scripts (Contacts Data Lake)

#### 1. Ingest Real-World Contacts

Populates the shared data lake with real web data for companies in the lake (using Exa/Tavily web search and Gemini extraction). Never scrapes LinkedIn; only public search result snippets and URLs are stored. Never stores phone numbers.

- **Configurable Queries Per Company:** `INGEST_QUERIES_PER_COMPANY` (default `4` for targeted dry runs; recommend setting to `2` or `3` for wide-lake ingestion runs to conserve provider quota). Can be configured via environment variable or passed as `--queries-per-company N`.

```bash
cd apps/api

# Dry-run: simulate additions without writing to database
python scripts/ingest_contacts.py --category GCC --limit 5 --dry-run

# Wide-lake ingestion run with 2 queries per company and rate-limiting delay
python scripts/ingest_contacts.py --queries-per-company 2 --delay 1.5
```

#### 2. Purge Synthetic Seed Contacts

Deletes synthetic seed rows (`source='seed'`) and their provenance records from `contact_sources` after explicit confirmation:

```bash
cd apps/api

# Check seed row counts (dry-run)
python scripts/purge_seed.py

# Confirm and delete seed rows
python scripts/purge_seed.py --yes
```

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

## Demo Personas & Isolated Sandbox (/demo)

Web demo logins are isolated on their own dedicated page at `/demo`, keeping the primary `/login` screen clean and credential-focused with an optional secondary "Try the demo" button.

### Demo Roles Available

1. **Student (`student`)**: Aarav Sharma (SPIT Mumbai, Batch 2027) — view readiness scores, explore the Mumbai railway milestone timeline, and test mocked pre-verification.
2. **Placement Officer (`placement_officer`)**: Prof. Sunita Patil (VJTI Mumbai) — manage campus batches, toggle batch-sharing permissions, and view student scores.
3. **Company (`company`)**: Pooja Sharma (University Relations Lead) — upload hiring history CSVs, calculate company scores, and search opted-in candidates.
4. **Recruiter (`recruiter`)**: Karan Mehta (Early Careers Specialist) — search candidate profiles via AI assistant, filter by scores, and save to My List.

### Key Controls & Protections

- **Notice Banner**: _"Demo accounts use sample data. Verification is mocked. Nothing is ever sent."_
- **Role Switching**: An active demo session (`profiles.is_demo = true`) surfaces a "Switch demo role" button in all dashboard headers to sign out and return to `/demo`. Real users never see this button.
- **Environment Gating**:
  - Web: `NEXT_PUBLIC_DEMO_ENABLED` (when `false`, `/demo` renders a 404 not-found page and the login button is hidden).
  - API: `DEMO_LOGIN_ENABLED` (when `false`, returns `404 Not Found`).
- **Data Isolation**: Demo accounts search and interact exclusively with demo-flagged records (`is_demo_data = true`). Live external web searches and data ingestion are disabled for demo users.

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

---

## Future Work

Features deferred from Day 1–5 scope; listed in rough priority order.

### Identity verification

- **Real Aadhaar/PAN verification via DigiLocker / API Setu** — replace `MockVerifier` with `DigiLockerVerifier` using the DigiLocker API or the [API Setu](https://apisetu.gov.in) identity stack. This requires: (1) UIDAI AUA/KUA certification, (2) partner registration with API Setu or directly with NIC/DigiLocker, (3) DPDP compliance review, (4) a Supabase Vault or equivalent secrets store for the partner credentials. The `DigiLockerVerifier` stub in `apps/api/app/verification/verifier.py` raises `NotImplementedError` as a placeholder.

### Authentication

- **Native Google sign-in on mobile** — replace the current email/password + magic-link flow on Expo with the Expo Google Auth plugin for a smoother mobile onboarding; requires Google Cloud OAuth credentials.

### Import & parsing

- **LLM header mapping for CSV** — use `LLMProvider.generate_structured` to map non-standard column headers to known fields when the deterministic alias list fails. Only headers are sent to the LLM; cell values are never sent.
- **XLSX import** — extend the student-records and campus-hiring import pipeline to accept `.xlsx` files via openpyxl; CSV-only for now.

### Student visibility

- **Individual student discoverable toggle** — let students mark themselves discoverable independently of officer batch-sharing. The `discoverable` column already exists in `student_records`; the UI and visibility rule are Day 5+.

### Outreach

- **Interview and offer letter drafts** — extend `outreach_draft_kind` with `'interview'` and `'offer'`; add letter-generation prompts for each kind.
- **Outreach status tracking UI** — the `user_saved_contacts.status` column is already populated by migration 005; add a UI chip and agent tool to surface it.

### Recruiter

- **Recruiter dashboard polish** — dedicated home screen beyond My list (Day 3); recruiter currently uses chat + My list only.
- **Mobile dashboards** — officer, company and recruiter web dashboards on mobile; mobile currently shows chat, lists and scores from Days 1–3.
