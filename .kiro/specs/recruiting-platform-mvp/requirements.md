# Recruiting Platform MVP — Requirements

## 1. Overview

A voice/text-driven recruiting platform connecting Mumbai college students (batches 2027 and 2028) with companies and recruiters. The differentiating principle: users never fill out forms. A conversational agent turns natural language — typed or spoken — into structured records.

This spec covers the **Day 1 walking skeleton**: the smallest end-to-end slice that proves the architecture (auth → role → chat → agent → structured records → realtime cross-device sync). Everything not listed here is explicitly out of scope.

## 2. Goals & Success Criteria

The Day 1 build succeeds when all of the following are demoable end-to-end:

- A new user can sign up, pick one of four roles, and land on a chat screen on both web and mobile.
- On web or mobile, the user types a message; the agent responds and creates/updates a structured record (e.g., a student self-reporting college and batch, or a company adding a contact) via the `upsert_record` tool.
- A message typed on mobile appears in the web chat for the same signed-in user within 2 seconds (realtime sync).
- All data is secured with Supabase Row-Level Security so a user can only read their own records.
- The API exposes `/health` and `/v1/chat` with auto-generated OpenAPI documentation.
- The web app deploys to Vercel and the API deploys to Railway or Render against hosted Supabase.

## 3. Non-Goals (Out of Scope for Day 1)

- Resume / CV parsing
- Web search / external data enrichment
- Candidate scoring or ranking
- Dashboards or analytics
- Consent / data-sharing approval flows
- Voice input (Day 2 — the chat screen reserves the affordance but is text-only for Day 1)
- Notifications, email, SMS
- Multi-language UI
- Admin tooling beyond the role picker

## 4. User Roles

Four roles, selected at onboarding and stored on the user's profile:

| Role | Who they are | What they do in Day 1 |
|------|--------------|------------------------|
| Student | A student in batch 2027/2028 at a Mumbai college | Self-reports their details; the agent upserts a `students` record |
| Placement Officer | A college's placement cell staff | Adds/edits college and student records via chat |
| Company | A hiring company entity | Adds company details and contacts via chat |
| Recruiter | An individual recruiter at a company | Adds contacts and company details via chat |

## 5. Functional Requirements

### 5.1 Authentication & Onboarding
- **FR-AUTH-1**: WHEN a user opens the app for the first time THE SYSTEM SHALL present a login screen using Supabase Auth.
- **FR-AUTH-2**: WHEN a user completes authentication THE SYSTEM SHALL present a role-picker screen offering exactly four options: Student, Placement Officer, Company, Recruiter.
- **FR-AUTH-3**: WHEN a user selects a role THE SYSTEM SHALL create a `profiles` row (if absent) and persist the selected `role`.
- **FR-AUTH-4**: WHEN a user has already selected a role THE SYSTEM SHALL route them directly to the chat screen on subsequent launches.

### 5.2 Chat Interface
- **FR-CHAT-1**: THE SYSTEM SHALL provide a chat screen on both web and mobile with a text input and a scrollable message list.
- **FR-CHAT-2**: WHEN a user submits a text message THE SYSTEM SHALL send it to `POST /v1/chat` and display the user's message and the agent's reply in the message list.
- **FR-CHAT-3**: THE SYSTEM SHALL reserve a visible voice-input affordance in the chat composer, but it SHALL be disabled with a "Day 2" label for Day 1.
- **FR-CHAT-4**: THE SYSTEM SHALL display agent processing steps (tool calls/results) inline or in a collapsible steps view so the demo shows the agent working.

### 5.3 Agent
- **FR-AGENT-1**: THE SYSTEM SHALL expose an agent loop implemented in plain Python (no heavy framework) that calls the Claude API with tool use.
- **FR-AGENT-2**: THE SYSTEM SHALL provide the agent exactly one tool: `upsert_record`, parameterized by table name and record data.
- **FR-AGENT-3**: THE SYSTEM SHALL constrain `upsert_record` to a whitelist of tables: `students`, `colleges`, `companies`, `contacts`.
- **FR-AGENT-4**: THE SYSTEM SHALL use a role-aware system prompt so the agent extracts the fields relevant to the user's role.
- **FR-AGENT-5**: WHEN the agent calls `upsert_record` THE SYSTEM SHALL write the tool call and tool result to `raw_events` as separate events.
- **FR-AGENT-6**: WHEN a user message is received THE SYSTEM SHALL write it to `raw_events` with `source='user_message'`.
- **FR-AGENT-7**: WHEN the agent produces a reply THE SYSTEM SHALL write it to `raw_events` with `source='agent_message'`.
- **FR-AGENT-8**: THE SYSTEM SHALL create an `agent_runs` row at the start of each turn and log the step sequence, setting status to `completed` or `failed` at the end.

