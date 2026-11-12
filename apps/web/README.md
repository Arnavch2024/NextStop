# Recruiting Platform Web (`apps/web`)

Responsive web application built with **Next.js 14 (App Router)**, **React 18**, **Tailwind CSS**, and **Supabase Auth**.

---

## Features

- **Persona Dashboards**: Specialized portals for Students, Placement Officers, Companies, and Recruiters.
- **Dedicated Demo Portal (`/demo`)**: Instant one-click persona switcher and sandbox login without credential entry.
- **Interactive Conversational UI**: Role-customized chat suggestions, live markdown rendering, voice recording support, and instant data upserting.
- **Student Roster Management**: Placement Officer CSV imports and batch sharing toggles.
- **Company Candidate Explorer**: CGPA and branch filtering respecting student privacy and consent opt-outs.

---

## Quickstart

### 1. Prerequisites

- Node.js ≥ 20
- pnpm ≥ 9

### 2. Environment Configuration

Create `.env.local` in `apps/web`:

```ini
NEXT_PUBLIC_SUPABASE_URL=https://bsegerbrkbxnosyojmwf.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOi...
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_DEMO_ENABLED=true
```

### 3. Run Development Server

```bash
pnpm dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## Vercel Deployment

Configured via `apps/web/vercel.json`:

- **Root Directory**: `apps/web`
- **Build Command**: `cd ../.. && pnpm --filter @recruiting/shared build && pnpm --filter @recruiting/web build`
- **Output Directory**: `.next`
