-- Migration 010_subscriptions.sql
-- Accommodate Stripe subscriptions and Pro tier status

-- 1. Add subscription columns to profiles if they do not exist
alter table public.profiles
  add column if not exists subscription_tier text not null default 'free'
    check (subscription_tier in ('free', 'student_pro', 'recruiter_pro', 'officer_pro', 'company_pro')),
  add column if not exists stripe_customer_id text,
  add column if not exists stripe_subscription_id text;

-- 2. Dedicated subscriptions table
create table if not exists public.subscriptions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  plan text not null check (plan in ('student_pro', 'recruiter_pro', 'officer_pro', 'company_pro')),
  billing_interval text not null default 'month' check (billing_interval in ('month', 'year')),
  status text not null default 'active',
  stripe_customer_id text,
  stripe_subscription_id text,
  current_period_end timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Index for fast user subscription lookup
create index if not exists idx_subscriptions_user_id on public.subscriptions(user_id);
create index if not exists idx_subscriptions_status on public.subscriptions(status);

-- Enable RLS
alter table public.subscriptions enable row level security;

-- Policy: Users can view their own subscription
drop policy if exists "Users can view own subscription" on public.subscriptions;
create policy "Users can view own subscription"
  on public.subscriptions
  for select
  to authenticated
  using (auth.uid() = user_id);

-- Policy: Service role has full access (for webhooks & server actions)
drop policy if exists "Service role full access on subscriptions" on public.subscriptions;
create policy "Service role full access on subscriptions"
  on public.subscriptions
  for all
  to service_role
  using (true)
  with check (true);

-- Updated_at trigger for subscriptions table
drop trigger if exists tr_subscriptions_updated_at on public.subscriptions;
create trigger tr_subscriptions_updated_at
  before update on public.subscriptions
  for each row execute function public.set_updated_at();
