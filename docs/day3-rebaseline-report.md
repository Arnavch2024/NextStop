# Day 3 Spec Re-baseline Report

Re-baselined the Day 3 spec against the committed Day 1/2 code.

## What I read

- `supabase/migrations/001_init.sql`, `002_student_slice.sql`
- `apps/api`: `app/agent/{runner,tools,prompts,resume_parser}.py`, `app/db/supabase.py`, `app/models/db.py`, `app/routers/{chat,health,students,voice}.py`, `tests/*`
- `packages/shared/src/types/{api,db}.ts`; `apps/web` (chat + student home)

## What differed (real vs spec §11.1 / §11.2)

1. **Agent framework = Gemini, not Claude.** Committed code uses `google.genai` (`types.FunctionDeclaration`/`types.Tool`, `generate_content`, `settings.GEMINI_MODEL`). The spec's fixed-stack line (§6) and Day 1 §4 say Claude. → Day 3 tools must be Gemini `FunctionDeclaration`s in the existing runner.
2. **`contacts` schema assumption MATCHED reality** (`full_name`, `phone`, `owner_id`, unique `(company_id, lower(email))`). But the spec's migration DROPPED `phone` + `owner_id` — not allowed since they may hold data. → retain deprecated, backfill `created_by_profile_id` from `owner_id`.
3. **RLS MATCHED** (`colleges/companies/contacts owner` "for all"; `students self`; `raw_events actor`; `agent_runs self`). Day 3 flip is as designed; `drop policy if exists` is safe.
4. **`agent_runs` has no `summary` column** (only `id, profile_id, status, steps, created_at, updated_at`). Spec implied a top-level summary. → store the search summary as a final entry in `steps[]`.
5. **`companies.category` / `colleges` Mumbai CHECK** — additive; existing rows are all Mumbai → CHECK validates.
6. **`raw_events.source='search'`** — additive; the Gemini history builder ignores unknown sources, so search audits are not replayed as chat. No conflict.
7. Existing routers: `chat`, `health`, `students` (`/v1/students/me/resume|/resume/{id}|/score|/profile`), `voice`. Day 3 adds `contacts`/`outreach`/`agent-runs` routers — no conflict.

## Day 1/2 code paths that read contacts/companies/colleges (must update for the changed `contacts` shape)

- `apps/api/app/models/db.py` — `ContactUpsertData` (`full_name` required, `phone`) → `name`, drop `phone`, add lake fields.
- `apps/api/app/agent/tools.py` — `contacts` branch (matches `full_name`, sets `owner_id`, inserts `phone`) → new dedupe, stop writing `owner_id`, never write `phone`.
- `apps/api/app/agent/prompts.py` — Company/Recruiter prompts (`full_name, email, phone`) → `name`/title/public URL/business email, no `phone`.
- `apps/api/tests/test_tools.py` — `test_upsert_company_and_contact` (`full_name` + `phone`, expects "updated") → `name`, no `phone`, expect merge.
- `packages/shared/src/types/db.ts` — `Contact` interface (`full_name`/`phone`/`owner_id`) → lake shape (rebuild `dist`).
- Note: `students.full_name` is UNCHANGED (Day 3 touches only `contacts`); all student tests, chat, and home keep working.

## What I changed in the spec

- **design §11.1**: 003 is non-destructive + re-runnable (guarded rename; `add column if not exists`; backfill `created_by_profile_id` from `owner_id`; retain `phone`/`owner_id` deprecated; drop only the legacy index).
- **design §11.2**: note that `phone`/`owner_id` are retained deprecated; policy drops are independent of retained columns.
- **design §11.3**: tools re-cast as Gemini `FunctionDeclaration`s in the existing runner (role-aware).
- **design §11.6**: search summary stored as a step in `steps[]` (no new column).
- **design §11.11**: added re-baseline decisions 16–20.
- **requirements §9.3**: Gemini re-baseline note.
- **tasks 6.1**: rewritten as non-destructive/re-runnable 003 + rollback note + DoD (Day 1/2 tests pass + code-path update list).
- **tasks 6.8**: Gemini tool declarations + summary-as-step.

## Open decisions that need your input

1. **Gemini vs Claude** — **Resolved: keep Google Gemini** (Gemini Pro available via `GEMINI_MODEL`). The committed agent uses `google.genai`; the spec's stack line (§6) and agent sections now reflect Gemini.
2. **Keep `contacts.phone` / `owner_id` deprecated (not dropped)** to avoid data loss, with a later cleanup migration to drop after verifying no data — acceptable? Or drop now if you confirm `contacts` holds no real data? **Needs decision.**
