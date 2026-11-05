# Recruiting Platform MVP — Tasks

> Implementation order is top-to-bottom. Each task has a Definition of Done (DoD) that can be demoed. Check the box when the DoD is met.

## Phase 0 — Foundations

### Task 0.1 Scaffold monorepo
- [ ] Initialize pnpm workspaces + Turborepo at the repo root.
- [ ] Create `apps/web` (Next.js App Router, TS, Tailwind, shadcn/ui), `apps/mobile` (Expo, TS), `apps/api` (FastAPI, Python 3.12), `packages/shared` (TS lib).
- [ ] `pnpm install` and `turbo build` run cleanly. Python venv + `uvicorn` documented in `apps/api/README`.
- **DoD**: `turbo build` builds web + shared; `apps/api` runs `uvicorn app.main:app` locally; all four workspaces exist with hello-world entrypoints.

### Task 0.2 Shared types & API client
- [ ] In `packages/shared`: `types/api.ts` and `types/db.ts` matching the OpenAPI + schema in the design doc.
- [ ] `client/apiClient.ts` exporting `health(base)` and `chat(base, message, token)`.
- [ ] `client/supabase.ts` shared Supabase client factory.
- [ ] Exported from `packages/shared/index.ts`; consumed by web + mobile.
- **DoD**: `pnpm --filter shared build` emits types; web can import `apiClient` and call a stubbed `/health`.

## Phase 1 — Data & Auth

### Task 1.1 Supabase schema + RLS migration
- [ ] Create a single SQL migration (or `supabase/migrations`) with the two enums, the 7 tables, indexes, and RLS policies from the design doc.
- [ ] Add a trigger (or onboarding path) to create a `profiles` row on `auth.users` insert.
- **DoD**: Running the migration on a fresh Supabase project creates all tables; a query as a non-service role cannot read another user's rows; selecting your own row works.

### Task 1.2 Web login + role picker
- [ ] `app/login/page.tsx` with Supabase Auth (email/password + magic link).
- [ ] `app/onboarding/page.tsx` with 4 role cards; selecting one upserts `profiles(role)`.
- [ ] Redirect to `/chat` once role is set; redirect to `/onboarding` if role is null.
- **DoD**: Fresh signup → pick role → lands on `/chat`; reload keeps the role and skips onboarding.

### Task 1.3 Mobile login + role picker
- [ ] Mirror web flows in Expo with `@supabase/supabase-js` + AsyncStorage session persistence.
- **DoD**: Same DoD as 1.2 on a physical device or emulator.

## Phase 2 — API & Agent

### Task 2.1 FastAPI skeleton + health + OpenAPI
- [ ] `apps/api/app/main.py` with `GET /health` and Pydantic models for the OpenAPI contract.
- [ ] CORS for web + mobile origins.
- [ ] `/docs` and `/openapi.json` auto-served.
- **DoD**: `curl /health` returns `{status,version,time}`; `/docs` renders Swagger matching the design contract.

### Task 2.2 Auth on /v1/chat
- [ ] `POST /v1/chat` with bearer auth; validate JWT via Supabase `auth.getUser`; resolve profile (id, role).
- [ ] Return 401 on missing/invalid token.
- **DoD**: An authenticated call with a stub agent returns `{reply:"…",steps:[],records_created:[]}`; a call without a token returns 401.

### Task 2.3 Agent loop + upsert_record tool
- [ ] `apps/api/app/agent.py` implementing the loop in the design doc.
- [ ] `upsert_record` with table whitelist + ownership enforcement + natural-key upsert.
- [ ] Write `user_message`, `tool_call`, `tool_result`, `agent_message` raw_events and manage the `agent_runs` row.
- **DoD**: As a student, messaging "I'm Riya at St. Xavier's, batch 2027, BSc CS" creates/updates a `students` row + `colleges` row, returns a human reply, and all four event types appear in `raw_events` with the correct `actor_id`.

### Task 2.4 Claude integration
- [ ] Wire the Anthropic SDK with the `upsert_record` tool; role-aware system prompts.
- [ ] `ANTHROPIC_MODEL` configurable; errors surface as `agent_runs.status='failed'`.
- **DoD**: A company user saying "We're Acme Corp, hiring SDEs, contact pooja@acme.com" upserts a `companies` + `contacts` row; the agent stops calling tools and returns a final reply.

## Phase 3 — Frontend Chat & Realtime

### Task 3.1 Web chat screen
- [ ] `app/chat/page.tsx`: message list + text composer; voice button visible but disabled (label "Day 2").
- [ ] Calls `apiClient.chat`; shows user message + agent reply; shows steps in a collapsible view.
- **DoD**: Type a message → see your message and the agent reply; steps (tool calls) are visible; a created record is shown.

### Task 3.2 Mobile chat screen
- [ ] Expo chat screen mirroring web.
- **DoD**: Same DoD as 3.1 on device/emulator.

### Task 3.3 Realtime cross-device sync
- [ ] Web + mobile subscribe to Supabase Realtime `postgres_changes` on `raw_events` for the current user.
- [ ] Insert of `user_message`/`agent_message` appends to the message list on the other device.
- **DoD**: Signed in as the same user on web + mobile, send a message on mobile → it and the agent reply appear on the web message list within 2 seconds, and vice versa.

## Phase 4 — Deploy & Verify

### Task 4.1 Deploy web (Vercel)
- [ ] Connect repo to Vercel; set env vars; build from `apps/web`.
- **DoD**: Production web URL loads login; a real signup + role pick + chat works against the deployed API.

### Task 4.2 Deploy API (Railway/Render)
- [ ] Deploy FastAPI with a `/health` probe; set service env vars.
- **DoD**: `https://<api>/health` returns ok; `/v1/chat` works end-to-end from the deployed web app.

### Task 4.3 End-to-end demo verification
- [ ] Run the full flow on deployed environments: signup → role → chat → record created → realtime sync.
- **DoD**: A recorded demo shows: (1) signup + role on web, (2) chat creating a record verifiable in Supabase, (3) the same user on mobile seeing the message within 2s. Each Phase 1–3 DoD reproduced on deployed infra.