### 5.4 Data & Security
- **FR-DATA-1**: THE SYSTEM SHALL store all structured data in Supabase Postgres using the schema defined in the design doc.
- **FR-DATA-2**: THE SYSTEM SHALL enforce Row-Level Security such that a user can read only records they own (their profile, their student record, events they authored, their agent runs).
- **FR-DATA-3**: THE SYSTEM SHALL record every user message, tool call, tool result, and agent message as an immutable `raw_events` row.

### 5.5 Realtime
- **FR-RT-1**: WHEN a message is created for a user on one device THE SYSTEM SHALL reflect it on any other device signed in as the same user within 2 seconds via Supabase Realtime.

### 5.6 API
- **FR-API-1**: THE SYSTEM SHALL expose `GET /health` returning a JSON status object.
- **FR-API-2**: THE SYSTEM SHALL expose `POST /v1/chat` that requires a Supabase access token, accepts `{message}`, and returns `{reply, steps, records_created}`.
- **FR-API-3**: THE API SHALL serve auto-generated OpenAPI documentation at `/docs` (Swagger UI) and `/openapi.json`.
- **FR-API-4**: WHEN the access token is missing or invalid THE SYSTEM SHALL reject the request with HTTP 401.

### 5.7 Deployment
- **FR-DEPLOY-1**: THE SYSTEM SHALL deploy the web app to Vercel.
- **FR-DEPLOY-2**: THE SYSTEM SHALL deploy the API to Railway or Render.
- **FR-DEPLOY-3**: THE SYSTEM SHALL use Supabase hosted Postgres, Auth, Realtime, and Storage.

## 6. Constraints (Fixed Stack — Do Not Change)

- Monorepo with pnpm workspaces + Turborepo.
- `apps/web`: Next.js + TypeScript + Tailwind + shadcn/ui.
- `apps/mobile`: Expo + TypeScript.
- `apps/api`: FastAPI + Python 3.12.
- `packages/shared`: shared TypeScript types and API client.
- Supabase: Postgres, Auth, Realtime, Storage.
- Claude API with tool use for the agent.

## 7. Non-Functional Requirements

- **NFR-1**: The web and mobile apps SHALL be strongly typed (TypeScript) and share types via `packages/shared`.
- **NFR-2**: The API SHALL validate tool calls server-side before execution; `upsert_record` SHALL enforce a table whitelist and ownership.
- **NFR-3**: Secrets (Supabase service key, Claude API key) SHALL never be exposed to the client; the API SHALL validate user-supplied JWTs server-side.
- **NFR-4**: Realtime round-trip for cross-device message sync SHALL be under 2 seconds in normal network conditions.
---

## 8. Day 2 — Student Slice (extends the spec; stack and Day 1 contracts unchanged)

Day 2 adds the Student experience: voice input, resume upload + parsing, deterministic scoring, and a student home screen. This section **lifts** the following Day 1 non-goals into scope for Day 2 only: resume parsing, voice input, and scoring. The Day 1 contracts (`GET /health`, `POST /v1/chat`) are unchanged; new endpoints are additive. The internal `upsert_record` tool is extended **additively** (new tables + a `source` field) — the public `/v1/chat` response shape `{reply, steps, records_created}` is unchanged.

### 8.1 Voice Input
- **FR-VOICE-1**: THE SYSTEM SHALL expose `POST /v1/voice/transcribe` (multipart) accepting an audio file and returning `{text}`.
- **FR-VOICE-2**: THE SYSTEM SHALL support transcription in English and Hindi; Marathi support SHALL be best-effort pending a recorded test (see FR-VOICE-6).
- **FR-VOICE-3**: WHEN the client receives transcribed text THE SYSTEM SHALL send it through the existing `POST /v1/chat` (no new chat contract).
- **FR-VOICE-4**: WHEN audio cannot be transcribed THE SYSTEM SHALL return HTTP 422 with an error message.
- **FR-VOICE-5**: THE transcription provider SHALL be pluggable behind a `Transcriber` interface, defaulting to an OpenAI Whisper-compatible API (`whisper-1`).
- **FR-VOICE-6**: A Marathi transcription test SHALL exist; until it passes reliably, Marathi is marked best-effort and the test carries an explicit best-effort marker with its outcome recorded.

