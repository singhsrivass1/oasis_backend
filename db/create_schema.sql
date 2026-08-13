-- Oasis schema setup. Safe to run even if some tables already exist.
create extension if not exists "uuid-ossp";
create extension if not exists "pgcrypto";

create table if not exists public.users (
  id uuid not null default uuid_generate_v4(),
  name text not null,
  email text not null unique,
  password_hash text,
  org text default 'My Organization'::text,
  plan text default 'starter'::text check (plan = any (array['starter'::text, 'professional'::text, 'enterprise'::text])),
  avatar text default ''::text,
  google_id text unique,
  github_id text unique,
  github_username text default ''::text,
  github_repos integer default 0,
  github_followers integer default 0,
  auth_provider text default 'local'::text check (auth_provider = any (array['local'::text, 'google'::text, 'github'::text])),
  created_at timestamp with time zone default now(),
  updated_at timestamp with time zone default now(),
  constraint users_pkey primary key (id)
);

create table if not exists public.repositories (
  id uuid not null default uuid_generate_v4(),
  owner_id uuid not null,
  name text not null,
  full_name text not null,
  language text default 'TypeScript'::text,
  status text default 'secure'::text check (status = any (array['secure'::text, 'reviewing'::text, 'attention'::text])),
  score numeric default 95 check (score >= 0::numeric and score <= 100::numeric),
  prs_reviewed integer default 0,
  issues_open integer default 0,
  last_event timestamp with time zone default now(),
  created_at timestamp with time zone default now(),
  constraint repositories_pkey primary key (id),
  constraint repositories_owner_id_fkey foreign key (owner_id) references public.users(id)
);

create table if not exists public.findings (
  id uuid not null default uuid_generate_v4(),
  owner_id uuid not null,
  repo_id uuid,
  repo_name text not null,
  title text not null,
  location text default ''::text,
  severity text default 'medium'::text check (severity = any (array['critical'::text, 'high'::text, 'medium'::text, 'low'::text, 'advisory'::text])),
  status text default 'open'::text check (status = any (array['open'::text, 'awaiting_approval'::text, 'approved'::text, 'dismissed'::text, 'resolved'::text])),
  patch_filename text default ''::text,
  patch_diff text default ''::text,
  patch_pr_number integer,
  patch_pr_title text default ''::text,
  patch_pr_branch text default ''::text,
  resolved_at timestamp with time zone,
  approved_at timestamp with time zone,
  dismissed_at timestamp with time zone,
  created_at timestamp with time zone default now(),
  fix_status text default 'not_attempted'::text,
  fix_error text,
  fix_pr_number integer,
  fix_pr_url text,
  fix_branch text,
  constraint findings_pkey primary key (id),
  constraint findings_owner_id_fkey foreign key (owner_id) references public.users(id),
  constraint findings_repo_id_fkey foreign key (repo_id) references public.repositories(id)
);

create table if not exists public.oasis_findings (
  id uuid not null default gen_random_uuid(),
  repo_name text not null,
  pr_number integer not null,
  pr_author text,
  status text default 'pending'::text,
  severity text,
  file_path text,
  line_number integer,
  description text,
  patch_content text,
  created_at timestamp with time zone default timezone('utc'::text, now()),
  owner_id uuid,
  repo_id uuid,
  title text default ''::text,
  location text default ''::text,
  patch_filename text default ''::text,
  patch_diff text default ''::text,
  patch_pr_number integer,
  patch_pr_title text default ''::text,
  patch_pr_branch text default ''::text,
  resolved_at timestamp with time zone,
  approved_at timestamp with time zone,
  dismissed_at timestamp with time zone,
  constraint oasis_findings_pkey primary key (id),
  constraint oasis_findings_owner_id_fkey foreign key (owner_id) references auth.users(id),
  constraint oasis_findings_repo_id_fkey foreign key (repo_id) references public.repositories(id)
);

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

create table if not exists public.activity (
  id uuid not null default uuid_generate_v4(),
  owner_id uuid not null,
  title text not null,
  meta text default ''::text,
  color text default '#4ade80'::text,
  created_at timestamp with time zone default now(),
  constraint activity_pkey primary key (id),
  constraint activity_owner_id_fkey foreign key (owner_id) references public.users(id)
);

-- Make sure PostgREST picks up the new tables immediately.
notify pgrst, 'reload schema';
