# App settings. Both values here are PUBLIC on purpose:
# the publishable key can't read any table, it can only call the "safe doors"
# (functions in supabase/app_functions.sql) that ask for the person's login code.
# NEVER put the secret key (sb_secret_...) in the app.
APP_NAME = "Garimpeiro"
SUPABASE_URL = "https://ahkdkncfsnvxjzxjgldz.supabase.co"
SUPABASE_PUBLISHABLE_KEY = "sb_publishable_bVa3QxL2sf_vi0_RkfbJYg_Fdyc29Mq"
