import uuid
import sys
import os

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Camera
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

try:
    ip_addr = "10.123.122.34"
    stream_url = "http://10.123.122.34:8080/video"
    
    existing = db.query(Camera).filter(Camera.ip == ip_addr).first()
    if existing:
        print(f"Updating camera: {existing.name}")
        existing.rtsp_url = stream_url
        existing.modality = "rgb" # Keep as rgb if mjpeg not in enum, or use 'mjpeg' if updated schemas.py
        if not existing.config_json:
            existing.config_json = {}
        existing.config_json["mjpeg_url"] = stream_url
        existing.config_json["stream_url"] = stream_url
        db.commit()
    else:
        new_cam = Camera(
            id=uuid.uuid4(),
            name="Tactical IP Webcam",
            ip=ip_addr,
            port=8080,
            rtsp_url=stream_url,
            modality="rgb",
            status="online",
            config_json={
                "mjpeg_url": stream_url,
                "stream_url": stream_url,
                "ptz_enabled": True
            }
        )
        db.add(new_cam)
        db.commit()
    print("Camera operation successful.")
finally:
    db.close()
