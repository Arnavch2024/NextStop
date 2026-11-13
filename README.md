# Wildcatter Ventures — Recruiting Platform MVP

> NextStop is a campus recruiting platform for students, placement officers, companies, and recruiters. It combines role-based dashboards and conversational workflows with student readiness scoring, campus hiring insights, and consent-aware candidate discovery.

---

## Table of Contents

- [Key Capabilities by Persona](#key-capabilities-by-persona)
- [Repository Layout](#repository-layout)
- [Tech Stack](#tech-stack)
- [Database Schema & Migrations](#database-schema--migrations)
- [Quick Start](#quick-start)
  - [Prerequisites](#prerequisites)
  - [Environment Setup](#environment-setup)
  - [Local Development](#local-development)
- [API Overview](#api-overview)
- [Subscriptions](#subscriptions)
- [Development Checks](#development-checks)
- [Seed & Demo Data Architecture](#seed--demo-data-architecture)
  - [Canonical CSV Lake](#canonical-csv-lake)
  - [Synthetic Demo Data Seeder](#synthetic-demo-data-seeder)
  - [Safe Demo Data Purge](#safe-demo-data-purge)
- [Mobile & Emulator Setup (Expo SDK 51)](#mobile--emulator-setup-expo-sdk-51)
- [Scoring Engines](#scoring-engines)
- [Security, Privacy & Consent](#security-privacy--consent)
- [Deployment](#deployment)

---

## Repository Layout

```
.
├── apps/
│   ├── api/          # FastAPI backend, agent, API routers, scoring, search, and scripts
│   ├── web/          # Next.js App Router web app, dashboards, chat, and billing routes
│   └── mobile/       # Expo / React Native application
├── packages/
│   └── shared/       # Shared TypeScript types, client SDKs, and scoring interfaces
├── supabase/
│   └── migrations/   # Ordered database schema and policy migrations
├── data/
│   └── seed/         # Canonical CSV files (colleges, companies, domains, contacts)
├── docs/             # Scoring, privacy, and project notes
├── turbo.json        # Turborepo task orchestrator
└── pnpm-workspace.yaml
```

This is a pnpm workspace. Run JavaScript commands from the repository root unless a command explicitly changes directory.

---

## Key Capabilities by Persona

The platform features role-based routing and persona-specific chat interfaces across Web and Mobile:

| Persona               | Primary Workflow                                                       | Conversational Quick Actions                                                                       | Data Privacy Boundaries                                                                                 |
| :-------------------- | :--------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------ |
| **Student**           | Resume ingestion, readiness scoring, consent management                | _"Add my resume"_, _"Calculate my score"_, audio voice mic                                         | Own profile only; explicit consent required for reference checks and discoverability.                   |
| **Placement Officer** | Student list CSV import, batch-sharing toggles, campus hiring history  | _"Import student list (CSV)"_, _"Companies to contact for BE CS/IT"_, mic                          | College-scoped records; can toggle batch sharing with companies for batches 2027/2028.                  |
| **Company**           | Candidate search, hiring cycle CSV upload, company tier score          | _"Import campus hiring file"_, _"Colleges to contact in Mumbai"_, _"Search students by CGPA"_, mic | Visibility filtered: can only view students who are **batch-shared** AND **not opted out**; no raw PII. |
| **Recruiter**         | Placement cell outreach, cross-campus talent search, outreach drafting | _"Placement officers at engineering colleges"_, mic                                                | Unsuppressed shared contact lake; outreach drafts generated with audit trail.                           |

The web app also includes a demo portal and subscription checkout/status routes. Demo login is controlled by the API's `DEMO_LOGIN_ENABLED` setting.

---

## Tech Stack

| Domain              | Technology Stack                                                                             |
| :------------------ | :------------------------------------------------------------------------------------------- |
| **Backend API**     | FastAPI 0.111, Python 3.10+, Uvicorn, Pydantic v2                                            |
| **AI / Agent**      | Google Gemini (`gemini-3.5-flash-lite`, `gemini-2.5-flash`) via `google-genai`               |
| **Voice / Audio**   | Groq Whisper (`whisper-large-v3-turbo`) for multi-lingual Indian English audio transcription |
| **Database & Auth** | Supabase Postgres with Row Level Security (RLS), Realtime replication, and GoTrue Auth       |
| **Web Frontend**    | Next.js 14, React 18, Tailwind CSS, Lucide Icons, TypeScript                                 |
| **Mobile App**      | Expo SDK 51, React Native 0.74, `expo-router` v3, `expo-av`                                  |
| **Monorepo**        | pnpm workspaces, Turborepo, Husky pre-commit hooks, Ruff (lint/format)                       |

---

## Database Schema & Migrations

Database changes are tracked in `supabase/migrations/` and should be applied in numeric order:

- `001_init.sql`: Core tables (`profiles`, `colleges`, `companies`, `contacts`, `students`, `raw_events`, `agent_runs`).
- `002_student_slice.sql`: Student portfolio tables (`education`, `internships`, `jobs`, `skills`, `documents`, `score_events`) and private Storage bucket.
- `003_search_slice.sql` & `004_day3_security.sql`: Shared lake with provenance tracking (`contact_sources`, `search_cache`, `user_saved_contacts`, `outreach_drafts`, contact suppression).
- `005_day4_roles.sql`: Day 4 schema additions (`student_records`, `campus_hiring`, `batch_sharing`, `is_demo` flag).
- `006_college_domains.sql`: College domain registry (`college_domains`) with sub-domain root extraction and freemail filtering.
- `007_profiles_guard.sql`: Profiles integrity security triggers.
- `008_google_oauth_onboarding_guard.sql`: Google OAuth onboarding redirect and role guards.
- `009_day5_consent.sql`: Day 5 student reference consent (`reference_authorizations`) and document pre-verification triggers (`guard_document_verification`).
- `010_subscriptions.sql`: Subscription and billing state schema.

For local Supabase development, start the stack with the Supabase CLI and apply migrations with `supabase db reset`. For a hosted project, review and apply the migrations using your normal migration workflow. The API checks the expected schema during startup.

---

## Quick Start

### Prerequisites

| Tool             | Version Requirement                                  |
| :--------------- | :--------------------------------------------------- |
| **Node.js**      | `>= 20.0.0`                                          |
| **pnpm**         | `>= 9.0.0`                                           |
| **Python**       | `>= 3.10`                                            |
| **Supabase CLI** | Latest (for local database development / migrations) |

### Environment Setup

Create local environment files from the committed examples:

```bash
# PowerShell
Copy-Item apps/api/.env.example apps/api/.env
Copy-Item apps/web/.env.example apps/web/.env.local
Copy-Item apps/mobile/.env.example apps/mobile/.env

# macOS / Linux
cp apps/api/.env.example apps/api/.env
cp apps/web/.env.example apps/web/.env.local
cp apps/mobile/.env.example apps/mobile/.env
```

Fill in your own Supabase and provider credentials. Example files use placeholders; do not commit real credentials. The API needs a Supabase service-role key, which must remain server-side and must never be exposed to web or mobile clients.

Key environment configuration variables:

| Variable                                                    | Target        | Purpose                                                                                                     |
| :---------------------------------------------------------- | :------------ | :---------------------------------------------------------------------------------------------------------- |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY`                         | API           | Supabase project URL and public anon key.                                                                   |
| `SUPABASE_SERVICE_KEY`                                      | API only      | Server-side service-role key; never expose to clients.                                                      |
| `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Web           | Supabase client configuration.                                                                              |
| `NEXT_PUBLIC_API_BASE_URL`                                  | Web           | API origin, usually `http://localhost:8000`.                                                                |
| `NEXT_PUBLIC_DEMO_ENABLED`                                  | Web           | Enables the demo entry point in the UI.                                                                     |
| `EXPO_PUBLIC_SUPABASE_URL`, `EXPO_PUBLIC_SUPABASE_ANON_KEY` | Mobile        | Supabase client configuration.                                                                              |
| `EXPO_PUBLIC_API_BASE_URL`                                  | Mobile        | API origin; use `http://10.0.2.2:8000` on Android Emulator or a reachable LAN address on a physical device. |
| `GEMINI_API_KEY` (or `GOOGLE_API_KEY`)                      | API           | Gemini model access.                                                                                        |
| `LLM_PROVIDER`, `LLM_AGENT_MODEL`, `LLM_FAST_MODEL`         | API           | Agent provider and model selection.                                                                         |
| `TRANSCRIPTION_API_KEY`, `TRANSCRIPTION_PROVIDER`           | API           | Voice transcription provider configuration.                                                                 |
| `EXA_API_KEY`, `TAVILY_API_KEY`, `JINA_API_KEY`             | API, optional | Search and web-fetch integrations.                                                                          |
| `DEMO_LOGIN_ENABLED`, `DEMO_USER_PASSWORD`                  | API           | Demo authentication controls; demo login is disabled by default.                                            |

See each `.env.example` for additional server, CORS, search, transcription, and demo settings. The API reads `apps/api/.env`; Next.js reads `apps/web/.env.local`; Expo reads `apps/mobile/.env`.

### Local Development

```bash
# 1. Install JS dependencies
pnpm install

# 2. Setup Python Virtual Environment
cd apps/api
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt

# 3. Run FastAPI Backend
uvicorn app.main:app --reload --port 8000
```

In separate terminals:

```bash
# Run Next.js Web App
pnpm --filter @recruiting/web dev

# Run Expo Mobile App
pnpm --filter @recruiting/mobile start
```

## Development Checks

```bash
# Run backend pytest suite
cd apps/api
pytest -v

# Run type checks and linters across monorepo
pnpm --filter @recruiting/shared build
pnpm --filter @recruiting/web exec tsc --noEmit
pnpm --filter @recruiting/mobile exec tsc --noEmit
ruff check .
ruff format --check .
```

## API Overview

The FastAPI service exposes interactive OpenAPI documentation at `http://localhost:8000/docs` and a health endpoint at `http://localhost:8000/health`. Main route groups include `/v1/chat`, `/v1/students`, `/v1/student-records`, `/v1/campus-hiring`, `/v1/contacts`, `/v1/outreach`, `/v1/colleges`, `/v1/companies`, `/v1/voice/transcribe`, and `/v1/auth` (demo authentication when enabled). Authenticated endpoints expect a Supabase access token as a bearer token. The running API's OpenAPI page documents request and response schemas.

## Subscriptions

The web app includes Stripe checkout, status, activation, and webhook routes. Configure `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `SUPABASE_SERVICE_ROLE_KEY`, and `NEXT_PUBLIC_APP_URL` in `apps/web/.env.local`, apply `010_subscriptions.sql`, and configure Stripe to send events to `/api/stripe/webhook`. Keep Stripe secret keys out of `NEXT_PUBLIC_*` variables.

See [CONTRIBUTING.md](CONTRIBUTING.md) for local hooks, branch naming, and contribution guidance. CI workflows are in `.github/workflows/`.

---

## Seed & Demo Data Architecture

The project includes an idempotent data seeding and isolation system.

### Canonical CSV Lake

Located in `data/seed/`:

- `colleges.csv`: 40+ Mumbai universities and engineering institutes.
- `companies.csv`: Categorized recruiters (GCC, Tier 1 Investment Banks, Tech Enterprises, Startups).
- `college_domains.csv`: Verified institutional domain roots mapped to college UUIDs.
- `contacts.csv`: Sample placement coordinators and recruiters with synthetic provenance.

To ingest or update the canonical CSV data:

```powershell
cd apps/api
python scripts/seed_csv_data.py
```

_Matches rows by normalized natural key; reports added, matched, and skipped counts without creating duplicates._

### Synthetic Demo Data Seeder

Populates clean, realistic, synthetic data flagged with `is_demo_data=true`:

- **60 Student Records** for Demo Officer (`University of Mumbai`): Batches 2027 & 2028 across 5 engineering branches, varied CGPA (6.5 to 9.8) and percentages, statuses (`in_college`, `internship`, `full_time`, `not_placed`). **Strictly zero real PII (no personal emails, phones, Aadhaar, or documents)**.
- **15 Student Records** for Second College (`JBIMS`): MBA Finance candidates including top-tier profiles (CGPA > 9.0) for recruiter filtering.
- **Batch Sharing Rules**: Batch 2027 shared with recruiters; batch 2028 private; selective opt-outs for visibility testing.
- **Campus Hiring Cycles**: Demo company (`JP Morgan Chase Global Technology`) drives across 3 cycles (2024–2026) testing all score bands (0-offer deduction, 5–9 offer band, and >20 offer bonus).
- **Synthetic Internships & Jobs**: Populated for campus readiness scoring.
- **Sample Placement Officers**: Generic college placement cell contacts.

```powershell
cd apps/api
python scripts/seed_demo_data.py
```

### Safe Demo Data Purge

Deletes **only** rows flagged as demo data (`is_demo_data=true` or created by demo profiles). Never touches manually imported or real user data:

```powershell
cd apps/api

# 1. Preview scan (dry run, deletes nothing):
python scripts/purge_demo_data.py

# 2. Confirm and purge demo rows:
python scripts/purge_demo_data.py --yes
```

---

## Mobile & Emulator Setup (Expo SDK 51)

The mobile client runs on **Expo SDK 51** with React Native 0.74:

1. **Android Emulator Networking**:
   - The Android Emulator routes host machine `localhost` via IP `10.0.2.2`.
   - `apps/mobile/lib/supabase.ts` automatically maps `localhost` to `10.0.2.2` when running inside the Android environment.
   - Set `EXPO_PUBLIC_API_BASE_URL=http://10.0.2.2:8000` in `apps/mobile/.env`.
2. **Cleartext Traffic**:
   - Enabled in `apps/mobile/app.json` (`"usesCleartextTraffic": true`) to permit local HTTP development calls to FastAPI.
3. **CORS Allowlist**:
   - `apps/api/app/config.py` allows all `localhost`, `10.0.2.2`, and local LAN IP ranges (`192.168.*.*`) automatically.
4. **EAS Cloud Builds**:
   - `apps/mobile/eas.json` is configured for APK builds under the `preview` profile:
     ```bash
     cd apps/mobile
     eas build --platform android --profile preview
     ```

---

## Scoring Engines

The platform computes three deterministic scores (0–100) adhering strictly to `docs/scoring.md`:

1. **Student Readiness Score (`app/scoring/engine.py`)**:
   - Base 50 points.
   - Education bonuses (CGPA > 8.0 or > 85% in 10th/12th/Degree).
   - Verified internships and full-time experience duration bonuses.
   - Pre-verified ID and authorized reference check boosts.
2. **Campus Score & Campus Internship Score (`app/scoring/campus_score.py`)**:
   - Grouped by hiring cycle year and company category:
     - Tier 1 (Investment Banks, Institutional Investors, Global Fortune 500): +3 pts for >5 offers.
     - Tier 2 (GCCs, Global Enterprises): +2 pts for >5 offers.
     - Tier 3 (Domestic, Startups, SMEs): +1 pt for >5 offers.
3. **Company Score (`app/scoring/company_score.py`)**:
   - Base 50 points.
   - Evaluates campus drives by cycle and offers made:
     - 0 offers: `-1 pt` (deduction)
     - 1–4 offers: `0 pts`
     - 5–9 offers: `+1 pt`
     - 10–20 offers: `+2 pts`
     - `> 20` offers: `+3 pts`

---

## Security, Privacy & Consent

- **Document Verification Guard (`009_day5_consent.sql`)**: Postgres trigger `guard_document_verification` prevents clients from directly updating `verified_flag`, `verified_at`, or `masked_id_tail`. All verification updates must originate from backend service-role procedures.
- **Reference Check Consent**: Chat agents and LLMs can **propose** reference authorization but can **never grant** it. Granting requires an authenticated student API confirmation.
- **Zero Document Leakage**: Resumes and documents are stored in a private Supabase bucket and are **never sent to external LLMs or OCR services**.
- **Student Visibility Filter**: Company and Recruiter searches enforce `batch_sharing.shared_with_recruiters == true` AND `student_records.opted_out == false`. Candidate contact details (email, phone) are strictly omitted from recruiter search responses.
- **Safe Log Sanitization**: All bearer tokens, JWTs, and API credentials are automatically stripped by `SafeLogFilter`.

---

## Deployment

### API → Docker / Railway / Render

Production Docker build:

```bash
docker build -t recruiting-api apps/api
docker run -p 8000:8000 --env-file apps/api/.env recruiting-api
```

Start Command for PaaS: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### Web → Vercel

Configured via `apps/web/vercel.json`. Set root directory to `apps/web` and build command:

```bash
cd ../.. && pnpm --filter @recruiting/shared build && pnpm --filter @recruiting/web build
```

### Mobile → Expo Application Services (EAS)

```bash
cd apps/mobile
eas build --platform all --profile preview
```
