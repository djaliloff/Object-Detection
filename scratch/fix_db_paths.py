import sys
import os
from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql://postgres:djalildjt@localhost:5432/surveillanceV2"
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    # 1. Update rtsp_url
    update_rtsp = conn.execute(text("""
        UPDATE cameras 
        SET rtsp_url = REPLACE(rtsp_url, 'backend-api', 'backend_api')
        WHERE rtsp_url LIKE '%backend-api%'
    """))
    print(f"Updated {update_rtsp.rowcount} RTSP URLs")
    
    # 2. Update config_json (if it contains paths)
    update_config = conn.execute(text("""
        UPDATE cameras 
        SET config_json = CAST(REPLACE(CAST(config_json AS TEXT), 'backend-api', 'backend_api') AS JSONB)
        WHERE CAST(config_json AS TEXT) LIKE '%backend-api%'
    """))
    print(f"Updated {update_config.rowcount} config_json entries")
    
    conn.commit()

print("Database paths updated successfully.")
