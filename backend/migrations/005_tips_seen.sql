-- Onboarding tips: remember which tips each person has dismissed.
--
-- Run ONCE against production in the Supabase SQL editor, BEFORE deploying
-- the onboarding-tips code. Everyone who already has an account is marked as
-- having seen every tip, so only new sign-ups get the tour.
--
-- Safe to re-run: the column is added (and existing users marked) only if it
-- doesn't exist yet, so people who signed up since keep their real progress.

do $$
begin
  if not exists (
    select 1 from information_schema.columns
    where table_name = 'users' and column_name = 'tips_seen'
      and table_schema = current_schema()
  ) then
    alter table users add column tips_seen text[] not null default '{}';
    update users set tips_seen = array['starter', 'log', 'connect'];
  end if;
end $$;
