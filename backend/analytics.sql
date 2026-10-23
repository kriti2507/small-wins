-- Analytics queries. Paste one at a time into the Supabase SQL editor (save
-- the ones you use as snippets there). Read-only: nothing here changes data.
--
-- What the columns mean (added by migrations/006_analytics.sql):
--   users.signup_source  where they first came from: utm_source, ?ref=, the
--                        referring site, or 'direct'. Null = signed up before
--                        tracking, or no browser storage.
--   users.last_seen_at   last sign-in or app open.
--   entries.created_at   when the entry was logged (entries.date is the day
--                        the person picked, which can be in the past).
--   entries.via          'web' or 'mcp' (a connected app like Claude). Null =
--                        logged before tracking.
-- Entries logged before the migration all share its created_at, so ignore
-- that one day in the daily numbers.


-- 1. Headline numbers
select
  (select count(*) from users)                                                    as users,
  (select count(*) from users where created_at > now() - interval '7 days')       as new_this_week,
  (select count(*) from users where last_seen_at > now() - interval '1 day')      as seen_today,
  (select count(*) from users where last_seen_at > now() - interval '7 days')     as seen_this_week,
  (select count(distinct user_id) from entries
     where created_at > now() - interval '7 days')                                 as logged_this_week;


-- 2. Sign-ups per day
select created_at::date as day, count(*) as signups
from users
group by 1 order by 1 desc
limit 60;


-- 3. Where people came from
select coalesce(signup_source, '(unknown)') as source, count(*) as users
from users
group by 1 order by 2 desc;


-- 4. People logging something each day, and how
select created_at::date as day,
       count(distinct user_id)                               as people_logging,
       count(*)                                              as entries,
       count(*) filter (where via = 'web')                   as via_web,
       count(*) filter (where via = 'mcp')                   as via_mcp
from entries
group by 1 order by 1 desc
limit 60;


-- 5. Web vs connected app, per person (who uses Claude to log?)
select u.email,
       count(*) filter (where e.via = 'web') as via_web,
       count(*) filter (where e.via = 'mcp') as via_mcp,
       max(e.created_at)                     as last_logged
from entries e join users u on u.id = e.user_id
group by u.email order by last_logged desc nulls last;


-- 6. What people track: topics by name, with how many people have one and
-- how many entries they hold. 'workout' and 'journal' are the starter topics.
select t.name,
       count(distinct t.user_id) as people,
       count(e.id)               as entries
from topics t
left join entries e on e.user_id = t.user_id and e.topic_slug = t.slug
group by t.name order by people desc, entries desc;


-- 7. Which kinds of fields people add (text, number, pace, ...)
select f->>'type' as field_type,
       count(*)   as fields,
       count(distinct t.user_id) as people
from topics t, jsonb_array_elements(t.fields) f
group by 1 order by 2 desc;


-- 8. Connected apps
select coalesce(client_name, '(unnamed)') as app,
       count(*)                           as connections,
       count(*) filter (where last_used_at > now() - interval '7 days') as used_this_week
from mcp_grants
where redeemed_at is not null
group by 1 order by 2 desc;


-- 9. Retention: of each week's sign-ups, how many logged something 7+ days
-- after signing up.
select date_trunc('week', u.created_at)::date as signup_week,
       count(*) as signups,
       count(*) filter (where exists (
         select 1 from entries e
         where e.user_id = u.id and e.created_at > u.created_at + interval '7 days'
       )) as still_logging_after_a_week
from users u
group by 1 order by 1 desc;
