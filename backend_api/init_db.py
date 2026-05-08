"""
Database initialization script for Multi-Modal Video Surveillance Platform
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
import uuid

# Ensure the root directory is in the Python path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from backend_api.database import get_db, engine, Base
from backend_api.models import User, Camera, CameraGroup, Event, Zone, Detection, Frame
from sqlalchemy.orm import Session
from backend_api.auth import get_password_hash

def create_sample_data(db: Session):
    """Create sample data for demonstration."""
    
    # Check if admin user already exists
    existing_admin = db.query(User).filter(User.username == "admin").first()
    if existing_admin:
        print("Admin user already exists, skipping user creation")
    else:
        # Create admin user
        admin_user = User(
            username="admin",
            email="admin@surveillance.local", 
            password_hash=get_password_hash("changeme"),
            role="admin"
        )
        db.add(admin_user)
        db.flush()  # Get the ID
        print("Admin user created")
    
    # Create camera groups
    front_door_group = CameraGroup(
        name="Front Entrance",
        description="Cameras covering front entrance and lobby",
        location="Main Building - Floor 1"
    )
    parking_group = CameraGroup(
        name="Parking Lot",
        description="Parking lot surveillance cameras",
        location="Outdoor Parking Area"
    )
    db.add(front_door_group)
    db.add(parking_group)
    db.flush()  # Get the IDs
    
    # Create cameras
    cameras = [
        Camera(
            name="Front Door RGB",
            ip="192.168.1.100",
            port=554,
            rtsp_url="rtsp://192.168.1.100:554/stream1",
            credentials={"username": "admin", "password": "password123"},
            modality="rgb",
            group_id=front_door_group.id,
            config_json={"resolution": "1920x1080", "fps": 15},
            status="online",
            last_seen=datetime.utcnow()
        ),
        Camera(
            name="Front Door Thermal",
            ip="192.168.1.101",
            port=554,
            rtsp_url="rtsp://192.168.1.101:554/stream1",
            credentials={"username": "admin", "password": "password123"},
            modality="thermal",
            group_id=front_door_group.id,
            config_json={"resolution": "640x480", "fps": 10},
            status="online",
            last_seen=datetime.utcnow()
        ),
        Camera(
            name="Parking Camera 1",
            ip="192.168.1.102",
            port=554,
            rtsp_url="rtsp://192.168.1.102:554/stream1",
            credentials={"username": "admin", "password": "password123"},
            modality="rgb",
            group_id=parking_group.id,
            config_json={"resolution": "1920x1080", "fps": 15},
            status="online",
            last_seen=datetime.utcnow()
        ),
        Camera(
            name="Parking Camera 2",
            ip="192.168.1.103",
            port=554,
            rtsp_url="rtsp://192.168.1.103:554/stream1",
            credentials={"username": "admin", "password": "password123"},
            modality="rgb",
            group_id=parking_group.id,
            config_json={"resolution": "1920x1080", "fps": 15},
            status="offline",
            last_seen=datetime.utcnow() - timedelta(hours=2)
        )
    ]
    
    for camera in cameras:
        db.add(camera)
    
    db.flush()  # Get camera IDs
    
    # Create zones for cameras
    zones = []
    for camera in cameras:
        if camera.status == "online":
            # Create an intrusion detection zone
            zone = Zone(
                camera_id=camera.id,
                name=f"{camera.name} - Intrusion Zone",
                polygon=[[100, 100], [500, 100], [500, 400], [100, 400]],
                zone_type="alert",
                config_json={"detection_classes": ["person", "vehicle"], "min_confidence": 0.7}
            )
            zones.append(zone)
    
    for zone in zones:
        db.add(zone)
    
    db.flush()  # Get zone IDs
    
    # Create sample events
    events = []
    online_cameras = [c for c in cameras if c.status == "online"]
    
    for i in range(10):
        camera = online_cameras[i % len(online_cameras)]
        event = Event(
            event_type=["intrusion", "loitering", "line_crossing"][i % 3],
            camera_id=camera.id,
            start_time=datetime.utcnow() - timedelta(minutes=i*15),
            severity=["low", "medium", "high", "critical"][i % 4],
            event_data={
                "object_class": ["person", "vehicle", "person", "person"][i % 4],
                "confidence": 0.75 + (i * 0.02),
                "bbox": {"x1": 100, "y1": 100, "x2": 200, "y2": 300}
            },
            status="new" if i < 3 else "viewed"
        )
        events.append(event)
    
    for event in events:
        db.add(event)
    
    db.flush()  # Get event IDs
    
    # Create sample frames first (required for detections)
    frames = []
    for i in range(10):
        camera = online_cameras[i % len(online_cameras)]
        frame = Frame(
            camera_id=camera.id,
            timestamp=datetime.utcnow() - timedelta(minutes=i*5),
            frame_number=i+1,
            modality=camera.modality,
            resolution="1920x1080" if camera.modality == "rgb" else "640x480"
        )
        frames.append(frame)
    
    for frame in frames:
        db.add(frame)
    
    db.flush()  # Get frame IDs
    
    # Create sample detections (now with valid frame_ids)
    detections = []
    for i, frame in enumerate(frames):
        detection = Detection(
            frame_id=frame.id,
            camera_id=frame.camera_id,
            timestamp=frame.timestamp,
            object_class=["person", "vehicle", "bicycle", "dog"][i % 4],
            bbox={"x1": 100 + i*10, "y1": 100 + i*5, "x2": 200 + i*10, "y2": 300 + i*5},
            confidence=0.65 + (i * 0.01),
            track_id=i // 5  # Group detections into tracks
        )
        detections.append(detection)
    
    for detection in detections:
        db.add(detection)
    
    db.commit()
    
    print(f"Created sample data:")
    print(f"- 1 admin user")
    print(f"- 2 camera groups")
    print(f"- {len(cameras)} cameras")
    print(f"- {len(zones)} zones")
    print(f"- {len(events)} events")
    print(f"- {len(detections)} detections")

def main():
    """Initialize database with sample data."""
    print("Initializing database...")
    
    try:
        # Create database tables
        Base.metadata.create_all(bind=engine)
        print("Database tables created successfully")
        
        # Create sample data
        db = next(get_db())
        try:
            create_sample_data(db)
            print("Sample data created successfully")
        finally:
            db.close()
            
    except Exception as e:
        print(f"Error initializing database: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
