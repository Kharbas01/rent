-- ============================================================================
--  OPTIONAL DEMO DATA
--  Run AFTER schema.sql and AFTER you have created your first user.
--  It automatically attaches the sample data to the oldest user account.
-- ============================================================================

do $$
declare
  v_owner  uuid;
  v_flat   uuid;
  v_villa  uuid;
  v_shop   uuid;
  v_t1     uuid;
  v_t2     uuid;
  v_month  date := date_trunc('month', current_date)::date;
  v_prev   date := (date_trunc('month', current_date) - interval '1 month')::date;
begin
  select id into v_owner from auth.users order by created_at asc limit 1;

  if v_owner is null then
    raise notice 'No user found. Sign up in the app first, then run seed.sql again.';
    return;
  end if;

  -- Properties ---------------------------------------------------------------
  insert into public.properties (owner_id, name, type, address, monthly_rent, status)
  values (v_owner, 'Sunrise Apartment 302', 'Apartment', '302, Sunrise Towers, MG Road', 18000, 'Occupied')
  returning id into v_flat;

  insert into public.properties (owner_id, name, type, address, monthly_rent, status)
  values (v_owner, 'Green Villa', 'Villa', 'Plot 14, Green Park Colony', 42000, 'Occupied')
  returning id into v_villa;

  insert into public.properties (owner_id, name, type, address, monthly_rent, status)
  values (v_owner, 'Main Street Shop 7', 'Commercial', 'Shop 7, Main Street Market', 25000, 'Vacant')
  returning id into v_shop;

  -- Tenants ------------------------------------------------------------------
  insert into public.tenants (owner_id, property_id, name, phone, email, rent_amount,
                              security_deposit, agreement_start, agreement_end, is_active)
  values (v_owner, v_flat, 'Rahul Sharma', '9876543210', 'rahul.sharma@example.com',
          18000, 36000, v_prev - interval '5 month', v_prev + interval '7 month', true)
  returning id into v_t1;

  insert into public.tenants (owner_id, property_id, name, phone, email, rent_amount,
                              security_deposit, agreement_start, agreement_end, is_active)
  values (v_owner, v_villa, 'Priya Nair', '9812345678', 'priya.nair@example.com',
          42000, 84000, v_prev - interval '2 month', v_prev + interval '10 month', true)
  returning id into v_t2;

  -- Payments -----------------------------------------------------------------
  insert into public.payments (owner_id, tenant_id, property_id, period_month, amount_due,
                               amount_paid, status, payment_date, payment_method)
  values
    (v_owner, v_t1, v_flat,  v_prev,  18000, 18000, 'Paid',    v_prev + 4,  'UPI'),
    (v_owner, v_t2, v_villa, v_prev,  42000, 42000, 'Paid',    v_prev + 2,  'Bank Transfer'),
    (v_owner, v_t1, v_flat,  v_month, 18000, 10000, 'Partial', v_month + 3, 'Cash'),
    (v_owner, v_t2, v_villa, v_month, 42000, 0,     'Pending', null,        null)
  on conflict (tenant_id, period_month) do nothing;

  raise notice 'Demo data inserted for user %', v_owner;
end $$;
