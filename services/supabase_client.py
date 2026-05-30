import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL: str = os.environ.get("SUPABASE_URL")
SUPABASE_KEY: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError(".env 파일에 SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY 가 없습니다.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
