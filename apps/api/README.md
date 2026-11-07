# Recruiting Platform API (`apps/api`)

FastAPI backend and conversational recruiting agent powered by Google Gemini and Supabase.

## Features

- **FastAPI application**: Auto-generated OpenAPI specs and documentation at `/docs` and `/openapi.json`.
- **Supabase JWT Authentication**: Secure bearer token verification dependency rejecting unauthenticated requests with HTTP 401.
- **Conversational Recruiting Agent**: Multi-turn agent loop with tool use using Google Gemini (max 5 iterations per turn).
- **`upsert_record` Tool**: Whitelisted tables (`students`, `colleges`, `companies`, `contacts`) with Pydantic schema validation and server-enforced natural-key upsert with ownership.
- **Audit Logging**: Persists `user_message`, `tool_call`, `tool_result`, and `agent_message` in `raw_events` and records run states in `agent_runs`.
- **Safe Logging**: Redacts all tokens and secrets; never logs raw bearer tokens or API keys.

## Quickstart

### 1. Setup Virtual Environment

```bash
cd apps/api
python -m venv .venv

# Windows
.venv\Scripts\activate

# Unix/macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Environment Configuration

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Fill in your Supabase credentials (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`) and Google Gemini API key (`GEMINI_API_KEY`).

### 3. Run Locally

```bash
uvicorn app.main:app --reload --port 8000
```

Interactive API docs are available at: [http://localhost:8000/docs](http://localhost:8000/docs)

### 4. Run Tests

```bash
pytest tests -v
```

## Docker Deployment

```bash
docker build -t recruiting-api .
docker run -p 8000:8000 --env-file .env recruiting-api
```
