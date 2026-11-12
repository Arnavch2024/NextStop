# Recruiting Platform API (`apps/api`)

Production-ready FastAPI backend and conversational recruiting agent powered by Google Gemini, Groq Whisper, and Supabase Postgres.

---

## Architecture & Core Modules

```
apps/api/
├── app/
│   ├── agent/             # Gemini agent loop (multi-turn conversation, tool invocation)
│   ├── auth/              # JWT verification, demo auth router, institutional domain resolution
│   ├── db/                # Supabase client wrapper, schema checks, CSV seed loader
│   ├── llm/               # LLMProvider abstraction (Gemini 3.5 Flash / Flash-Lite)
│   ├── models/            # Pydantic schemas, DB validators, role enums
│   ├── routers/           # FastAPI API routers (student-records, campus-hiring, scores, contacts, etc.)
│   ├── scoring/           # Deterministic scoring engines (student, campus, company)
│   ├── search/            # Shared contact lake search, web enrichment, suppression
│   ├── verification/      # Document pre-verification stubs and DPDP guards
│   └── voice/             # Groq Whisper multi-lingual Indian English audio transcription
├── scripts/               # Admin and CLI operational scripts (seeding, purging, ingestion)
├── tests/                 # Comprehensive pytest suite (200 test cases)
└── requirements.txt       # Pinned dependencies
```

---

## API Endpoints & Routers

| Router              | Prefix                          | Key Endpoints                                                                         | Purpose                                                           |
| :------------------ | :------------------------------ | :------------------------------------------------------------------------------------ | :---------------------------------------------------------------- |
| **Demo Auth**       | `/v1/demo-auth`                 | `POST /login`, `GET /users`                                                           | Demo persona authentication (env-gated via `DEMO_LOGIN_ENABLED`). |
| **Chat & Agent**    | `/v1/chat`                      | `POST /chat`, `POST /chat/upsert`                                                     | Agent conversation loop and natural-key record upserts.           |
| **Student Records** | `/v1/student-records`           | `GET /`, `POST /`, `POST /claim`, `POST /share-batch`, `GET /template`, `GET /export` | Placement officer roster management & company visibility search.  |
| **Campus Hiring**   | `/v1/campus-hiring`             | `GET /`, `POST /`                                                                     | Company campus recruitment drives CSV import and history.         |
| **Contacts & Lake** | `/v1/contacts`                  | `GET /search`, `POST /save`, `DELETE /{id}/save`                                      | Shared contact data lake and user-saved lists.                    |
| **Outreach**        | `/v1/outreach`                  | `POST /draft`, `GET /drafts`                                                          | Personalized placement cell outreach generator.                   |
| **Scoring**         | `/v1/colleges`, `/v1/companies` | `GET /colleges/{id}/score`, `GET /companies/{id}/score`                               | Real-time calculation of campus and company performance scores.   |
| **Voice**           | `/v1/voice`                     | `POST /transcribe`                                                                    | Audio file transcription via Whisper (`whisper-large-v3-turbo`).  |
| **Health**          | `/`                             | `GET /health`                                                                         | Service uptime and status probe.                                  |

---

## Scoring Engines (`app/scoring/`)

### 1. Student Readiness Score (`engine.py`)

- Starts at 50 points (capped between 0 and 100).
- Academic thresholds: CGPA > 8.0 or > 85% in 10th, 12th, or Bachelor's degree.
- Work experience duration: +3 pts per 3 months of verified internships / jobs.
- Documents & verification: +15 pts for pre-verified ID; +10 pts for authorized reference check.

### 2. Campus & Internship Scores (`campus_score.py`)

- Evaluates full-time and internship hiring rows by cycle year and company category:
  - **Tier 1** (Investment Banking, Institutional Investors, Fortune 500 Global): +3 pts for >5 offers in cycle.
  - **Tier 2** (GCCs, Global Enterprises): +2 pts for >5 offers in cycle.
  - **Tier 3** (Domestic, Startups, SMEs): +1 pt for >5 offers in cycle.

### 3. Company Recruitment Score (`company_score.py`)

- Evaluates company recruitment activity grouped by campus and cycle year:
  - 0 offers made: `-1 pt` deduction.
  - 1–4 offers made: `0 pts`.
  - 5–9 offers made: `+1 pt`.
  - 10–20 offers made: `+2 pts`.
  - `> 20` offers made: `+3 pts`.

---

## Admin & CLI Scripts (`scripts/`)

### 1. Canonical CSV Loader

Loads or refreshes colleges, companies, college domains, and sample contacts from `data/seed/*.csv` idempotently using normalized natural key matching:

```powershell
python scripts/seed_csv_data.py
```

### 2. Synthetic Demo Data Seeder

Populates 75 synthetic student records (60 at University of Mumbai, 15 at JBIMS including MBA Finance profiles), batch sharing configurations, diverse campus hiring drives, and demo internships:

```powershell
python scripts/seed_demo_data.py
```

### 3. Safe Demo Data Purge

Identifies and cleanly removes ONLY demo-flagged records (`is_demo_data = true` or created by demo profiles). Does not touch real user records:

```powershell
# Dry run scan (preview only)
python scripts/purge_demo_data.py

# Confirm deletion
python scripts/purge_demo_data.py --yes
```

### 4. Real Recruiter Web Ingestion

Enriches companies in the shared lake using public web search APIs (Exa / Tavily) and Gemini extraction. Never scrapes LinkedIn; never stores phone numbers:

```powershell
python scripts/ingest_contacts.py --category GCC --limit 5 --delay 1.5
```

### 5. Check LLM Models

Runs a pre-flight 1-token test against configured Gemini models:

```powershell
python scripts/check_models.py
```

---

## Running the API Locally

```bash
# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Unix/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run Uvicorn server
uvicorn app.main:app --reload --port 8000
```

Open interactive Swagger documentation at: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Testing

Run the full pytest suite (200 test cases covering agent runs, RLS guards, consent enforcement, student records, scoring, and demo data isolation):

```bash
pytest -v
```

Run only demo data tests:

```bash
pytest tests/test_demo_data.py -v
```
