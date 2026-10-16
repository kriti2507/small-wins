-- Phase 3, Part B: stored, revocable MCP grants.
--
-- Run ONCE against production in the Supabase SQL editor, BEFORE deploying
-- the Part B code. It only adds a table, so the currently deployed code is
-- unaffected, and it's safe to re-run.

create table if not exists mcp_grants (
  id            bigserial primary key,
  user_id       bigint not null references users(id) on delete cascade,
  client_name   text,
  redirect_host text not null,
  secret_hash   text not null,          -- sha256 hex of the secret
  created_at    timestamptz not null default now(),
  redeemed_at   timestamptz,
  last_used_at  timestamptz
);

-- No policies: Supabase's REST API can't touch it; Flask (the table owner)
-- is unaffected.
alter table mcp_grants enable row level security;
