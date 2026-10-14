-- Phase 2: give every topic, entry and post an owner.
--
-- Run ONCE against production, in the Supabase SQL editor:
--   1. Take a backup (Database -> Backups), or confirm a recent one exists.
--   2. Sign in to the live app once with the owner's Google account, so
--      their users row exists.
--   3. Have the Phase 2 deploy ready to go: the currently deployed (old)
--      code breaks as soon as this runs, so deploy immediately after.
--   4. Paste the WHOLE file into the SQL editor (don't run a highlighted
--      part), replace you@example.com below with the owner's email, Run.
-- Supabase may ask you to confirm a destructive operation (the
-- `drop constraint`s below) -- that's expected.
-- The whole file is one statement: if anything fails, nothing changes. An
-- error such as "constraint ... does not exist" means production's
-- constraint names differ from the ones below -- stop and ask rather than
-- editing and re-running blind.
-- Afterwards, sanity-check with:
--   select count(*), count(distinct user_id) from topics;
-- (the distinct count should be 1).

do $$
declare
  owner_email constant text := 'you@example.com';
  owner_id bigint;
  n int;
begin
  perform set_config('lock_timeout', '5s', true);

  select count(*) into n from users where lower(email) = lower(owner_email);
  if n = 0 then
    raise exception 'No user with email %. Sign in once with that account first.', owner_email;
  end if;
  if n > 1 then
    raise exception 'More than one user has email %; resolve that before migrating.', owner_email;
  end if;
  select id into owner_id from users where lower(email) = lower(owner_email);

  -- Old keys go first: the foreign keys depend on the primary keys.
  alter table posts drop constraint posts_topic_slug_entry_id_fkey;
  alter table entries drop constraint entries_topic_slug_fkey;
  alter table posts drop constraint posts_pkey;
  alter table entries drop constraint entries_pkey;
  alter table topics drop constraint topics_pkey;

  alter table topics add column user_id bigint references users(id) on delete cascade;
  alter table entries add column user_id bigint;
  alter table posts add column user_id bigint;

  update topics set user_id = owner_id;
  update entries set user_id = owner_id;
  update posts set user_id = owner_id;

  alter table topics alter column user_id set not null;
  alter table entries alter column user_id set not null;
  alter table posts alter column user_id set not null;

  alter table topics add primary key (user_id, slug);
  alter table entries add primary key (user_id, topic_slug, id);
  alter table entries add foreign key (user_id, topic_slug)
    references topics(user_id, slug) on delete cascade;
  alter table posts add primary key (user_id, topic_slug, entry_id);
  alter table posts add foreign key (user_id, topic_slug, entry_id)
    references entries(user_id, topic_slug, id) on delete cascade;
end $$;
