import sys
import os
# Add the correct path to the backend API package
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend-api")))

from database import SessionLocal
from models import Camera
import json

db = SessionLocal()
try:
    c = db.query(Camera).filter(Camera.name == 'islem').first()
    if c:
        print(f"ID: {c.id}")
        print(f"Name: {c.name}")
        print(f"IP: {c.ip}")
        print(f"Port: {c.port}")
        print(f"RTSP: {c.rtsp_url}")
        print(f"MJPEG: {c.mjpeg_url}")
        print(f"Stream URL: {c.stream_url}")
        print(f"Config JSON: {c.config_json}")
        # Show detection flag
        det_enabled = getattr(c, "detection_enabled", None)
        if det_enabled is None:
            try:
                cfg = json.loads(c.config_json or "{}")
                det_enabled = cfg.get("detection_enabled")
            except Exception:
                det_enabled = "unknown"
        print(f"Detection Enabled: {det_enabled}")
    else:
        print("Camera not found")
finally:
    db.close()
