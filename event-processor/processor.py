import os
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
from shapely.geometry import Point, Polygon, LineString
from shapely.ops import nearest_points
import uuid
from dotenv import load_dotenv

# Load environment variables from the root .env file
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

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

@dataclass
class Zone:
    """Detection zone for a camera."""
    id: str
    camera_id: str
    name: str
    polygon: List[List[float]]
    zone_type: str
    config: Dict[str, Any] = field(default_factory=dict)
    shapely_polygon: Optional[Polygon] = field(init=False)
    
    def __post_init__(self):
        if self.polygon and len(self.polygon) >= 3:
            self.shapely_polygon = Polygon(self.polygon)

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
        
        for det in detections:
            if det.track_id is None or det.track_id < 0:
                continue
            
            tid = det.track_id
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
                # New track
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
        
        return list(self.tracks[camera_id].values())

# ─── Event Detectors ─────────────────────────────────────────────────────────

class IntrusionDetector:
    """Detects intrusion events (objects entering exclusion zones)."""
    
    def __init__(self):
        self.active_intrusions: Dict[str, Event] = {}
    
    def detect_intrusion(self, track: Track, zones: List[Zone]) -> List[Event]:
        events = []
        
        if not track.positions:
            return events
        
        current_pos = track.positions[-1][:2]
        current_point = Point(current_pos)
        
        for zone in zones:
            if zone.zone_type != "exclusion":
                continue
            if not zone.shapely_polygon:
                continue
            
            is_in_zone = zone.shapely_polygon.contains(current_point)
            intrusion_key = f"{track.camera_id}_{track.id}_{zone.id}"
            
            if is_in_zone and intrusion_key not in self.active_intrusions:
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
                    }
                )
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
    
    def detect_loitering(self, track: Track, zones: List[Zone]) -> List[Event]:
        events = []
        
        if not track.positions:
            return events
        
        current_pos = track.positions[-1][:2]
        current_point = Point(current_pos)
        
        for zone in zones:
            if zone.zone_type != "alert":
                continue
            if not zone.shapely_polygon:
                continue
            
            is_in_zone = zone.shapely_polygon.contains(current_point)
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
                            }
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
    
    def detect_line_crossing(self, track: Track, lines: List[Line]) -> List[Event]:
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
                            }
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
    
    def detect_abandoned(self, track: Track) -> List[Event]:
        events = []
        
        if track.object_class == "person":
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
                        }
                    )
                    self.static_objects[track_key]["event_created"] = True
                    events.append(event)
        else:
            # Object moved, no longer static
            self.static_objects.pop(track_key, None)
        
        return events

