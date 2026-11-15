-- WP-07 prerequisite: canonical Stripe subscription entitlement projection.
-- Schema only: no Stripe products/prices/subscriptions are seeded or activated.
begin;

create table if not exists public.billing_products (
  id uuid primary key default gen_random_uuid(),
  product_key text not null unique check (product_key ~ '^[a-z0-9][a-z0-9._-]{1,79}$'),
  name text not null check (char_length(name) between 1 and 160),
  description text check (description is null or char_length(description) <= 1000),
  purpose text not null check (purpose in ('ai_credit_topup','premium_subscription')),
  product_approval_reference text not null check (char_length(product_approval_reference) between 3 and 160),
  stripe_price_id text not null unique check (stripe_price_id ~ '^price_[A-Za-z0-9]+$'),
  stripe_mode text not null check (stripe_mode in ('payment','subscription')),
  amount_minor bigint not null check (amount_minor > 0),
  currency text not null check (currency ~ '^[a-z]{3}$'),
  billing_interval text check (billing_interval is null or billing_interval in ('day','week','month','year')),
  credits_grant bigint not null default 0 check (credits_grant >= 0),
  monthly_credits_grant bigint not null default 0 check (monthly_credits_grant >= 0),
  credit_policy_version text references public.credit_policy_versions(policy_version) on delete restrict,
  credit_policy_approval_reference text,
  plan_key text,
  entitlement_version text,
  status text not null default 'draft' check (status in ('draft','active','retired')),
  sort_order integer not null default 100,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (
    (purpose = 'ai_credit_topup' and stripe_mode = 'payment' and credits_grant > 0
      and monthly_credits_grant = 0 and credit_policy_version is not null
      and credit_policy_approval_reference is not null and plan_key is null)
    or
    (purpose = 'premium_subscription' and stripe_mode = 'subscription'
      and credits_grant = 0 and monthly_credits_grant > 0
      and credit_policy_version is not null and credit_policy_approval_reference is not null
      and plan_key is not null and entitlement_version is not null)
  )
);

create table if not exists public.billing_subscriptions (
  id uuid primary key default gen_random_uuid(),
  owner_user_id uuid not null references auth.users(id) on delete restrict,
  product_id uuid not null references public.billing_products(id) on delete restrict,
  stripe_subscription_id text not null unique,
  stripe_customer_id text,
  plan_key text not null,
  entitlement_version text not null,
  status text not null check (status in ('active','past_due','canceled','unpaid','incomplete','incomplete_expired','paused','trialing')),
  current_period_start timestamptz,
  current_period_end timestamptz,
  cancel_at_period_end boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists billing_subscriptions_owner_updated_idx
  on public.billing_subscriptions(owner_user_id,updated_at desc);

alter table public.billing_products enable row level security;
alter table public.billing_subscriptions enable row level security;
revoke all on public.billing_products,public.billing_subscriptions
  from public,anon,authenticated,service_role;
grant select,insert,update,delete on public.billing_products,public.billing_subscriptions
  to service_role;

comment on table public.billing_subscriptions is
  'Server-verified Stripe subscription projection. No entitlement is active until a verified billing event creates or updates the row.';

commit;