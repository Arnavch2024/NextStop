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
