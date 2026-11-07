# Contributing Guidelines

## Quick Setup

Run the one-time setup command to install dependencies and enable all Git pre-commit hooks (Python & JS):

```bash
# 1. Install Node dependencies and Husky hooks
pnpm install

# 2. Set up Python virtual environment and pre-commit
cd apps/api
python -m venv .venv
source .venv/bin/activate       # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
pre-commit install
cd ../..
```

---

## Running Tests & Checks Locally

All checks should pass locally before pushing:

### 1. Python API (`apps/api`)

```bash
cd apps/api
# Lint & formatting check
ruff check .
ruff format --check .

# Run test suite
pytest -v
```

### 2. Web & Mobile (`apps/web`, `apps/mobile`, `packages/shared`)

```bash
# Build shared types
pnpm --filter @recruiting/shared build

# Linting
pnpm --filter @recruiting/web lint
pnpm exec eslint apps/mobile packages/shared

# Typechecking
pnpm --filter @recruiting/shared exec tsc --noEmit
pnpm --filter @recruiting/web exec tsc --noEmit
pnpm --filter @recruiting/mobile exec tsc --noEmit

# Web build
pnpm --filter @recruiting/web build
```

---

## Pre-Commit Hooks

Once enabled, pre-commit runs automatically on `git commit`:

- **JS/TS:** Prettier and ESLint via `lint-staged` + Husky
- **Python:** Ruff (lint with `--fix` + format) and basic hygiene hooks (`trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-added-large-files`, `detect-private-key`)

To run manually on all files:

```bash
# Python & hygiene hooks
pre-commit run --all-files

# JS formatting & linting
pnpm exec prettier --write "apps/**/*.{ts,tsx,json}" "packages/**/*.{ts,tsx,json}"
pnpm exec eslint apps/mobile packages/shared apps/web
```

---

## Branch Naming & Commit Convention

- **Branch naming:** Use `type/dayX-feature`, for example:
  - `feat/day3-search`
  - `fix/voice-transcription-timeout`
  - `chore/ci-caching`

- **Commit messages:** Follow Conventional Commits:
  - `feat(day3): implement recruiter search endpoint`
  - `fix(voice): handle empty audio payload gracefully`
  - `chore: add CI, pre-commit, PR template and repo hygiene`

---

## PR Checklist

Before submitting a PR:

1. Ensure all tests and lint checks pass.
2. Verify diffs contain **no secrets, API keys, or personal data**.
3. Align with `.kiro/specs/` and `docs/scoring.md`.
4. Update `PROMPTS.md` if AI-assisted development tools were used.
