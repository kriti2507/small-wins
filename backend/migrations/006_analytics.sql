-- Analytics: record when and how each entry was logged, where each person
-- first came from, and when they last opened the app. backend/analytics.sql
-- has the queries that read these.
--
-- Run ONCE against production in the Supabase SQL editor, BEFORE deploying
-- the analytics code. Every column is new and nullable or defaulted, so the
-- code that's live now keeps working against it; rolling the code back later
-- never requires undoing this.
--
-- Existing entries get created_at = the time this runs and via = null, and
-- existing users get null source and last-seen: history starts from today.
--
-- Safe to re-run: each column is only added if it isn't there yet.

alter table entries add column if not exists created_at timestamptz not null default now();
alter table entries add column if not exists via        text;  -- 'web' or 'mcp'
alter table users   add column if not exists signup_source text;
alter table users   add column if not exists last_seen_at  timestamptz;
