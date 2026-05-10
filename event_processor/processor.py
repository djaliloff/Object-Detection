import os
import sys

# Ensure both root, backend_api, and this directory are in path for all imports
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend_api")
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
for _p in [THIS_DIR, ROOT_DIR, BACKEND_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import json
import time
import math
import asyncio
import numpy as np
import redis
import structlog
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
from shapely.geometry import Point, Polygon, LineString, box
from shapely.ops import nearest_points
import uuid
from dotenv import load_dotenv
# Local imports
from notification_service import notification_service

from database import SessionLocal
from models import Zone as DBZone, Camera as DBCamera, Event as DBEvent

# Load environment variables from the root .env file
load_dotenv(os.path.join(ROOT_DIR, ".env"))

logger = structlog.get_logger()

# ─── Data Classes ────────────────────────────────────────────────────────────

@dataclass
class Detection:
    """Detection object from AI engine with tracking info."""
    camera_id: str
    frame_id: str
    timestamp: datetime
    object_class: str
    confidence: float
    bbox: List[float]           # [x1, y1, x2, y2] normalized
    track_id: Optional[int] = None
    center: Optional[Tuple[float, float]] = None
    velocity: Optional[Dict[str, float]] = None
    trajectory: Optional[List[List[float]]] = None
    age: int = 0
    hits: int = 0
    features: Optional[Dict[str, Any]] = None

@dataclass
class Track:
    """Object track across multiple frames — populated from AI engine MOT data."""
    id: int
    camera_id: str
    object_class: str
    first_seen: datetime
    last_seen: datetime
    positions: List[Tuple[float, float, datetime]] = field(default_factory=list)
    confidence_avg: float = 0.0
    length: int = 0
    velocity: Optional[Tuple[float, float]] = None
    age: int = 0
    hits: int = 0
    trajectory: List[Tuple[float, float]] = field(default_factory=list)
    bbox: List[float] = field(default_factory=list) # [x1, y1, x2, y2] normalized

@dataclass
class Zone:
    """Detection zone for a camera."""
    id: str
    camera_id: str
    name: str
    polygon: Optional[List[List[float]]]
    zone_type: str
    is_active: bool = True
    config: Dict[str, Any] = field(default_factory=dict)
    shapely_polygon: Optional[Polygon] = field(init=False, default=None)
    
    def __post_init__(self):
        if self.polygon and len(self.polygon) >= 3:
            self.shapely_polygon = Polygon(self.polygon)
            
    def contains(self, point: Point) -> bool:
        """Check if a point is within the zone."""
        if not self.is_active: return False
        shape = self.config.get('shape', 'polygon')
        if shape == 'circle':
            center = self.config.get('center', [0, 0])
            radius = self.config.get('radius', 0)
            dist = math.sqrt((point.x - center[0])**2 + (point.y - center[1])**2)
            return dist <= radius
        elif shape in ['square', 'rectangle']:
            rect = self.config.get('rect', [0, 0, 0, 0])
            x, y, w, h = rect
            x_min, x_max = min(x, x + w), max(x, x + w)
            y_min, y_max = min(y, y + h), max(y, y + h)
            return x_min <= point.x <= x_max and y_min <= point.y <= y_max
        else:
            if self.shapely_polygon and self.shapely_polygon.is_valid: 
                return self.shapely_polygon.contains(point)
        return False

    def intersects_bbox(self, bbox: List[float]) -> bool:
        """Check if a bounding box [x1, y1, x2, y2] intersects the zone."""
        if not self.is_active or not bbox or len(bbox) < 4: return False
        
        # Create a shapely box for the detection
        det_box = box(bbox[0], bbox[1], bbox[2], bbox[3])
        
        shape = self.config.get('shape', 'polygon')
        if shape == 'circle':
            # Approximate circle intersection
            center = self.config.get('center', [0, 0])
            radius = self.config.get('radius', 0)
            circle_poly = Point(center[0], center[1]).buffer(radius)
            return circle_poly.intersects(det_box)
        elif shape in ['square', 'rectangle']:
            rect = self.config.get('rect', [0, 0, 0, 0])
            x, y, w, h = rect
            x_min, x_max = min(x, x + w), max(x, x + w)
            y_min, y_max = min(y, y + h), max(y, y + h)
            zone_box = box(x_min, y_min, x_max, y_max)
            return zone_box.intersects(det_box)
        else:
            if self.shapely_polygon and self.shapely_polygon.is_valid:
                return self.shapely_polygon.intersects(det_box)
        return False

@dataclass
class Line:
    """Virtual line for crossing detection."""
    id: str
    camera_id: str
    name: str
    start_point: List[float]
    end_point: List[float]
    direction: str
    config: Dict[str, Any] = field(default_factory=dict)
    shapely_line: Optional[LineString] = field(init=False)
    
    def __post_init__(self):
        if self.start_point and self.end_point:
            self.shapely_line = LineString([self.start_point, self.end_point])

@dataclass
class Event:
    """Detected event."""
    id: str
    event_type: str
    camera_id: str
    track_id: Optional[int]
    start_time: datetime
    end_time: Optional[datetime]
    severity: str
    zone_id: Optional[str]
    event_data: Dict[str, Any]
    status: str = "new"
    snapshot_refs: Optional[Dict[str, str]] = None

# ─── Track Manager (receives MOT data from AI engine) ────────────────────────

class MOTTrackManager:
    """
    Manages tracks received from the AI engine's integrated MOT tracker (BoT-SORT/ByteTrack).
    
    Unlike the old ByteTrack class that re-tracked detections, this manager
    consumes the track_id assignments from the AI engine and maintains local 
    state for event detection (positions, velocity, etc).
    """
    
    def __init__(self, max_track_history: int = 300):
        self.max_track_history = max_track_history
        # camera_id -> { track_id -> Track }
        self.tracks: Dict[str, Dict[int, Track]] = defaultdict(dict)
    
    def update(self, camera_id: str, detections: List[Detection]) -> List[Track]:
        """
        Update tracks from AI-engine-assigned track IDs.
        
        Returns list of all active tracks for the camera.
        """
        current_time = datetime.now()
        active_track_ids = set()
        ephemeral_tracks = []  # Not stored between frames
        
        for i, det in enumerate(detections):
            tid = det.track_id
            
            # Untracked object — build a one-shot ephemeral track, don't store it
            if tid is None or tid < 0:
                center = det.center if det.center else (
                    (det.bbox[0] + det.bbox[2]) / 2.0,
                    (det.bbox[1] + det.bbox[3]) / 2.0
                )
                ephemeral_track = Track(
                    id=-1000 - i,
                    camera_id=camera_id,
                    object_class=det.object_class,
                    first_seen=current_time,
                    last_seen=current_time,
                    positions=[(center[0], center[1], current_time)],
                    confidence_avg=det.confidence,
                    length=1,
                    age=0,
                    hits=0,
                    bbox=det.bbox,
                )
                ephemeral_tracks.append(ephemeral_track)
                continue
            
            active_track_ids.add(tid)
            
            center = det.center if det.center else (
                (det.bbox[0] + det.bbox[2]) / 2.0,
                (det.bbox[1] + det.bbox[3]) / 2.0
            )
            
            if tid in self.tracks[camera_id]:
                # Update existing track
                track = self.tracks[camera_id][tid]
                track.last_seen = current_time
                track.length += 1
                track.bbox = det.bbox # Latest bbox
                track.confidence_avg = (
                    (track.confidence_avg * (track.length - 1) + det.confidence) / track.length
                )
                
                # Append position
                track.positions.append((center[0], center[1], current_time))
                if len(track.positions) > self.max_track_history:
                    track.positions = track.positions[-self.max_track_history:]
                
                # Use velocity from AI engine if available
                if det.velocity:
                    track.velocity = (det.velocity.get('vx', 0), det.velocity.get('vy', 0))
                elif len(track.positions) >= 2:
                    prev_pos = track.positions[-2]
                    curr_pos = track.positions[-1]
                    dt = (curr_pos[2] - prev_pos[2]).total_seconds()
                    if dt > 0:
                        vx = (curr_pos[0] - prev_pos[0]) / dt
                        vy = (curr_pos[1] - prev_pos[1]) / dt
                        track.velocity = (vx, vy)
                
                # Update from AI engine metadata
                track.age = det.age
                track.hits = det.hits
                if det.trajectory:
                    track.trajectory = [(p[0], p[1]) for p in det.trajectory]
                
            else:
                # New tracked object
                track = Track(
                    id=tid,
                    camera_id=camera_id,
                    object_class=det.object_class,
                    first_seen=current_time,
                    last_seen=current_time,
                    positions=[(center[0], center[1], current_time)],
                    confidence_avg=det.confidence,
                    length=1,
                    age=det.age,
                    hits=det.hits,
                    bbox=det.bbox,
                )
                if det.velocity:
                    track.velocity = (det.velocity.get('vx', 0), det.velocity.get('vy', 0))
                if det.trajectory:
                    track.trajectory = [(p[0], p[1]) for p in det.trajectory]
                
                self.tracks[camera_id][tid] = track
        
        # Clean up stale tracks (not seen in this frame and older than 30s)
        stale = []
        for tid, track in self.tracks[camera_id].items():
            if tid not in active_track_ids:
                time_since = (current_time - track.last_seen).total_seconds()
                if time_since > 30:
                    stale.append(tid)
        
        for tid in stale:
            del self.tracks[camera_id][tid]
        
        # Return persistent tracks + ephemeral one-shot tracks
        return list(self.tracks[camera_id].values()) + ephemeral_tracks


# ─── Event Detectors ─────────────────────────────────────────────────────────

class IntrusionDetector:
    """Detects intrusion events (objects entering exclusion zones)."""
    
    def __init__(self):
        self.active_intrusions: Dict[str, Event] = {}
        self.last_ephemeral_alert: Dict[str, float] = {}
        self.history_alerted_tracks: set = set() # (camera_id, track_id, zone_id)
        self.last_zone_alert: Dict[str, float] = {}
    
    def detect_intrusion(self, track: Track, zones: List[Zone], snapshot_path: Optional[str] = None) -> List[Event]:
        events = []
        
        if not track.positions:
            return events
            
        # Only trigger intrusion alerts for people
        if track.object_class.lower() != "person":
            return events
        
        current_pos = track.positions[-1][:2]
        current_point = Point(current_pos)
        
        for zone in zones:
            if zone.zone_type != "exclusion":
                continue
            
            # Sensitive detection: if any part of the bbox is in the zone, it's an intrusion
            is_in_zone = zone.intersects_bbox(track.bbox)
            intrusion_key = f"{track.camera_id}_{track.id}_{zone.id}"
            
            if is_in_zone:
                is_ephemeral = track.id < -500
                should_alert = False
                
                if is_ephemeral:
                    # Throttle ephemeral alerts to 30 seconds per zone to avoid spam
                    ephemeral_key = f"{track.camera_id}_{zone.id}"
                    now = time.time()
                    if now - self.last_ephemeral_alert.get(ephemeral_key, 0) > 30.0:
                        self.last_ephemeral_alert[ephemeral_key] = now
                        should_alert = True
                elif intrusion_key not in self.active_intrusions and (track.camera_id, track.id, zone.id) not in self.history_alerted_tracks:
                    # Also throttle non-ephemeral by 5 seconds per zone to avoid track ID flickering
                    zone_key = f"{track.camera_id}_{zone.id}"
                    now = time.time()
                    if now - self.last_zone_alert.get(zone_key, 0) > 5.0:
                        self.last_zone_alert[zone_key] = now
                        should_alert = True
                        self.history_alerted_tracks.add((track.camera_id, track.id, zone.id))

                if should_alert:
                    event = Event(
                        id=str(uuid.uuid4()),
                        event_type="intrusion",
                        camera_id=track.camera_id,
                        track_id=track.id,
                        start_time=track.last_seen,
                        end_time=None,
                        severity="medium",
                        zone_id=zone.id,
                        event_data={
                            "object_class": track.object_class,
                            "zone_name": zone.name,
                            "entry_point": current_pos,
                            "confidence": track.confidence_avg,
                            "track_age": track.age,
                            "track_hits": track.hits,
                            "is_ephemeral": is_ephemeral,
                        },
                        snapshot_refs={"frame": snapshot_path} if snapshot_path else None
                    )
                    if not is_ephemeral:
                        self.active_intrusions[intrusion_key] = event
                    events.append(event)
                
            elif not is_in_zone and intrusion_key in self.active_intrusions:
                event = self.active_intrusions[intrusion_key]
                event.end_time = track.last_seen
                event.status = "resolved"
                del self.active_intrusions[intrusion_key]
                events.append(event)
        
        return events

class LoiteringDetector:
    """Detects loitering events (objects staying in zones too long)."""
    
    def __init__(self):
        self.loitering_tracks: Dict[str, Dict] = {}
    
    def detect_loitering(self, track: Track, zones: List[Zone], snapshot_path: Optional[str] = None) -> List[Event]:
        events = []
        
        if not track.positions:
            return events
        
        current_pos = track.positions[-1][:2]
        current_point = Point(current_pos)
        
        for zone in zones:
            if zone.zone_type != "alert":
                continue
            
            is_in_zone = zone.contains(current_point)
            loitering_key = f"{track.id}_{zone.id}"
            
            min_duration = zone.config.get("min_duration_seconds", 30)
            max_displacement = zone.config.get("max_displacement_pixels", 50)
            
            if is_in_zone:
                if loitering_key not in self.loitering_tracks:
                    self.loitering_tracks[loitering_key] = {
                        "start_time": track.last_seen,
                        "positions": [current_pos],
                        "zone_id": zone.id,
                        "event_created": False
                    }
                else:
                    loitering_data = self.loitering_tracks[loitering_key]
                    loitering_data["positions"].append(current_pos)
                    
                    duration = (track.last_seen - loitering_data["start_time"]).total_seconds()
                    
                    positions = loitering_data["positions"]
                    if len(positions) > 1:
                        total_displacement = 0
                        for i in range(1, len(positions)):
                            displacement = math.sqrt(
                                (positions[i][0] - positions[0][0])**2 + 
                                (positions[i][1] - positions[0][1])**2
                            )
                            total_displacement = max(total_displacement, displacement)
                    else:
                        total_displacement = 0
                    
                    if (duration >= min_duration and 
                        total_displacement <= max_displacement and 
                        not loitering_data["event_created"]):
                        
                        event = Event(
                            id=str(uuid.uuid4()),
                            event_type="loitering",
                            camera_id=track.camera_id,
                            track_id=track.id,
                            start_time=loitering_data["start_time"],
                            end_time=track.last_seen,
                            severity="medium",
                            zone_id=zone.id,
                            event_data={
                                "object_class": track.object_class,
                                "zone_name": zone.name,
                                "duration_seconds": duration,
                                "displacement_pixels": total_displacement,
                                "confidence": track.confidence_avg,
                                "track_age": track.age,
                                "track_hits": track.hits,
                            },
                            snapshot_refs={"frame": snapshot_path} if snapshot_path else None
                        )
                        
                        loitering_data["event_created"] = True
                        events.append(event)
            else:
                if loitering_key in self.loitering_tracks:
                    del self.loitering_tracks[loitering_key]
        
        return events

class LineCrossingDetector:
    """Detects line crossing events."""
    
    def __init__(self):
        self.crossing_memory: Dict[str, List] = {}
    
    def detect_line_crossing(self, track: Track, lines: List[Line], snapshot_path: Optional[str] = None) -> List[Event]:
        events = []
        
        if not track.positions:
            return events
        
        current_pos = track.positions[-1][:2]
        current_point = Point(current_pos)
        
        for line in lines:
            if not line.shapely_line:
                continue
            
            distance = current_point.distance(line.shapely_line)
            if distance > 10:
                continue
            
            line_vec = np.array([line.end_point[0] - line.start_point[0], 
                                line.end_point[1] - line.start_point[1]])
            line_normal = np.array([-line_vec[1], line_vec[0]])
            
            track_vec = np.array([current_pos[0] - line.start_point[0], 
                                 current_pos[1] - line.start_point[1]])
            
            side = np.sign(np.dot(track_vec, line_normal))
            
            crossing_key = f"{track.id}_{line.id}"
            
            if crossing_key in self.crossing_memory:
                last_side, last_pos = self.crossing_memory[crossing_key]
                
                if last_side != 0 and side != 0 and last_side != side:
                    direction = "a_to_b" if side > 0 else "b_to_a"
                    
                    if line.direction in ["both", direction]:
                        event = Event(
                            id=str(uuid.uuid4()),
                            event_type="line_crossing",
                            camera_id=track.camera_id,
                            track_id=track.id,
                            start_time=track.last_seen,
                            end_time=track.last_seen,
                            severity="low",
                            zone_id=line.id,
                            event_data={
                                "object_class": track.object_class,
                                "line_name": line.name,
                                "crossing_point": current_pos,
                                "direction": direction,
                                "confidence": track.confidence_avg,
                                "track_age": track.age,
                            },
                            snapshot_refs={"frame": snapshot_path} if snapshot_path else None
                        )
                        events.append(event)
            
            self.crossing_memory[crossing_key] = [side, current_pos]
        
        return events

class AbandonedObjectDetector:
    """Detects abandoned objects — static non-person detections persisting beyond threshold."""
    
    def __init__(self, min_duration_seconds: float = 60.0, min_area: float = 0.001):
        self.min_duration = min_duration_seconds
        self.min_area = min_area
        self.static_objects: Dict[str, Dict] = {}  # track_key -> {first_seen, last_pos, event_created}
    
    def detect_abandoned(self, track: Track, snapshot_path: Optional[str] = None) -> List[Event]:
        events = []
        
        if track.object_class not in ["suitcase", "handbag", "backpack"]:
            return events
        
        if not track.positions or len(track.positions) < 2:
            return events
        
        current_pos = track.positions[-1][:2]
        track_key = f"{track.camera_id}_{track.id}"
        
        # Calculate displacement from first position
        first_pos = track.positions[0][:2]
        displacement = math.sqrt(
            (current_pos[0] - first_pos[0])**2 + (current_pos[1] - first_pos[1])**2
        )
        
        # Object is considered static if displacement is tiny
        is_static = displacement < 0.02  # 2% of frame dimension
        
        if is_static:
            if track_key not in self.static_objects:
                self.static_objects[track_key] = {
                    "first_seen": track.first_seen,
                    "last_pos": current_pos,
                    "event_created": False,
                }
            else:
                duration = (track.last_seen - self.static_objects[track_key]["first_seen"]).total_seconds()
                
                if duration >= self.min_duration and not self.static_objects[track_key]["event_created"]:
                    event = Event(
                        id=str(uuid.uuid4()),
                        event_type="abandoned_object",
                        camera_id=track.camera_id,
                        track_id=track.id,
                        start_time=self.static_objects[track_key]["first_seen"],
                        end_time=track.last_seen,
                        severity="high",
                        zone_id=None,
                        event_data={
                            "object_class": track.object_class,
                            "duration_seconds": duration,
                            "position": current_pos,
                            "confidence": track.confidence_avg,
                            "track_age": track.age,
                        },
                        snapshot_refs={"frame": snapshot_path} if snapshot_path else None
                    )
                    self.static_objects[track_key]["event_created"] = True
                    events.append(event)
        else:
            # Object moved, no longer static
            self.static_objects.pop(track_key, None)
        
        return events

# ─── Main Event Processor ────────────────────────────────────────────────────

class EventProcessor:
    """Main event processor that coordinates all event detection using AI-engine MOT data."""
    
    def __init__(self):
        self.redis_client = self._connect_redis()
        
        # MOT Track Manager — receives track IDs from AI engine
        self.track_manager = MOTTrackManager(max_track_history=300)
        
        self.zones: Dict[str, List[Zone]] = {}
        self.lines: Dict[str, List[Line]] = {}
        
        # Event detectors
        self.intrusion_detector = IntrusionDetector()
        self.loitering_detector = LoiteringDetector()
        self.line_crossing_detector = LineCrossingDetector()
        self.abandoned_detector = AbandonedObjectDetector(min_duration_seconds=180.0)
        
        self.running = False
        self.stats = {
            'detections_processed': 0,
            'events_generated': 0,
            'active_tracks': 0,
            'processing_time_avg': 0.0,
            'events_by_type': defaultdict(int),
        }
    
    def _connect_redis(self) -> redis.Redis:
        """Connect to Redis with retry logic."""
        while True:
            try:
                client = redis.Redis(
                    host=os.getenv("REDIS_HOST", "localhost"),
                    port=int(os.getenv("REDIS_PORT", 6379)),
                    decode_responses=False
                )
                client.ping()
                logger.info("Connected to Redis")
                return client
            except Exception as e:
                logger.error(f"Failed to connect to Redis (retrying in 5s): {e}")
                time.sleep(5)
    
    def _deserialize_detections(self, data: Dict) -> List[Detection]:
        """Deserialize detection data dictionary — supports new MOT format."""
        try:
            
            detections = []
            for det_data in data.get('detections', []):
                # Parse center
                center_data = det_data.get('center')
                center = None
                if center_data:
                    center = (center_data.get('x', 0), center_data.get('y', 0))
                
                detection = Detection(
                    camera_id=data['camera_id'],
                    frame_id=data['frame_id'],
                    timestamp=datetime.fromisoformat(data['timestamp']),
                    object_class=det_data['class_name'],
                    confidence=det_data['confidence'],
                    bbox=det_data['bbox'],
                    track_id=det_data.get('track_id'),
                    center=center,
                    velocity=det_data.get('velocity'),
                    trajectory=det_data.get('trajectory'),
                    age=det_data.get('age', 0),
                    hits=det_data.get('hits', 0),
                    features=det_data.get('features'),
                )
                detections.append(detection)
            
            return detections
            
        except Exception as e:
            logger.error(f"Failed to deserialize detections: {e}")
            return []
    
    def _serialize_event_to_dict(self, event: Event) -> Dict:
        """Convert event to dictionary for serialization and notification."""
        return {
            'id': event.id,
            'event_type': event.event_type,
            'camera_id': event.camera_id,
            'track_id': event.track_id,
            'start_time': event.start_time.isoformat() if isinstance(event.start_time, datetime) else event.start_time,
            'end_time': event.end_time.isoformat() if isinstance(event.end_time, datetime) else event.end_time,
            'severity': event.severity,
            'zone_id': event.zone_id,
            'event_data': event.event_data,
            'status': event.status,
            'snapshot_refs': event.snapshot_refs
        }

    def _get_camera_name(self, camera_id: str) -> str:
        """Helper to get camera name (stub for now)."""
        # In a real app, this would query the DB or a cache
        return f"Camera {camera_id[:8]}"

    def _serialize_event(self, event: Event) -> bytes:
        """Serialize event object to JSON bytes."""
        return json.dumps(self._serialize_event_to_dict(event)).encode('utf-8')
    
    def _load_zones_and_lines(self):
        """Load zones and lines from database."""
        try:
            db = SessionLocal()
            db_zones = db.query(DBZone).all()
            
            # Reset internal maps
            self.zones = {}
            self.lines = {}
            
            for z in db_zones:
                cam_id = str(z.camera_id)
                if cam_id not in self.zones:
                    self.zones[cam_id] = []
                
                # Create Zone dataclass from DB model
                zone = Zone(
                    id=str(z.id),
                    camera_id=cam_id,
                    name=z.name,
                    polygon=z.polygon,
                    zone_type=z.zone_type,
                    is_active=z.is_active,
                    config=z.config_json or {}
                )
                self.zones[cam_id].append(zone)
                
            db.close()
            logger.info(f"Synchronized {len(db_zones)} zones from DB")
        except Exception as e:
            logger.error(f"Failed to load zones from database: {e}")
            # Fallback to empty or keep existing
            if not hasattr(self, 'zones'):
                self.zones = {}
                self.lines = {}
    
    def _process_detections(self, camera_id: str, detections: List[Detection], snapshot_path: Optional[str] = None) -> List[Event]:
        """Process detections with track IDs from AI engine and run event detection."""
        events = []
        
        # Update track manager with AI-engine-assigned track IDs
        # Ephemeral tracks (ID < 0) are now included
        tracks = self.track_manager.update(camera_id, detections)
        
        # Get zones and lines for this camera
        zones = self.zones.get(camera_id, [])
        lines = self.lines.get(camera_id, [])
        
        if zones:
            logger.debug(f"[Zone Check] Camera {camera_id[:8]}: {len(tracks)} tracks vs {len(zones)} zones")
        
        # Run all event detectors on each track
        for track in tracks:
            # Intrusion detection
            intrusion_events = self.intrusion_detector.detect_intrusion(track, zones, snapshot_path=snapshot_path)
            for event in intrusion_events:
                logger.warning(f"[INTRUSION] Camera {camera_id[:8]} | Class={track.object_class} | Zone={event.zone_id} | Ephemeral={track.id < -500}")
                if track.id < -500: # It's a temporary/ephemeral track
                    event.event_data["is_ephemeral"] = True
                events.append(event)

            
            # Loitering detection
            loitering_events = self.loitering_detector.detect_loitering(track, zones, snapshot_path=snapshot_path)
            events.extend(loitering_events)
            
            # Line crossing detection
            crossing_events = self.line_crossing_detector.detect_line_crossing(track, lines, snapshot_path=snapshot_path)
            events.extend(crossing_events)
            
            # Abandoned object detection (new)
            abandoned_events = self.abandoned_detector.detect_abandoned(track, snapshot_path=snapshot_path)
            events.extend(abandoned_events)
            
        return events
    
    async def process_detection_queue(self):
        """Process detections from Redis queue."""
        self.running = True
        
        self._load_zones_and_lines()
        
        logger.info("Event processor started (using AI-engine MOT track IDs)")
        
        last_zone_refresh = time.time()
        
        while self.running:
            try:
                # Periodic zone refresh (every 5 seconds)
                if time.time() - last_zone_refresh > 5:
                    self._load_zones_and_lines()
                    last_zone_refresh = time.time()
                
                detection_data = self.redis_client.lpop('detection_queue')
                if detection_data is None:
                    await asyncio.sleep(0.01)
                    continue
                
                start_time = time.time()
                if isinstance(detection_data, bytes):
                    detection_data = detection_data.decode('utf-8')
                msg = json.loads(detection_data)
                detections = self._deserialize_detections(msg)
                snapshot_path = msg.get('snapshot_path')
                
                if not detections:
                    continue
                
                camera_id = detections[0].camera_id
                events = self._process_detections(camera_id, detections, snapshot_path=snapshot_path)
                
                    # Publish events
                for event in events:
                    event_data_dict = self._serialize_event_to_dict(event)
                    event_data_bytes = json.dumps(event_data_dict).encode('utf-8')
                    
                    # Save to DB for persistence and dashboard alerts
                    try:
                        db = SessionLocal()
                        db_event = DBEvent(
                            id=uuid.UUID(event.id) if isinstance(event.id, str) else event.id,
                            event_type=event.event_type,
                            camera_id=uuid.UUID(camera_id) if isinstance(camera_id, str) else camera_id,
                            track_id=event.track_id,
                            start_time=event.start_time if isinstance(event.start_time, datetime) else datetime.fromisoformat(event.start_time),
                            severity=event.severity,
                            zone_id=uuid.UUID(event.zone_id) if event.zone_id and isinstance(event.zone_id, str) else event.zone_id,
                            event_data=event.event_data,
                            status=event.status,
                            snapshot_refs=event.snapshot_refs
                        )
                        db.merge(db_event)
                        db.commit()
                        db.close()
                        logger.debug(f"Event {event.id} persisted to database")
                    except Exception as db_err:
                        logger.error(f"Failed to persist event to DB: {db_err}")

                    self.redis_client.rpush('event_queue', event_data_bytes)
                    self.redis_client.publish('surveillance_events', event_data_bytes)
                    
                    # Send email for specific events or high severity
                    if event.severity in ["high", "critical"] or event.event_type in ["intrusion", "loitering"]:
                        # Run email sending in background task
                        asyncio.create_task(notification_service.send_event_email(
                            event_data_dict, 
                            camera_name=self._get_camera_name(camera_id)
                        ))
                    
                    # Update event type stats
                    self.stats['events_by_type'][event.event_type] += 1
                
                # Update stats
                processing_time = time.time() - start_time
                self.stats['detections_processed'] += len(detections)
                self.stats['events_generated'] += len(events)
                self.stats['active_tracks'] = sum(
                    len(tracks) for tracks in self.track_manager.tracks.values()
                )
                
                total_processed = self.stats['detections_processed']
                current_avg = self.stats['processing_time_avg']
                self.stats['processing_time_avg'] = (
                    (current_avg * (total_processed - len(detections)) + processing_time) / total_processed
                )
                
                if events:
                    logger.info(
                        f"[MOT Events] Camera {camera_id}: {len(detections)} detections -> "
                        f"{len(events)} events: {[e.event_type for e in events]}"
                    )
                
            except Exception as e:
                logger.error(f"Error processing detections: {e}")
                await asyncio.sleep(0.1)
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            'detections_processed': self.stats['detections_processed'],
            'events_generated': self.stats['events_generated'],
            'active_tracks': self.stats['active_tracks'],
            'processing_time_avg': self.stats['processing_time_avg'],
            'events_by_type': dict(self.stats['events_by_type']),
            'track_manager_cameras': len(self.track_manager.tracks),
            'zones_count': sum(len(zones) for zones in self.zones.values()),
            'lines_count': sum(len(lines) for lines in self.lines.values()),
        }
    
    async def start(self):
        await self.process_detection_queue()
    
    def stop(self):
        self.running = False
        logger.info("Event processor stopped")

if __name__ == "__main__":
    processor = EventProcessor()
    
    try:
        asyncio.run(processor.start())
    except KeyboardInterrupt:
        processor.stop()
        logger.info("Event processor stopped by user")
