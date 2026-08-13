-- Migration: adds GitHub App support to an existing Oasis database.
-- Safe to run once against your existing project (idempotent).

create table if not exists public.github_installations (
  id uuid not null default uuid_generate_v4(),
  installation_id bigint not null unique,
  owner_id uuid,
  account_login text default ''::text,
  account_type text default 'User'::text,
  created_at timestamp with time zone default now(),
  constraint github_installations_pkey primary key (id),
  constraint github_installations_owner_id_fkey foreign key (owner_id) references public.users(id)
);

alter table public.repositories add column if not exists installation_id bigint;

notify pgrst, 'reload schema';
