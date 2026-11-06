-- Database layout for the deal-alert bot.
-- Paste this whole file into Supabase: SQL Editor -> New query -> Run.

-- One row per person who receives alerts.
create table people (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  code text unique not null,          -- "login" code the person types in the app
  ntfy_topic text unique not null,    -- secret ntfy channel name
  whatsapp_enabled boolean not null default false,
  whatsapp_phone text,
  whatsapp_apikey text,
  created_at timestamptz not null default now()
);

-- Product tags, e.g. "rtx 5060 ti".
create table tags (
  id bigint generated always as identity primary key,
  person_id uuid not null references people(id) on delete cascade,
  text text not null,
  blocked_words text[] not null default '{}',
  max_price numeric,
  absurd_alert boolean not null default false,
  market_price numeric,
  limit_pct integer not null default 50 check (limit_pct between 1 and 100)
);

-- Categories a person follows, e.g. "computers" with 50% min discount.
create table followed_categories (
  id bigint generated always as identity primary key,
  person_id uuid not null references people(id) on delete cascade,
  category text not null check (category in ('computers', 'games', 'phones', 'electronics')),
  min_discount_pct numeric,
  min_temperature integer
);

-- Deals already sent to each person (so nobody gets the same alert twice).
create table sent_alerts (
  person_id uuid not null references people(id) on delete cascade,
  deal_id text not null,
  sent_at timestamptz not null default now(),
  primary key (person_id, deal_id)
);

-- The "heartbeat": when the bot last ran and where (PC or GitHub Actions).
create table bot_status (
  id integer primary key default 1 check (id = 1),  -- only one row ever
  last_run timestamptz,
  runner text
);
insert into bot_status (id) values (1);

-- Security: lock every table. Nobody with the public key can read or write.
-- The bot uses the secret key, which skips these locks.
-- The app (Phase 6) will get its own safe doors later.
alter table people enable row level security;
alter table tags enable row level security;
alter table followed_categories enable row level security;
alter table sent_alerts enable row level security;
alter table bot_status enable row level security;