class SpeedAnomalyDetector:
    """Detects speed anomalies — tracks moving faster than threshold."""
    
    def __init__(self, max_speed: float = 0.5):
        """
        Args:
            max_speed: Max speed in normalized coordinates per second.
                      0.5 means crossing 50% of frame per second.
        """
        self.max_speed = max_speed
        self.alerted_tracks: set = set()  # track_key -> already alerted
    
    def detect_speed_anomaly(self, track: Track) -> List[Event]:
        events = []
        
        if track.velocity is None:
            return events
        
        speed = math.sqrt(track.velocity[0]**2 + track.velocity[1]**2)
        track_key = f"{track.camera_id}_{track.id}"
        
        if speed > self.max_speed and track_key not in self.alerted_tracks:
            event = Event(
                id=str(uuid.uuid4()),
                event_type="speed_anomaly",
                camera_id=track.camera_id,
                track_id=track.id,
                start_time=track.last_seen,
                end_time=track.last_seen,
                severity="medium",
                zone_id=None,
                event_data={
                    "object_class": track.object_class,
                    "speed": round(speed, 4),
                    "velocity_x": round(track.velocity[0], 4),
                    "velocity_y": round(track.velocity[1], 4),
                    "confidence": track.confidence_avg,
                    "track_age": track.age,
                }
            )
            self.alerted_tracks.add(track_key)
            events.append(event)
        
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
        self.abandoned_detector = AbandonedObjectDetector(min_duration_seconds=60.0)
        self.speed_detector = SpeedAnomalyDetector(max_speed=0.5)
        
        self.running = False
        self.stats = {
            'detections_processed': 0,
            'events_generated': 0,
            'active_tracks': 0,
            'processing_time_avg': 0.0,
            'events_by_type': defaultdict(int),
        }
    
    def _connect_redis(self) -> redis.Redis:
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
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    def _deserialize_detections(self, detection_data: bytes) -> List[Detection]:
        """Deserialize detection data from Redis — supports new MOT format."""
        try:
            data = json.loads(detection_data.decode('utf-8'))
            
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
    
    def _serialize_event(self, event: Event) -> bytes:
        event_data = {
            'id': event.id,
            'event_type': event.event_type,
            'camera_id': event.camera_id,
            'track_id': event.track_id,
            'start_time': event.start_time.isoformat(),
            'end_time': event.end_time.isoformat() if event.end_time else None,
            'severity': event.severity,
            'zone_id': event.zone_id,
            'event_data': event.event_data,
            'status': event.status,
            'snapshot_refs': event.snapshot_refs
        }
        
        return json.dumps(event_data).encode('utf-8')
    
    def _load_zones_and_lines(self):
        """Load zones and lines from database or configuration."""
        example_zones = [
            Zone(
                id="zone_001",
                camera_id="cam_001",
                name="Restricted Area",
                polygon=[[100, 100], [400, 100], [400, 400], [100, 400]],
                zone_type="exclusion",
                config={"min_duration_seconds": 2}
            ),
            Zone(
                id="zone_002",
                camera_id="cam_001",
                name="Loitering Zone",
                polygon=[[500, 300], [800, 300], [800, 600], [500, 600]],
                zone_type="alert",
                config={"min_duration_seconds": 30, "max_displacement_pixels": 50}
            )
        ]
        
        example_lines = [
            Line(
                id="line_001",
                camera_id="cam_001",
                name="Entrance Line",
                start_point=[300, 0],
                end_point=[300, 720],
                direction="both"
            )
        ]
        
        for zone in example_zones:
            if zone.camera_id not in self.zones:
                self.zones[zone.camera_id] = []
            self.zones[zone.camera_id].append(zone)
        
        for line in example_lines:
            if line.camera_id not in self.lines:
                self.lines[line.camera_id] = []
            self.lines[line.camera_id].append(line)
        
        logger.info(f"Loaded {len(example_zones)} zones and {len(example_lines)} lines")
    
    def _process_detections(self, camera_id: str, detections: List[Detection]) -> List[Event]:
        """Process detections with track IDs from AI engine and run event detection."""
        events = []
        
        # Update track manager with AI-engine-assigned track IDs
        tracks = self.track_manager.update(camera_id, detections)
        
        # Get zones and lines for this camera
        zones = self.zones.get(camera_id, [])
        lines = self.lines.get(camera_id, [])
        
        # Run all event detectors on each track
        for track in tracks:
            # Intrusion detection
            intrusion_events = self.intrusion_detector.detect_intrusion(track, zones)
            events.extend(intrusion_events)
            
            # Loitering detection
            loitering_events = self.loitering_detector.detect_loitering(track, zones)
            events.extend(loitering_events)
            
            # Line crossing detection
            crossing_events = self.line_crossing_detector.detect_line_crossing(track, lines)
            events.extend(crossing_events)
            
            # Abandoned object detection (new)
            abandoned_events = self.abandoned_detector.detect_abandoned(track)
            events.extend(abandoned_events)
            
            # Speed anomaly detection (new)
            speed_events = self.speed_detector.detect_speed_anomaly(track)
            events.extend(speed_events)
        
        return events
    
    async def process_detection_queue(self):
        """Process detections from Redis queue."""
        self.running = True
        
        self._load_zones_and_lines()
        
        logger.info("Event processor started (using AI-engine MOT track IDs)")
        
        while self.running:
            try:
                detection_data = self.redis_client.lpop('detection_queue')
                if detection_data is None:
                    await asyncio.sleep(0.01)
                    continue
                
                start_time = time.time()
                detections = self._deserialize_detections(detection_data)
                
                if not detections:
                    continue
                
                camera_id = detections[0].camera_id
                events = self._process_detections(camera_id, detections)
                
                # Publish events
                for event in events:
                    event_data = self._serialize_event(event)
                    self.redis_client.rpush('event_queue', event_data)
                    self.redis_client.publish('surveillance_events', event_data)
                    
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
                        f"[MOT Events] Camera {camera_id}: {len(detections)} detections → "
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
