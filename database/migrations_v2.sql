-- ============================================================================
--  RENT MANAGEMENT SYSTEM - MIGRATION v2
--  Adds: tenant due date, agreement duration, rent increase %, payment type.
--  Run this file in: Supabase Dashboard -> SQL Editor -> New Query -> Run
--  Safe to re-run: every statement uses IF NOT EXISTS / OR REPLACE guards.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- TENANTS: due date, agreement duration, rent increase percentage
-- ----------------------------------------------------------------------------
alter table public.tenants
  add column if not exists due_day_of_month smallint not null default 1;

alter table public.tenants
  add column if not exists agreement_duration_months integer;

alter table public.tenants
  add column if not exists rent_increase_percentage numeric(5,2) not null default 0.00;

-- CHECK constraints (dropped first so this script is safely re-runnable)
alter table public.tenants drop constraint if exists tenants_due_day_range;
alter table public.tenants
  add constraint tenants_due_day_range check (due_day_of_month between 1 and 31);

alter table public.tenants drop constraint if exists tenants_agreement_duration_positive;
alter table public.tenants
  add constraint tenants_agreement_duration_positive check (
    agreement_duration_months is null or agreement_duration_months > 0
  );

alter table public.tenants drop constraint if exists tenants_rent_increase_range;
alter table public.tenants
  add constraint tenants_rent_increase_range check (
    rent_increase_percentage >= 0 and rent_increase_percentage <= 100
  );

-- ----------------------------------------------------------------------------
-- PAYMENTS: payment type (Cash / Online / Hybrid) + optional breakdown note
-- ----------------------------------------------------------------------------
alter table public.payments
  add column if not exists payment_type text not null default 'Cash';

alter table public.payments
  add column if not exists payment_type_note text;

alter table public.payments drop constraint if exists payments_payment_type_valid;
alter table public.payments
  add constraint payments_payment_type_valid check (
    payment_type in ('Cash', 'Online', 'Hybrid')
  );

-- ============================================================================
-- ROW LEVEL SECURITY: unaffected. Existing policies on tenants/payments
-- already scope every row to auth.uid() = owner_id, and new columns are
-- covered automatically since RLS is row-level, not column-level.
-- No new policies are required by this migration.
-- ============================================================================

-- ============================================================================
-- DONE
-- ============================================================================