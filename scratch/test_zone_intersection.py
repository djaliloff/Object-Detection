"""
Direct diagnostic: simulate the processor's zone-intersection logic
with the real DB zones and a fake person bounding box.
Run from the scratch directory:
  ..\venv311\Scripts\python.exe test_zone_intersection.py
"""
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend-api")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "event-processor")))

from database import SessionLocal
from models import Zone as DBZone
from processor import Zone as ProcZone

db = SessionLocal()
try:
    camera_name = "islem"
    from models import Camera
    cam = db.query(Camera).filter(Camera.name == camera_name).first()
    if not cam:
        print(f"[ERROR] Camera '{camera_name}' not found in DB"); sys.exit(1)

    cam_id = str(cam.id)
    print(f"Camera ID: {cam_id}")

    db_zones = db.query(DBZone).filter(DBZone.camera_id == cam.id).all()
    print(f"Zones in DB for this camera: {len(db_zones)}")

    if not db_zones:
        print("[ERROR] No zones found for this camera — draw a zone first!")
        sys.exit(1)

    for z in db_zones:
        print(f"\n--- Zone: {z.name} ---")
        print(f"  Type       : {z.zone_type}")
        print(f"  Active     : {z.is_active}")
        print(f"  Config     : {z.config_json}")
        print(f"  Polygon    : {z.polygon}")

        zone = ProcZone(
            id=str(z.id),
            camera_id=cam_id,
            name=z.name,
            polygon=z.polygon,
            zone_type=z.zone_type,
            is_active=z.is_active,
            config=z.config_json or {}
        )

        # Simulate a person bbox covering the center of the image (normalized)
        test_cases = [
            [0.0, 0.0, 1.0, 1.0],   # entire frame — should always intersect
            [0.1, 0.05, 0.4, 0.5],   # upper-left person
            [0.4, 0.05, 0.75, 0.55], # upper-right person (inside ZONE-1 region in screenshot)
            [0.3, 0.1, 0.6, 0.4],   # center-top
        ]

        for bbox in test_cases:
            hit = zone.intersects_bbox(bbox)
            print(f"  bbox={bbox} -> intersects_bbox={hit}")

finally:
    db.close()
