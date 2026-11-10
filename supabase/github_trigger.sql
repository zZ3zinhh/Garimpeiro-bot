-- OPTIONAL, but the fix that makes the GitHub backup reliable.
--
-- Problem: GitHub's own timer ("schedule") skips most runs (about 5 a day instead of 96).
-- Fix: Supabase has its own reliable timer (pg_cron). Every 5 minutes it looks at the
-- heartbeat, and only if the PC has been silent for 20+ minutes it tells GitHub to
-- start the backup (workflow_dispatch). Nothing runs while your PC is working.
--
-- Before running this file:
--   1) In Supabase: Database -> Extensions -> turn ON "pg_cron" and "pg_net".
--   2) On GitHub, create a token ONLY for this repository:
--        github.com -> your photo -> Settings -> Developer settings -> Personal access tokens
--        -> Fine-grained tokens -> Generate new token
--        * Repository access: "Only select repositories" -> Garimpeiro-bot
--        * Permissions -> Repository permissions -> Actions: "Read and write"
--        * Expiration: the longest allowed (you will need a new one when it ends)
--   3) Paste the token below, replacing PASTE_YOUR_TOKEN_HERE (keep the quotes).
--      The token stays inside YOUR database. Never send it to anyone (not even to me).

create extension if not exists pg_net;
create extension if not exists pg_cron;

create or replace function private_trigger_github_backup()
returns void
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  v_last timestamptz;
  v_token text := 'PASTE_YOUR_TOKEN_HERE';
begin
  select last_run into v_last from bot_status where id = 1;
  if v_last is not null and v_last > now() - interval '20 minutes' then
    return;  -- the PC is working, nothing to do
  end if;
  perform net.http_post(
    url := 'https://api.github.com/repos/zZ3zinhh/Garimpeiro-bot/actions/workflows/backup-bot.yml/dispatches',
    headers := jsonb_build_object(
      'Authorization', 'Bearer ' || v_token,
      'Accept', 'application/vnd.github+json',
      'User-Agent', 'garimpeiro-supabase'
    ),
    body := '{"ref":"main"}'::jsonb
  );
end $$;
revoke all on function private_trigger_github_backup() from public, anon, authenticated;

-- Every 5 minutes. (To turn it off: select cron.unschedule('garimpeiro-github-backup');)
select cron.unschedule('garimpeiro-github-backup')
  where exists (select 1 from cron.job where jobname = 'garimpeiro-github-backup');
select cron.schedule('garimpeiro-github-backup', '*/5 * * * *', 'select private_trigger_github_backup()');
