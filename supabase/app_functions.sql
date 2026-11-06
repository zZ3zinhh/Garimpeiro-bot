-- "Safe doors" for the Garimpeiro app.
-- The app only has the PUBLIC key, which cannot read any table (RLS is on, no policies).
-- So it calls the functions below, always sending the person's login code.
-- Each function checks the code and only touches that person's own rows.
-- Run this once in Supabase: SQL Editor -> New query -> Run.

-- 1) Extra info on sent alerts, so the app can show "latest deals found".
alter table sent_alerts add column if not exists title text;
alter table sent_alerts add column if not exists price numeric;
alter table sent_alerts add column if not exists link text;
alter table sent_alerts add column if not exists reason text;

-- 2) Helper: login code -> person id. The app can NOT call this one directly.
create or replace function private_person_id(p_code text)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare v_id uuid;
begin
  select id into v_id from people where code = p_code;
  if v_id is null then
    raise exception 'invalid code' using errcode = '28000';
  end if;
  return v_id;
end $$;
revoke all on function private_person_id(text) from public, anon, authenticated;

-- 3) Read everything the app needs about one person.
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
      'tags', coalesce((select json_agg(t order by t.id) from tags t where t.person_id = v_id), '[]'::json),
      'categories', coalesce((select json_agg(c order by c.id) from followed_categories c where c.person_id = v_id), '[]'::json)
    )
    from people p where p.id = v_id
  );
end $$;

-- 4) Create (p_id is null) or edit a tag.
create or replace function app_save_tag(
  p_code text, p_id bigint, p_text text, p_blocked_words text[],
  p_max_price numeric, p_absurd_alert boolean, p_market_price numeric, p_limit_pct integer
)
returns bigint
language plpgsql
security definer
set search_path = public
as $$
declare
  v_person uuid := private_person_id(p_code);
  v_id bigint;
begin
  if trim(coalesce(p_text, '')) = '' then
    raise exception 'empty tag';
  end if;
  if p_id is null then
    if (select count(*) from tags where person_id = v_person) >= 50 then
      raise exception 'too many tags';
    end if;
    insert into tags (person_id, text, blocked_words, max_price, absurd_alert, market_price, limit_pct)
    values (v_person, trim(p_text), coalesce(p_blocked_words, '{}'), p_max_price,
            coalesce(p_absurd_alert, false), p_market_price, coalesce(p_limit_pct, 50))
    returning id into v_id;
  else
    update tags
       set text = trim(p_text), blocked_words = coalesce(p_blocked_words, '{}'),
           max_price = p_max_price, absurd_alert = coalesce(p_absurd_alert, false),
           market_price = p_market_price, limit_pct = coalesce(p_limit_pct, 50)
     where id = p_id and person_id = v_person
    returning id into v_id;
    if v_id is null then
      raise exception 'tag not found';
    end if;
  end if;
  return v_id;
end $$;

create or replace function app_delete_tag(p_code text, p_id bigint)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  delete from tags where id = p_id and person_id = private_person_id(p_code);
end $$;

-- 5) Create (p_id is null) or edit a followed category.
create or replace function app_save_category(
  p_code text, p_id bigint, p_category text, p_min_discount_pct numeric, p_min_temperature integer
)
returns bigint
language plpgsql
security definer
set search_path = public
as $$
declare
  v_person uuid := private_person_id(p_code);
  v_id bigint;
begin
  if p_id is null then
    insert into followed_categories (person_id, category, min_discount_pct, min_temperature)
    values (v_person, p_category, p_min_discount_pct, p_min_temperature)
    returning id into v_id;
  else
    update followed_categories
       set category = p_category, min_discount_pct = p_min_discount_pct, min_temperature = p_min_temperature
     where id = p_id and person_id = v_person
    returning id into v_id;
    if v_id is null then
      raise exception 'category not found';
    end if;
  end if;
  return v_id;
end $$;

create or replace function app_delete_category(p_code text, p_id bigint)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  delete from followed_categories where id = p_id and person_id = private_person_id(p_code);
end $$;

-- 6) WhatsApp settings.
create or replace function app_save_settings(
  p_code text, p_whatsapp_enabled boolean, p_whatsapp_phone text, p_whatsapp_apikey text
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  update people
     set whatsapp_enabled = coalesce(p_whatsapp_enabled, false),
         whatsapp_phone = nullif(trim(coalesce(p_whatsapp_phone, '')), ''),
         whatsapp_apikey = nullif(trim(coalesce(p_whatsapp_apikey, '')), '')
   where id = private_person_id(p_code);
end $$;

-- 7) Latest alerts sent to this person.
create or replace function app_recent_alerts(p_code text, p_limit integer default 30)
returns json
language plpgsql
security definer
set search_path = public
as $$
declare v_id uuid := private_person_id(p_code);
begin
  return coalesce((
    select json_agg(x) from (
      select title, price, link, reason, sent_at
        from sent_alerts
       where person_id = v_id and title is not null
       order by sent_at desc
       limit least(coalesce(p_limit, 30), 100)
    ) x
  ), '[]'::json);
end $$;

-- 8) Let the app (role "anon", the public key) call the safe doors, and nothing else.
grant usage on schema public to anon;
grant execute on function app_get_profile(text) to anon;
grant execute on function app_save_tag(text, bigint, text, text[], numeric, boolean, numeric, integer) to anon;
grant execute on function app_delete_tag(text, bigint) to anon;
grant execute on function app_save_category(text, bigint, text, numeric, integer) to anon;
grant execute on function app_delete_category(text, bigint) to anon;
grant execute on function app_save_settings(text, boolean, text, text) to anon;
grant execute on function app_recent_alerts(text, integer) to anon;
