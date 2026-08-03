-- ============================================================================
--  RENT MANAGEMENT SYSTEM - MIGRATION v3
--  Adds: agreements table (property-wise / tenant-wise document storage,
--  backed by Google Drive via a service account).
--  Run this file in: Supabase Dashboard -> SQL Editor -> New Query -> Run
-- ============================================================================

create table if not exists public.agreements (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  property_id uuid references public.properties(id) on delete set null,
  tenant_id uuid references public.tenants(id) on delete set null,

  file_name text not null,               -- stored / renamed file name
  original_file_name text,               -- name as uploaded by the user
  drive_file_id text,                    -- Google Drive file ID
  drive_link text,                       -- Google Drive shareable link
  file_size bigint default 0,            -- bytes
  page_count integer default 1,

  agreement_start date,
  agreement_end date,
  notes text,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists agreements_owner_idx on public.agreements(owner_id);
create index if not exists agreements_property_idx on public.agreements(property_id);
create index if not exists agreements_tenant_idx on public.agreements(tenant_id);

-- Keep updated_at fresh on every change
create or replace function public.set_agreements_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_agreements_updated_at on public.agreements;
create trigger trg_agreements_updated_at
  before update on public.agreements
  for each row execute function public.set_agreements_updated_at();

-- ----------------------------------------------------------------------------
-- Row Level Security — same pattern as every other table in this project
-- ----------------------------------------------------------------------------
alter table public.agreements enable row level security;

drop policy if exists "agreements_select_own" on public.agreements;
create policy "agreements_select_own" on public.agreements
  for select using (auth.uid() = owner_id);

drop policy if exists "agreements_insert_own" on public.agreements;
create policy "agreements_insert_own" on public.agreements
  for insert with check (auth.uid() = owner_id);

drop policy if exists "agreements_update_own" on public.agreements;
create policy "agreements_update_own" on public.agreements
  for update using (auth.uid() = owner_id);

drop policy if exists "agreements_delete_own" on public.agreements;
create policy "agreements_delete_own" on public.agreements
  for delete using (auth.uid() = owner_id);

-- ============================================================================
-- DONE — status (Active / Expiring Soon / Expired) is computed by the
-- backend from agreement_end, not stored, so it always reflects "today".
-- ============================================================================