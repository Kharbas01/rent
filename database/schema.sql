-- ============================================================================
--  RENT MANAGEMENT SYSTEM - DATABASE SCHEMA
--  Run this file in: Supabase Dashboard -> SQL Editor -> New Query -> Run
-- ============================================================================

create extension if not exists "pgcrypto";

-- ----------------------------------------------------------------------------
-- Helper: keep updated_at fresh
-- ----------------------------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;

$$;

-- ============================================================================
-- 1. PROFILES  (one row per authenticated user)
-- ============================================================================
create table if not exists public.profiles (
  id           uuid primary key references auth.users(id) on delete cascade,
  full_name    text,
  company_name text,
  phone        text,
  currency     text not null default 'INR',
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);

-- ============================================================================
-- 2. PROPERTIES
-- ============================================================================
create table if not exists public.properties (
  id            uuid primary key default gen_random_uuid(),
  owner_id      uuid not null references auth.users(id) on delete cascade,
  name          text not null,
  type          text not null default 'Apartment',
  address       text,
  monthly_rent  numeric(12,2) not null default 0 check (monthly_rent >= 0),
  status        text not null default 'Vacant' check (status in ('Occupied','Vacant')),
  notes         text,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

-- ============================================================================
-- 3. TENANTS
-- ============================================================================
create table if not exists public.tenants (
  id               uuid primary key default gen_random_uuid(),
  owner_id         uuid not null references auth.users(id) on delete cascade,
  property_id      uuid references public.properties(id) on delete set null,
  name             text not null,
  phone            text,
  email            text,
  rent_amount      numeric(12,2) not null default 0 check (rent_amount >= 0),
  security_deposit numeric(12,2) not null default 0 check (security_deposit >= 0),
  agreement_start  date,
  agreement_end    date,
  is_active        boolean not null default true,
  notes            text,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),
  constraint tenants_agreement_range check (
    agreement_end is null or agreement_start is null or agreement_end >= agreement_start
  )
);

-- ============================================================================
-- 4. PAYMENTS  (one row per tenant per rent month)
-- ============================================================================
create table if not exists public.payments (
  id             uuid primary key default gen_random_uuid(),
  owner_id       uuid not null references auth.users(id) on delete cascade,
  tenant_id      uuid not null references public.tenants(id) on delete cascade,
  property_id    uuid references public.properties(id) on delete set null,
  period_month   date not null,
  amount_due     numeric(12,2) not null default 0 check (amount_due >= 0),
  amount_paid    numeric(12,2) not null default 0 check (amount_paid >= 0),
  status         text not null default 'Pending' check (status in ('Pending','Partial','Paid')),
  payment_date   date,
  payment_method text check (
    payment_method is null
    or payment_method in ('Cash','Bank Transfer','UPI','Card','Cheque','Other')
  ),
  notes          text,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),
  constraint payments_unique_month unique (tenant_id, period_month)
);

-- ============================================================================
-- INDEXES
-- ============================================================================
create index if not exists idx_properties_owner   on public.properties(owner_id);
create index if not exists idx_properties_status  on public.properties(owner_id, status);
create index if not exists idx_tenants_owner      on public.tenants(owner_id);
create index if not exists idx_tenants_property   on public.tenants(property_id);
create index if not exists idx_payments_owner     on public.payments(owner_id);
create index if not exists idx_payments_tenant    on public.payments(tenant_id);
create index if not exists idx_payments_period    on public.payments(owner_id, period_month desc);
create index if not exists idx_payments_status    on public.payments(owner_id, status);

-- ============================================================================
-- UPDATED_AT TRIGGERS
-- ============================================================================
drop trigger if exists trg_profiles_updated   on public.profiles;
drop trigger if exists trg_properties_updated on public.properties;
drop trigger if exists trg_tenants_updated    on public.tenants;
drop trigger if exists trg_payments_updated   on public.payments;

create trigger trg_profiles_updated   before update on public.profiles
  for each row execute function public.set_updated_at();
create trigger trg_properties_updated before update on public.properties
  for each row execute function public.set_updated_at();
create trigger trg_tenants_updated    before update on public.tenants
  for each row execute function public.set_updated_at();
create trigger trg_payments_updated   before update on public.payments
  for each row execute function public.set_updated_at();

-- ============================================================================
-- AUTO-CREATE A PROFILE WHEN A USER SIGNS UP
-- ============================================================================
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, full_name)
  values (
    new.id,
    coalesce(new.raw_user_meta_data ->> 'full_name', split_part(new.email, '@', 1))
  )
  on conflict (id) do nothing;
  return new;
end;

$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ============================================================================
-- ROW LEVEL SECURITY  (every user only ever sees their own data)
-- ============================================================================
alter table public.profiles   enable row level security;
alter table public.properties enable row level security;
alter table public.tenants    enable row level security;
alter table public.payments   enable row level security;

-- PROFILES ------------------------------------------------------------------
drop policy if exists "profiles_select_own" on public.profiles;
drop policy if exists "profiles_insert_own" on public.profiles;
drop policy if exists "profiles_update_own" on public.profiles;

create policy "profiles_select_own" on public.profiles
  for select using (auth.uid() = id);
create policy "profiles_insert_own" on public.profiles
  for insert with check (auth.uid() = id);
create policy "profiles_update_own" on public.profiles
  for update using (auth.uid() = id) with check (auth.uid() = id);

-- PROPERTIES ----------------------------------------------------------------
drop policy if exists "properties_select_own" on public.properties;
drop policy if exists "properties_insert_own" on public.properties;
drop policy if exists "properties_update_own" on public.properties;
drop policy if exists "properties_delete_own" on public.properties;

create policy "properties_select_own" on public.properties
  for select using (auth.uid() = owner_id);
create policy "properties_insert_own" on public.properties
  for insert with check (auth.uid() = owner_id);
create policy "properties_update_own" on public.properties
  for update using (auth.uid() = owner_id) with check (auth.uid() = owner_id);
create policy "properties_delete_own" on public.properties
  for delete using (auth.uid() = owner_id);

-- TENANTS -------------------------------------------------------------------
drop policy if exists "tenants_select_own" on public.tenants;
drop policy if exists "tenants_insert_own" on public.tenants;
drop policy if exists "tenants_update_own" on public.tenants;
drop policy if exists "tenants_delete_own" on public.tenants;

create policy "tenants_select_own" on public.tenants
  for select using (auth.uid() = owner_id);
create policy "tenants_insert_own" on public.tenants
  for insert with check (auth.uid() = owner_id);
create policy "tenants_update_own" on public.tenants
  for update using (auth.uid() = owner_id) with check (auth.uid() = owner_id);
create policy "tenants_delete_own" on public.tenants
  for delete using (auth.uid() = owner_id);

-- PAYMENTS ------------------------------------------------------------------
drop policy if exists "payments_select_own" on public.payments;
drop policy if exists "payments_insert_own" on public.payments;
drop policy if exists "payments_update_own" on public.payments;
drop policy if exists "payments_delete_own" on public.payments;

create policy "payments_select_own" on public.payments
  for select using (auth.uid() = owner_id);
create policy "payments_insert_own" on public.payments
  for insert with check (auth.uid() = owner_id);
create policy "payments_update_own" on public.payments
  for update using (auth.uid() = owner_id) with check (auth.uid() = owner_id);
create policy "payments_delete_own" on public.payments
  for delete using (auth.uid() = owner_id);

-- ============================================================================
-- DONE
-- ============================================================================
