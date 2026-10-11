from supabase import create_client, Client

from config.settings import SUPABASE_SECRET_KEY, SUPABASE_URL

supabase: Client = create_client(
    supabase_url=SUPABASE_URL, supabase_key=SUPABASE_SECRET_KEY
)
