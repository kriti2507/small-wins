-- Phase 2: give every topic, entry and post an owner.
--
-- Run ONCE against production, in the Supabase SQL editor, BEFORE deploying
-- the Phase 2 code:
--   1. Take a backup (Database -> Backups) or note the latest one.
--   2. Sign in to the app once with the owner's Google account, so their
--      users row exists.
--   3. Replace you@example.com below with that account's email. Run.
-- The whole file is one statement: if anything fails, nothing changes.

do $$
declare
  owner_email constant text := 'you@example.com';
  owner_id bigint;
begin
  select id into owner_id from users where lower(email) = lower(owner_email);
  if owner_id is null then
    raise exception 'No user with email %. Sign in once with that account first.', owner_email;
  end if;

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
