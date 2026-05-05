import sys
import os
sys.path.append(os.path.join(os.getcwd(), "backend-api"))

from database import SessionLocal
from models import Camera
import json

db = SessionLocal()
try:
    cameras = db.query(Camera).all()
    for c in cameras:
        print(f"ID: {c.id}")
        print(f"Name: {c.name}")
        print(f"Detection Enabled: {getattr(c, 'detection_enabled', 'N/A')}")
        print(f"Status: {c.status}")
        print(f"Modality: {c.modality}")
        print(f"URL: {c.stream_url or c.rtsp_url}")
        print("-" * 20)
finally:
    db.close()
