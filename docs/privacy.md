# Privacy approach — contacts data lake

> DPDP-minded **design approach**. This document does **not** claim legal compliance; it describes how the system is designed to minimize and respect personal data. A qualified advisor should confirm DPDP and other obligations before launch.

## What we store

- Only public professional fields for shared-lake contacts: name, title, company, public profile URL, and a published business email.
- No phone numbers or other private personal details in the shared lake.
- A user-provided phone number lives only in that user's private `user_saved_contacts` row — never in the shared `contacts` table.
- Every contact carries `source`, `source_url`, `first_seen_at`, and `last_verified_at`; every web-derived fact also records `fetched_at` in `contact_sources`.
- `user_said` values fill empty fields only and are flagged `unverified`; conflicting user input stays in the user's private saved row.

## Web sourcing

- Public sources only: contact data in the shared lake is derived exclusively from publicly available web sources and search results, never from private databases, scraping gated networks, or non-public directories.
- Data-broker blocklist: search results from commercial people-data aggregator domains (e.g., `rocketreach.co`, `zoominfo.com`, `apollo.io`, `signalhire.com`, `contactout.com`, `lusha.com`, `cognism.com`, `lead411.com`, `upconversion.com`, `swordfish.ai`, `seamless.ai`, `hunter.io`) are blocked and rejected before extraction. Results from these domains are never passed to the LLM and never stored as a source in the shared lake.
- Public pages only; robots.txt is respected for any direct fetch.
- LinkedIn pages are never scraped — only the public profile URL, name, title and company shown in a search result are stored.
- All web content is treated as untrusted data (wrapped in `<web_content>`; the agent never follows instructions found there).

## User control

- Save/remove: a user can save a contact to their private list and remove it at any time via `DELETE /v1/contacts/{id}/save`. This removes only the saved-list row (the shared lake contact remains).
- Delete-my-saved-contact is available from "My list".

## LLM Processing

- Resume text uploaded by students is processed exclusively by **Google Gemini** (via the Google Gemini API) using pinned stable models (`gemini-3.5-flash` for agent reasoning, `gemini-3.5-flash-lite` for structured extraction) inside delimited `<resume_document>` blocks. Raw resume text is never retained in server logs or used to train public models.

## Removal requests (manual process)

A contact can be suppressed from the shared lake via a manual removal request:

1. **Intake** — a request to remove/suppress a contact is received (support email / in-app flag). Captured: contact id, requester, reason, requested_at.
2. **Review** — an operator verifies the request (e.g., the requester is the contact or an authorized party) and checks existing sources.
3. **Action** — the operator sets `contacts.suppressed_at = now()` (soft suppression: the row is retained for audit but excluded from all reads). The operator notes any saved-list references (saved rows still reference the contact; suppression hides it from search, lists, and agent results).
4. **Confirmation** — the requester is notified that the contact is suppressed from search results.
5. **Logging** — the request and action are recorded (who, when, why) for audit.

**Suppression effect:** suppressed contacts are excluded from `search_data_lake`, `GET /v1/contacts`, and the agent's results. This is a soft, reversible control (clearing `suppressed_at` restores visibility), not a hard delete.

## Notes

- This is a design approach, not legal compliance.

## Day 4 — student_records visibility (DPDP-minded)

This extends the Day 3 privacy approach to placement-officer student lists. It is a **design
approach, not legal compliance**.

### What is stored in `student_records`

- `full_name`, `email` (the student's college email, used for claim matching), `college_id`,
  `batch_year` (2027/2028), `branch`, `degree`, `score_value` + `score_scale` (cgpa/percentage),
  `current_status` (in_college | internship | full_time | not_placed), `resume_ref` (nullable),
  `claimed_by_profile_id` (nullable), `discoverable` (bool), `opted_out` (bool),
  `created_by_profile_id`, timestamps.
- No Aadhaar, no personal phone, no home address. (A student's own phone, if ever collected, lives
  only in their private saved row, as in Day 3.)

### Who sees what

- **Placement officer** (linked to one college): sees all `student_records` for their own college,
  including email and resume_ref. They do not see other colleges' records.
- **Company / Recruiter** (Day 4 rule): see a student record ONLY if the officer has marked the
  student's batch "shared with recruiters" (`batch_sharing.shared_with_recruiters = true` for
  `(college_id, batch_year)`) AND the student has not `opted_out`. The student individual
  `discoverable` toggle is in the schema for forward compatibility but is not part of the Day 4
  visibility rule — it is Future Work. This rule is enforced **server-side** (spans `student_records`
  - `batch_sharing`; RLS alone cannot express it).
