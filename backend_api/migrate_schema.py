import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Add parent dir to path to import database and models
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/surveillance")

def run_migration():
    print(f"Connecting to database: {DATABASE_URL}")
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        print("Checking for missing columns...")
        
        # Add stream_url to cameras
        try:
            conn.execute(text("ALTER TABLE cameras ADD COLUMN IF NOT EXISTS stream_url VARCHAR(500)"))
            print("Verified stream_url in cameras table")
        except Exception as e:
            print(f"Error updating cameras table: {e}")

        # Add is_active to zones
        try:
            conn.execute(text("ALTER TABLE zones ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE"))
            print("Verified is_active in zones table")
        except Exception as e:
            print(f"Error adding is_active to zones table: {e}")

        # Add config_json to zones
        try:
            conn.execute(text("ALTER TABLE zones ADD COLUMN IF NOT EXISTS config_json JSONB"))
            print("Verified config_json in zones table")
        except Exception as e:
            print(f"Error adding config_json to zones table: {e}")
            
        conn.commit()
        print("Migration completed successfully.")

if __name__ == "__main__":
    run_migration()
