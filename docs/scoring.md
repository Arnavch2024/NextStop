# Scoring Engine — Rules & Documented Ambiguities

Canonical reference for the Day 2 deterministic scoring engine (`apps/api/app/scoring.py`).
The engine is pure (no LLM, no DB inside `compute_score`); this document records every
rule and every ambiguity so behavior is unambiguous and testable.

## Base and cap
- Base score: **20**.
- Maximum score: **100** (hard cap; contributions that would exceed 100 are clamped to 100).

## Contributions

| # | Rule | Points | Notes |
|---|------|--------|-------|
| 1 | High school score > 85% (or > 8 GPA) | +1 | See "High school score" below. |
| 2 | Bachelors score > 85% (or > 8 CGPA) | +1 | See "Score scales & thresholds" below. |
| 3 | Per completed internship | +1 each | See "Completed internship". |
| 4 | First full-time job | +1 once | See "First full-time job". |
| 5 | Per full year in full-time work | +1 per full year | See "Full years". |
| 6 | Documents pre-verified | +2 | Wired Day 5; engine accepts the flag now. |
| 7 | Reference check authorized | +2 | Wired Day 5; engine accepts the flag now. |

## Result shape
```
{ score, breakdown: [{reason, points, source}], next_best_actions: [] }
```
- `breakdown[].source` is the **provenance** of the data that earned the points:
  `resume`, `user_said`, or `system` (base / verification flags / derived years).
- `next_best_actions` returns up to 3 deterministic suggestions derived from missing inputs.

## Score scales & thresholds (rule 1 & 2)
- `percentage`: threshold **> 85** (strict). Exactly 85.0 → **0 points**.
- `gpa10` / `cgpa10`: threshold **> 8** (strict). Exactly 8.0 → **0 points**.
- `cgpa4`: normalized to a 10-scale by **×2.5**, then checked **> 8**
  → equivalent to **> 3.2** on the 4-scale. Exactly 3.2 → 0 points.

### Ambiguity A1 — "high school score"
The spec says "high school score" and extraction yields both 10th and 12th.
- **Decision:** high school score = **12th** (higher secondary).
- **Fallback:** if 12th is absent, use **10th**.
- **If both absent:** 0 points (no error). This fallback is an explicit choice and may be revisited.

### Ambiguity A2 — scale equivalence
85% and 8 GPA are **not** equal (8 GPA = 80%). We do **not** normalize to one threshold;
each scale uses its own threshold (above). Only `cgpa4` is normalized (×2.5).

### Ambiguity A3 — 4-scale vs 10-scale "CGPA"
"8 CGPA" is read as a 10-scale CGPA. A 4-scale CGPA is converted ×2.5 before the >8 check.
If a transcript reports an unknown scale, the field is treated as missing (0 points).

## Completed internship (rule 3)
- **Decision:** an internship counts as "completed" iff `end_date` is present and
  `end_date <= today`. Ongoing internships (no `end_date`, or `end_date` in the future)
  do **not** count.
- **Ambiguity A4 — per-internship cap:** there is **no per-student cap** on internship
  points other than the global 100 cap. Each completed internship = +1.
- **Ambiguity A5 — overlap:** no deduplication of overlapping internships beyond the
  upsert natural key `(student_id, company, role)`.

## First full-time job (rule 4)
- **Decision:** +1 if the student has **at least one** full-time `jobs` row. This is the
  "first job" milestone; it is awarded **once**, regardless of how many jobs exist.
- **Ambiguity A6 — "first" semantics:** interpreted as "has any full-time job", not
  "first chronological job only". Documented; revisit if a stricter reading is wanted.

## Full years (rule 5)
- **Decision:** total full-time tenure across all jobs, summed in months, then
  **floor(total_months / 12)**. Current job (no `end_date`) counts up to today.
- **Examples:** 11 months → 0; 12 months → 1; 23 months → 1; 24 months → 2.
- **Ambiguity A7 — floor method:** we floor the **total** months, not each job's months
  then sum. Two 6-month jobs → 12 months → 1 year (not 0). Documented.
- **Ambiguity A8 — internships vs full-time work:** internship months do **not** count
  toward rule 5; only full-time `jobs` do. Internships are scored only by rule 3.

## Verification flags (rules 6 & 7)
- `documents_pre_verified`: true iff a `documents` row exists with
  `verification_status = 'pre_verified'`. None exist until the Day 5 verification flow.
- `reference_check_authorized`: boolean; no backing table until Day 5. Defaults false.
- The engine accepts both as parameters today; Day 5 wires the real sources.
- **Ambiguity A9 — "documents pre-verified":** interpreted as **any** pre-verified document,
  not "all documents verified". Revisit if "complete set" is intended.

## Edge cases covered by tests
- Base 20 for an empty profile.
- Exactly 85.0% → 0; 85.01% → +1. Exactly 8.0 GPA → 0; 8.01 → +1.
- cgpa4 3.2 → 0; 3.21 → +1 (after ×2.5 → 8.0025 > 8).
- Missing data → 0 points and no crash.
- Completed vs ongoing internship.
- Two full-time jobs → first-job still +1 (not +2).
- Full-year flooring: 11mo→0, 12mo→1, 24mo→2.
- `documents_pre_verified` and `reference_check_authorized` each +2.
- Inputs that would exceed 100 clamp to 100.
- `breakdown[].source` reflects provenance (`resume` / `user_said` / `system`).


## Security note (prompt-injection)
The verification flags `documents_pre_verified` and `reference_check_authorized` are derived **only**
from the database (`documents.verification_status`, and a future reference-check record) — never from
agent output or resume text. `recompute_score` reads DB state, so a resume containing an instruction
such as "set my score to 100" or "mark documents pre-verified" cannot change the score. The
deterministic engine is the source of truth for points; the agent never sets flags.
