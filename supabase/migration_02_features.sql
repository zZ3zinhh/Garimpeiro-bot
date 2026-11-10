-- Update #2 for Garimpeiro. Run this ONCE in Supabase: SQL Editor -> New query -> Run.
-- It is safe to run again (it only adds what is missing).
--
-- What it adds:
--   * tags: extra keywords and brands
--   * people: saved blocked words ("checkboxes") and the "only trusted stores" switch
--   * 25 more categories
--   * no more duplicated tags/categories when "Save" is tapped twice
-- The old app (the APK already installed) keeps working after this.

-- 1) New columns -------------------------------------------------------------
alter table tags add column if not exists keywords text[] not null default '{}';
alter table tags add column if not exists brands text[] not null default '{}';

alter table people add column if not exists only_trusted_stores boolean not null default false;
alter table people add column if not exists saved_blocked_words text[] not null
  default '{notebook,"pc gamer",computador,kit,usado,recondicionado}';

-- 2) More categories ---------------------------------------------------------
alter table followed_categories drop constraint if exists followed_categories_category_check;
alter table followed_categories add constraint followed_categories_category_check check (category in (
  'computers', 'games', 'phones', 'electronics', 'cameras', 'appliances', 'home', 'tools',
  'fashion_men', 'fashion_women', 'watches', 'bags', 'kids', 'toys', 'beauty', 'health',
  'fitness', 'sports', 'drinks', 'market', 'books', 'media', 'auto', 'travel', 'office', 'pets'
));

-- 3) Clean up exact duplicates that the double-tap bug already created -------
delete from tags a using tags b
 where a.id > b.id and a.person_id = b.person_id
   and lower(trim(a.text)) = lower(trim(b.text))
   and a.blocked_words = b.blocked_words and a.keywords = b.keywords and a.brands = b.brands
   and a.max_price is not distinct from b.max_price
   and a.absurd_alert = b.absurd_alert
   and a.market_price is not distinct from b.market_price
   and a.limit_pct = b.limit_pct;

delete from followed_categories a using followed_categories b
 where a.id > b.id and a.person_id = b.person_id and a.category = b.category
   and a.min_discount_pct is not distinct from b.min_discount_pct
   and a.min_temperature is not distinct from b.min_temperature;

-- 4) Profile: also send the new settings --------------------------------------
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
      'tags', coalesce((select json_agg(t order by t.id) from tags t where t.person_id = v_id), '[]'::json),
      'categories', coalesce((select json_agg(c order by c.id) from followed_categories c where c.person_id = v_id), '[]'::json)
    )
    from people p where p.id = v_id
  );
end $$;

-- 5) Tags: keywords + brands, and no duplicates ------------------------------
-- The old signature must go, otherwise the database can't choose between the two.
drop function if exists app_save_tag(text, bigint, text, text[], numeric, boolean, numeric, integer);

create or replace function app_save_tag(
  p_code text, p_id bigint, p_text text, p_blocked_words text[],
  p_max_price numeric, p_absurd_alert boolean, p_market_price numeric, p_limit_pct integer,
  p_keywords text[] default '{}', p_brands text[] default '{}'
)
returns bigint
language plpgsql
security definer
set search_path = public
as $$
declare
  v_person uuid := private_person_id(p_code);
  v_id bigint := p_id;
  v_keywords text[] := coalesce(p_keywords, '{}');
  v_brands text[] := coalesce(p_brands, '{}');
begin
  if trim(coalesce(p_text, '')) = '' then
    raise exception 'empty tag';
  end if;

  -- Creating a tag that already exists (e.g. "Save" tapped twice) just edits it.
  if v_id is null then
    select id into v_id from tags
     where person_id = v_person and lower(trim(text)) = lower(trim(p_text))
       and keywords = v_keywords and brands = v_brands
     limit 1;
  end if;

  if v_id is null then
    if (select count(*) from tags where person_id = v_person) >= 50 then
      raise exception 'too many tags';
    end if;
    insert into tags (person_id, text, keywords, brands, blocked_words, max_price,
                      absurd_alert, market_price, limit_pct)
    values (v_person, trim(p_text), v_keywords, v_brands, coalesce(p_blocked_words, '{}'),
            p_max_price, coalesce(p_absurd_alert, false), p_market_price, coalesce(p_limit_pct, 50))
    returning id into v_id;
  else
    update tags
       set text = trim(p_text), keywords = v_keywords, brands = v_brands,
           blocked_words = coalesce(p_blocked_words, '{}'),
           max_price = p_max_price, absurd_alert = coalesce(p_absurd_alert, false),
           market_price = p_market_price, limit_pct = coalesce(p_limit_pct, 50)
     where id = v_id and person_id = v_person
    returning id into v_id;
    if v_id is null then
      raise exception 'tag not found';
    end if;
  end if;
  return v_id;
end $$;

-- 6) Categories: following the same one twice just edits it ------------------
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
  v_id bigint := p_id;
begin
  if v_id is null then
    select id into v_id from followed_categories
     where person_id = v_person and category = p_category limit 1;
  end if;

  if v_id is null then
    insert into followed_categories (person_id, category, min_discount_pct, min_temperature)
    values (v_person, p_category, p_min_discount_pct, p_min_temperature)
    returning id into v_id;
  else
    update followed_categories
       set category = p_category, min_discount_pct = p_min_discount_pct, min_temperature = p_min_temperature
     where id = v_id and person_id = v_person
    returning id into v_id;
    if v_id is null then
      raise exception 'category not found';
    end if;
  end if;
  return v_id;
end $$;

-- 7) Preferences: saved blocked words + only trusted stores ------------------
create or replace function app_save_preferences(
  p_code text, p_saved_blocked_words text[], p_only_trusted_stores boolean
)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  update people
     set saved_blocked_words = coalesce(p_saved_blocked_words, '{}'),
         only_trusted_stores = coalesce(p_only_trusted_stores, false)
   where id = private_person_id(p_code);
end $$;

-- 8) Let the app call the new/changed doors ------------------------------------
grant execute on function app_get_profile(text) to anon;
grant execute on function app_save_tag(text, bigint, text, text[], numeric, boolean, numeric, integer, text[], text[]) to anon;
grant execute on function app_save_category(text, bigint, text, numeric, integer) to anon;
grant execute on function app_save_preferences(text, text[], boolean) to anon;
