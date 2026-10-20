create table users (
  id          bigserial primary key,
  google_sub  text unique not null,
  email       text not null,
  name        text,
  avatar_url  text,
  -- Onboarding tips this person has dismissed (see frontend/src/lib/tips.ts).
  tips_seen   text[] not null default '{}',
  created_at  timestamptz not null default now()
);

-- Every row below belongs to one user; slugs and entry ids are unique per
-- user, not globally. Deleting a user cascades to all their data.
create table topics (
  user_id  bigint not null references users(id) on delete cascade,
  slug     text   not null,
  name     text   not null,
  color    text   not null,
  layout   text   not null,
  fields   jsonb  not null default '[]'::jsonb,
  position integer not null,
  primary key (user_id, slug)
);

create table entries (
  user_id    bigint  not null,
  topic_slug text    not null,
  id         integer not null,
  date       text    not null default '',
  image      text,
  "values"   jsonb   not null default '{}'::jsonb,
  primary key (user_id, topic_slug, id),
  foreign key (user_id, topic_slug) references topics(user_id, slug) on delete cascade
);

create table posts (
  user_id    bigint  not null,
  topic_slug text    not null,
  entry_id   integer not null,
  doc        jsonb   not null,
  primary key (user_id, topic_slug, entry_id),
  foreign key (user_id, topic_slug, entry_id)
    references entries(user_id, topic_slug, id) on delete cascade
);

-- One row per connected MCP app (see backend/grants.py). Only a sha256 of
-- the app's secret is kept. Revoking the app deletes the row.
create table mcp_grants (
  id            bigserial primary key,
  user_id       bigint not null references users(id) on delete cascade,
  client_name   text,
  redirect_host text not null,
  secret_hash   text not null,
  created_at    timestamptz not null default now(),
  redeemed_at   timestamptz,
  last_used_at  timestamptz
);

-- RLS on with no policies: Supabase's auto-generated REST API can't read or
-- write these tables. Flask connects as the table owner, which RLS doesn't
-- apply to, so the app is unaffected; its per-user filtering is in db.py.
alter table users   enable row level security;
alter table topics  enable row level security;
alter table entries enable row level security;
alter table posts   enable row level security;
alter table mcp_grants enable row level security;
