# Privacy approach — contacts data lake

> DPDP-minded **design approach**. This document does **not** claim legal compliance; it describes how the system is designed to minimize and respect personal data. A qualified advisor should confirm DPDP and other obligations before launch.

## What we store

- Only public professional fields for shared-lake contacts: name, title, company, public profile URL, and a published business email.
- No phone numbers or other private personal details in the shared lake.
- A user-provided phone number lives only in that user's private `user_saved_contacts` row — never in the shared `contacts` table.
- Every contact carries `source`, `source_url`, `first_seen_at`, and `last_verified_at`; every web-derived fact also records `fetched_at` in `contact_sources`.
- `user_said` values fill empty fields only and are flagged `unverified`; conflicting user input stays in the user's private saved row.

## Web sourcing

- Public pages only; robots.txt is respected for any direct fetch.
- LinkedIn pages are never scraped — only the public profile URL, name, title and company shown in a search result are stored.
- All web content is treated as untrusted data (wrapped in `<web_content>`; the agent never follows instructions found there).

## User control

- Save/remove: a user can save a contact to their private list and remove it at any time via `DELETE /v1/contacts/{id}/save`. This removes only the saved-list row (the shared lake contact remains).
- Delete-my-saved-contact is available from "My list".

## LLM Processing

- Resume text uploaded by students is processed exclusively by **Google Gemini** (via the Google Gemini API) using pinned stable models (`gemini-2.5-flash` for agent reasoning, `gemini-1.5-flash` for structured extraction) inside delimited `<resume_document>` blocks. Raw resume text is never retained in server logs or used to train public models.

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