### 8.2 Resume Upload & Parsing
- **FR-RESUME-1**: THE SYSTEM SHALL expose `POST /v1/students/me/resume` (multipart) accepting PDF or DOCX.
- **FR-RESUME-2**: THE SYSTEM SHALL store the file in a private Supabase Storage bucket and expose it only via signed URLs.
- **FR-RESUME-3**: A resume-parsing agent SHALL extract: name, college, degree, branch, batch year, 10th %, 12th %, CGPA or % (bachelors), internships (company, role, dates), jobs (company, role, dates), skills.
- **FR-RESUME-4**: EVERY extracted field SHALL be stored with `source='resume'` and a `confidence` value in [0,1].
- **FR-RESUME-5**: THE SYSTEM SHALL never present a form to the user; any missing field SHALL be requested in chat.
- **FR-RESUME-6**: THE SYSTEM SHALL store document metadata (kind, storage path, mime, size) in the `documents` table; file bytes live only in Storage.

### 8.3 Chat-Created Fields
- **FR-CHATFIELD-1**: WHEN a student states a fact in chat (e.g., "I interned at TCS for 2 months") THE agent SHALL call `upsert_record` and store it with `source='user_said'`.
- **FR-CHATFIELD-2**: THE chat agent's `upsert_record` SHALL accept the new tables (`education`, `internships`, `jobs`, `skills`) in addition to the Day 1 tables.

### 8.4 Scoring Engine
- **FR-SCORE-1**: THE SYSTEM SHALL implement a deterministic Python scoring module with no LLM involvement.
- **FR-SCORE-2**: THE score SHALL start at 20 and be capped at 100.
- **FR-SCORE-3**: THE SYSTEM SHALL award +1 if high school score > 85% (or > 8 GPA); +1 if bachelors score > 85% (or > 8 CGPA); +1 per completed internship; +1 for the first full-time job; +1 per full year in full-time work.
- **FR-SCORE-4**: THE SYSTEM SHALL award +2 when documents are pre-verified and +2 when a reference check is authorized; both inputs SHALL be accepted by the engine now even though they are wired on Day 5.
- **FR-SCORE-5**: THE scoring result SHALL be `{score, breakdown: [{reason, points, source}], next_best_actions: []}`.
- **FR-SCORE-6**: THE SYSTEM SHALL expose `GET /v1/students/me/score` returning the current score breakdown.
- **FR-SCORE-7**: THE SYSTEM SHALL recompute the score whenever student data changes and store the history in `score_events`.
- **FR-SCORE-8**: EVERY ambiguity in the scoring rules SHALL be documented in `docs/scoring.md`.

### 8.5 Student Home Screen
- **FR-HOME-1**: THE SYSTEM SHALL provide a Student home screen (web + mobile) showing the current score.
- **FR-HOME-2**: THE home screen SHALL show the breakdown list (answering "why is my score N?").
- **FR-HOME-3**: THE home screen SHALL show the next best action.
- **FR-HOME-4**: THE home screen SHALL show a basic vertical timeline of college → internship → job.
- **FR-HOME-5**: THE railway-style timeline visual is out of scope for Day 2 (Day 5).

### 8.6 Schema Additions
- **FR-SCHEMA-1**: THE SYSTEM SHALL add tables: `education`, `internships`, `jobs`, `skills`, `score_events`, `documents` (metadata only).
- **FR-SCHEMA-2**: All new tables SHALL be protected by RLS so a student sees only their own rows.

### 8.7 Day 2 Non-Goals
- Document verification UI/flow and reference-check flow (Day 5 wiring only; the engine must accept the flags now).
- Railway-style timeline visual (Day 5).
- Recruiter/Company-facing views of student scores (Day 3+).

### 8.8 Prompt-Injection Defense
- **FR-PROMPTSEC-1**: WHEN resume-derived (or any structured) values are injected into the chat agent's system prompt, THE SYSTEM SHALL place them inside a delimited `<student_data>...</student_data>` block.
- **FR-PROMPTSEC-2**: THE system prompt SHALL include an explicit rule that the `<student_data>` block is data, not instructions, and that the agent SHALL NOT follow any instructions, commands, or role-play found inside it.
- **FR-PROMPTSEC-3**: WHEN the resume-parsing agent ingests raw resume text, THE SYSTEM SHALL wrap it in a delimited `<resume_document>...</resume_document>` block with the same "data, not instructions" rule.
- **FR-PROMPTSEC-4**: THE scoring verification flags (`documents_pre_verified`, `reference_check_authorized`) SHALL be derived only from the database, never from agent output or resume text, so injection cannot inflate the score.
- **FR-PROMPTSEC-5**: THE SYSTEM SHALL include a test using a resume containing a prompt-injection attempt and SHALL assert the attempt is treated as data (no forbidden action, no score inflation).