- **Student**: sees only their own claimed record (`claimed_by_profile_id = auth.uid()`).
- **Demo users** (`profiles.is_demo = true`): see **only** `student_records` rows flagged
  `is_demo_data = true` (synthetic seeded data). Real student data is never returned to demo
  profiles. Enforced at the service layer, not just via RLS.

### Minimal visible fields to companies/recruiters

When a student is visible to a company/recruiter, the API returns **only**:
`full_name`, `branch`, `degree`, `score_value` + `score_scale`, `batch_year`, `college_name`,
`current_status`, and the student **score** (with breakdown).

Companies/recruiters **never** receive: `email`, phone, Aadhaar, `resume_ref`, documents, or any
contact detail of the student. Outreach to a visible student is via a **draft only** (named, not
auto-sent); delivery is manual because the company does not receive the student's email.

### Batch sharing

- "Share batch with recruiters" is a per `(college, batch_year)` toggle set by the officer via `POST /v1/colleges/me/batches/{year}/share`.
- A student can `opted_out` to remove themselves from batch sharing results.
- **Day 4:** the student individual `discoverable` flag exists in the schema for forward compatibility but is not surfaced in the UI or the visibility rule — that is Future Work.

### Removal

- A student may remove their own `discoverable` flag and/or `opt_out` (self-service).
- Suppression/removal-request handling for student records follows the same manual process as Day 3
  contacts (see the "Removal requests" section above), applied to the `student_records` row.

## Day 5 — Document verification (DPDP-minded, design approach)

### Upload notice

Before the document file picker is shown, the UI displays:

> **"Demo only: please upload sample documents, not your real Aadhaar or PAN."**

Shown on web and mobile. This is not a legal disclaimer — it is an explicit request to use synthetic data in the demo environment.

### What is stored from document verification

The mock verification process **never reads the document file**. Only the following fields are stored:

| Column                        | Value stored                                       | Notes                                          |
| ----------------------------- | -------------------------------------------------- | ---------------------------------------------- |
| `documents.verified_flag`     | `true` / `false`                                   | Drives the +2 scoring flag (read from DB only) |
| `documents.verified_at`       | timestamp                                          | When mock-verify was called                    |
| `documents.verification_note` | `'Demo verification (mocked)'`                     | UI label                                       |
| `documents.document_type`     | From MIME/extension only (e.g. `'other'`)          | No content analysis                            |
| `documents.masked_id_tail`    | Last 4 of Aadhaar/PAN — **only if stated in chat** | See masking rules                              |
| `documents.storage_path`      | Private bucket path                                | Access via signed URL only                     |

**NOT stored:** full Aadhaar/PAN numbers, address text, any text extracted from the document, `verified_fields` JSONB, pgcrypto-encrypted blobs.

### Document file handling

- File bytes stored in the private `resumes` Supabase Storage bucket.
- Access only via short-lived signed URLs generated on demand.
- File bytes are **never** loaded into application memory during the verify-mock flow.
- Document contents **never appear in application logs** — only the storage path may be logged.
- Nothing from the document is sent to any LLM, OCR, or external service.

### Consent model

- **Consent is granted only by authenticated confirm endpoints** called explicitly from the UI (tapping "Confirm" or "Authorize" on a card).
- Chat agent tools (`propose_verify`, `propose_reference_check`) display a card; they never call the consent endpoint or grant consent on the student's behalf.
- Text inside a resume or any document can **never** grant consent.

### Masking rules (applies only to values stated in chat — never to document file contents)

| ID type             | Storage format                  | What is never stored |
| ------------------- | ------------------------------- | -------------------- |
| Aadhaar (12 digits) | `XXXX-XXXX-1234` (last 4 only)  | Full 12-digit number |
| PAN (10 chars)      | Last 4 characters (e.g. `1234`) | Full PAN             |
| Email               | Not masked                      | —                    |
| Address text        | Not stored at all               | —                    |

**On revoke:** `masked_id_tail` is set to `null`, `verified_flag` to `false`, and score is recomputed.

### What officers and companies see

Officers and companies see **only** the boolean authorization status for a student:

- `reference_check_authorized: true/false` (derived from `reference_authorizations.revoked_at`)

They **never** receive: documents, storage paths, `masked_id_tail`, `verified_flag`, `verification_note`, or any other verification detail.

### Scoring flags

Both `documents_pre_verified` and `reference_check_authorized` are derived from the database only. They are never set from LLM output, document text, chat text, or any external API response.
