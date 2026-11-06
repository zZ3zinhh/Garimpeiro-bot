-- Gives the bot (which uses the secret key) permission to use the tables.
-- Run this once in Supabase: SQL Editor -> New query -> Run.
-- The secret key already skips RLS, so only table permissions are needed here.

grant usage on schema public to service_role;
grant select, insert, update, delete on all tables in schema public to service_role;
grant usage, select on all sequences in schema public to service_role;

-- Future tables get the same permissions automatically.
alter default privileges in schema public grant select, insert, update, delete on tables to service_role;
alter default privileges in schema public grant usage, select on sequences to service_role;
