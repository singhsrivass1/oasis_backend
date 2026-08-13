-- Migration: adds automated fix-PR tracking to an existing Oasis database.
-- Safe to run once against your existing project (idempotent).

alter table public.findings add column if not exists fix_status text default 'not_attempted';
alter table public.findings add column if not exists fix_error text;
alter table public.findings add column if not exists fix_pr_number integer;
alter table public.findings add column if not exists fix_pr_url text;
alter table public.findings add column if not exists fix_branch text;

notify pgrst, 'reload schema';
