-- Update #3 for Garimpeiro: "Do not disturb" (silent alerts).
-- Run ONCE in Supabase: SQL Editor -> New query -> Run. Safe to run again.
-- Alerts keep arriving, but without sound or vibration while the mode is on.

alter table people add column if not exists quiet_now boolean not null default false;
alter table people add column if not exists quiet_schedule_enabled boolean not null default false;
alter table people add column if not exists quiet_start text not null default '22:00';
alter table people add column if not exists quiet_end text not null default '07:00';
alter table people add column if not exists quiet_allow_absurd boolean not null default false;

-- The profile now also carries the quiet-mode settings.
create or replace function app_get_profile(p_code text)
returns json
language plpgsql
security definer
set search_path = public
as $$
declare v_id uuid := private_person_id(p_code);
begin
  return (
    select json_build_object(
      'name', p.name,
      'ntfy_topic', p.ntfy_topic,
      'whatsapp_enabled', p.whatsapp_enabled,
      'whatsapp_phone', p.whatsapp_phone,
      'whatsapp_apikey', p.whatsapp_apikey,
      'only_trusted_stores', p.only_trusted_stores,
      'saved_blocked_words', p.saved_blocked_words,
      'quiet_now', p.quiet_now,
      'quiet_schedule_enabled', p.quiet_schedule_enabled,
      'quiet_start', p.quiet_start,
      'quiet_end', p.quiet_end,
      'quiet_allow_absurd', p.quiet_allow_absurd,
      'tags', coalesce((select json_agg(t order by t.id) from tags t where t.person_id = v_id), '[]'::json),
      'categories', coalesce((select json_agg(c order by c.id) from followed_categories c where c.person_id = v_id), '[]'::json)
    )
    from people p where p.id = v_id
  );
end $$;

create or replace function app_save_quiet(
  p_code text, p_quiet_now boolean, p_schedule_enabled boolean,
  p_start text, p_end text, p_allow_absurd boolean
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  if p_start !~ '^([01][0-9]|2[0-3]):[0-5][0-9]$' or p_end !~ '^([01][0-9]|2[0-3]):[0-5][0-9]$' then
    raise exception 'invalid time';
  end if;
  update people
     set quiet_now = coalesce(p_quiet_now, false),
         quiet_schedule_enabled = coalesce(p_schedule_enabled, false),
         quiet_start = p_start,
         quiet_end = p_end,
         quiet_allow_absurd = coalesce(p_allow_absurd, false)
   where id = private_person_id(p_code);
end $$;

grant execute on function app_get_profile(text) to anon;
grant execute on function app_save_quiet(text, boolean, boolean, text, text, boolean) to anon;
