import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
engine = create_engine(os.getenv("DATABASE_URL"))

queries = [
    "SET lock_timeout = '5s'; ALTER TABLE cameras ADD COLUMN IF NOT EXISTS hls_url VARCHAR(500)",
    "SET lock_timeout = '5s'; ALTER TABLE cameras ADD COLUMN IF NOT EXISTS mjpeg_url VARCHAR(500)",
    "SET lock_timeout = '5s'; ALTER TABLE cameras ADD COLUMN IF NOT EXISTS webrtc_url VARCHAR(500)"
]

try:
    with engine.begin() as conn:
        for q in queries:
            print(f"Executing: {q}")
            conn.execute(text(q))
    print("Database schema updated successfully.")
except Exception as e:
    print(f"Error updating schema: {e}")
