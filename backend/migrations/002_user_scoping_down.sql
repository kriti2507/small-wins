-- Phase 2 rollback: reverses 002_user_scoping.sql.
--
-- Use ONLY if the Phase 2 deploy must be rolled back, and only BEFORE any
-- friend has their own data (this refuses to run otherwise -- restore from
-- backup instead). Redeploy the previous (pre-Phase-2) code immediately
-- after running this.
-- Paste the WHOLE file into the Supabase SQL editor and Run.

do $$
declare
  n int;
begin
  perform set_config('lock_timeout', '5s', true);

  select greatest(
    (select count(distinct user_id) from topics),
    (select count(distinct user_id) from entries),
    (select count(distinct user_id) from posts)
  ) into n;
  if n > 1 then
    raise exception 'Data belongs to more than one user; this rollback only works before other users are added.';
  end if;

  alter table posts drop constraint posts_user_id_topic_slug_entry_id_fkey;
  alter table posts drop constraint posts_pkey;
  alter table entries drop constraint entries_user_id_topic_slug_fkey;
  alter table entries drop constraint entries_pkey;
  alter table topics drop constraint topics_user_id_fkey;
  alter table topics drop constraint topics_pkey;

  alter table topics drop column user_id;
  alter table entries drop column user_id;
  alter table posts drop column user_id;

  alter table topics add constraint topics_pkey primary key (slug);
  alter table entries add constraint entries_pkey primary key (topic_slug, id);
  alter table entries add constraint entries_topic_slug_fkey
    foreign key (topic_slug) references topics(slug) on delete cascade;
  alter table posts add constraint posts_pkey primary key (topic_slug, entry_id);
  alter table posts add constraint posts_topic_slug_entry_id_fkey
    foreign key (topic_slug, entry_id) references entries(topic_slug, id) on delete cascade;
end $$;
