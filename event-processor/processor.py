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

@dataclass
class Detection:
    """Detection object from AI engine."""
    camera_id: str
    frame_id: str
    timestamp: datetime
    object_class: str
    confidence: float
    bbox: List[float]  # [x1, y1, x2, y2]
    track_id: Optional[int] = None
    features: Optional[Dict[str, Any]] = None

@dataclass
class Track:
    """Object track across multiple frames."""
    id: int
    camera_id: str
    object_class: str
    first_seen: datetime
    last_seen: datetime
    positions: List[Tuple[float, float, datetime]] = field(default_factory=list)  # [(x, y, timestamp), ...]
    confidence_avg: float = 0.0
    length: int = 0
    velocity: Optional[Tuple[float, float]] = None  # (vx, vy) pixels per second

@dataclass
class Zone:
    """Detection zone for a camera."""
    id: str
    camera_id: str
    name: str
    polygon: List[List[float]]  # [[x1, y1], [x2, y2], ...]
    zone_type: str  # exclusion, counting, alert
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
    start_point: List[float]  # [x, y]
    end_point: List[float]    # [x, y]
    direction: str  # a_to_b, b_to_a, both
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

class ByteTrack:
    """Simplified ByteTrack implementation for object tracking."""
    
    def __init__(self, max_disappeared: int = 30, max_distance: float = 100.0):
        self.max_disappeared = max_disappeared
        self.max_distance = max_distance
        self.tracks: Dict[int, Track] = {}
        self.next_track_id = 1
        self.frame_count = 0
    
    def _calculate_distance(self, pos1: Tuple[float, float], pos2: Tuple[float, float]) -> float:
        """Calculate Euclidean distance between two positions."""
        return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)
    
    def _get_bbox_center(self, bbox: List[float]) -> Tuple[float, float]:
        """Get center point of bounding box."""
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) / 2, (y1 + y2) / 2)
    
    def update(self, detections: List[Detection]) -> List[Track]:
        """Update tracker with new detections."""
        self.frame_count += 1
        current_time = datetime.now()
        
        # Get centers of current detections
        detection_centers = []
        for det in detections:
            center = self._get_bbox_center(det.bbox)
            detection_centers.append((center, det))
        
        # Match detections to existing tracks
        matched_tracks = set()
        new_tracks = []
        
        for center, detection in detection_centers:
            best_track_id = None
            best_distance = float('inf')
            
            # Find closest track
            for track_id, track in self.tracks.items():
                if track.positions:
                    last_pos = track.positions[-1][:2]  # (x, y)
                    distance = self._calculate_distance(center, last_pos)
                    
                    if distance < best_distance and distance < self.max_distance:
                        best_distance = distance
                        best_track_id = track_id
            
            if best_track_id is not None:
                # Update existing track
                track = self.tracks[best_track_id]
                track.positions.append((center[0], center[1], current_time))
                track.last_seen = current_time
                track.length += 1
                
                # Update average confidence
                track.confidence_avg = (track.confidence_avg * (track.length - 1) + detection.confidence) / track.length
                
                # Calculate velocity
                if len(track.positions) >= 2:
                    prev_pos = track.positions[-2]
                    curr_pos = track.positions[-1]
                    dt = (curr_pos[2] - prev_pos[2]).total_seconds()
                    if dt > 0:
                        vx = (curr_pos[0] - prev_pos[0]) / dt
                        vy = (curr_pos[1] - prev_pos[1]) / dt
                        track.velocity = (vx, vy)
                
                matched_tracks.add(best_track_id)
            else:
                # Create new track
                track = Track(
                    id=self.next_track_id,
                    camera_id=detection.camera_id,
                    object_class=detection.object_class,
                    first_seen=current_time,
                    last_seen=current_time,
                    positions=[(center[0], center[1], current_time)],
                    confidence_avg=detection.confidence,
                    length=1
                )
                self.tracks[self.next_track_id] = track
                new_tracks.append(track)
                self.next_track_id += 1
        
        # Mark unmatched tracks as disappeared
        disappeared_tracks = []
        for track_id, track in self.tracks.items():
            if track_id not in matched_tracks:
                time_since_last = (current_time - track.last_seen).total_seconds()
                if time_since_last > self.max_disappeared:
                    disappeared_tracks.append(track_id)
        
        # Remove disappeared tracks
        for track_id in disappeared_tracks:
            del self.tracks[track_id]
        
        return list(self.tracks.values())

class IntrusionDetector:
    """Detects intrusion events (objects entering exclusion zones)."""
    
    def __init__(self):
        self.active_intrusions: Dict[str, Event] = {}  # track_id -> Event
    
    def detect_intrusion(self, track: Track, zones: List[Zone]) -> List[Event]:
        """Detect intrusion events for a track."""
        events = []
        
        if not track.positions:
            return events
        
        current_pos = track.positions[-1][:2]  # (x, y)
        current_point = Point(current_pos)
        
        for zone in zones:
            if zone.zone_type != "exclusion":
                continue
            
            if not zone.shapely_polygon:
                continue
            
            # Check if track is in zone
            is_in_zone = zone.shapely_polygon.contains(current_point)
            
            intrusion_key = f"{track.camera_id}_{track.id}_{zone.id}"
            
            if is_in_zone and intrusion_key not in self.active_intrusions:
                # New intrusion detected
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
                        "confidence": track.confidence_avg
                    }
                )
                
                self.active_intrusions[intrusion_key] = event
                events.append(event)
                
            elif not is_in_zone and intrusion_key in self.active_intrusions:
                # Track left the zone, end the intrusion
                event = self.active_intrusions[intrusion_key]
                event.end_time = track.last_seen
                event.status = "resolved"
                
                del self.active_intrusions[intrusion_key]
                events.append(event)
        
        return events

class LoiteringDetector:
    """Detects loitering events (objects staying in zones too long)."""
    
    def __init__(self):
        self.loitering_tracks: Dict[str, Dict] = {}  # track_id_zone_id -> {start_time, total_displacement}
    
    def detect_loitering(self, track: Track, zones: List[Zone]) -> List[Event]:
        """Detect loitering events for a track."""
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
                    # Track entered zone
                    self.loitering_tracks[loitering_key] = {
                        "start_time": track.last_seen,
                        "positions": [current_pos],
                        "zone_id": zone.id,
                        "event_created": False
                    }
                else:
                    # Update tracking
                    loitering_data = self.loitering_tracks[loitering_key]
                    loitering_data["positions"].append(current_pos)
                    
                    # Calculate duration
                    duration = (track.last_seen - loitering_data["start_time"]).total_seconds()
                    
                    # Calculate total displacement
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
                    
                    # Check if loitering conditions are met
                    if (duration >= min_duration and 
                        total_displacement <= max_displacement and 
                        not loitering_data["event_created"]):
                        
                        # Create loitering event
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
                                "confidence": track.confidence_avg
                            }
                        )
                        
                        loitering_data["event_created"] = True
                        events.append(event)
            
            else:
                # Track left zone, clean up
                if loitering_key in self.loitering_tracks:
                    del self.loitering_tracks[loitering_key]
        
        return events

class LineCrossingDetector:
    """Detects line crossing events."""
    
    def __init__(self):
        self.crossing_memory: Dict[str, List] = {}  # track_id -> [last_side, last_position]
    
    def detect_line_crossing(self, track: Track, lines: List[Line]) -> List[Event]:
        """Detect line crossing events for a track."""
        events = []
        
        if not track.positions:
            return events
        
        current_pos = track.positions[-1][:2]
        current_point = Point(current_pos)
        
        for line in lines:
            if not line.shapely_line:
                continue
            
            # Check if track is near the line
            distance = current_point.distance(line.shapely_line)
            if distance > 10:  # Threshold distance in pixels
                continue
            
            # Determine which side of the line the track is on
            # Using perpendicular distance to determine side
            line_vec = np.array([line.end_point[0] - line.start_point[0], 
                                line.end_point[1] - line.start_point[1]])
            line_normal = np.array([-line_vec[1], line_vec[0]])  # Perpendicular vector
            
            track_vec = np.array([current_pos[0] - line.start_point[0], 
                                 current_pos[1] - line.start_point[1]])
            
            side = np.sign(np.dot(track_vec, line_normal))
            
            crossing_key = f"{track.id}_{line.id}"
            
            if crossing_key in self.crossing_memory:
                last_side, last_pos = self.crossing_memory[crossing_key]
                
                # Check if crossing occurred
                if last_side != 0 and side != 0 and last_side != side:
                    # Determine crossing direction
                    direction = "a_to_b" if side > 0 else "b_to_a"
                    
                    # Check if this direction is allowed
                    if line.direction in ["both", direction]:
                        # Create crossing event
                        event = Event(
                            id=str(uuid.uuid4()),
                            event_type="line_crossing",
                            camera_id=track.camera_id,
                            track_id=track.id,
                            start_time=track.last_seen,
                            end_time=track.last_seen,
                            severity="low",
                            zone_id=line.id,  # Using zone_id for line ID
                            event_data={
                                "object_class": track.object_class,
                                "line_name": line.name,
                                "crossing_point": current_pos,
                                "direction": direction,
                                "confidence": track.confidence_avg
                            }
                        )
                        events.append(event)
            
            # Update memory
            self.crossing_memory[crossing_key] = [side, current_pos]
        
        return events

class EventProcessor:
    """Main event processor that coordinates all detection."""
    
    def __init__(self):
        self.redis_client = self._connect_redis()
        self.trackers: Dict[str, ByteTrack] = {}  # camera_id -> tracker
        self.zones: Dict[str, List[Zone]] = {}    # camera_id -> zones
        self.lines: Dict[str, List[Line]] = {}    # camera_id -> lines
        
        # Event detectors
        self.intrusion_detector = IntrusionDetector()
        self.loitering_detector = LoiteringDetector()
        self.line_crossing_detector = LineCrossingDetector()
        
        self.running = False
        self.stats = {
            'detections_processed': 0,
            'events_generated': 0,
            'active_tracks': 0,
            'processing_time_avg': 0.0
        }
    
    def _connect_redis(self) -> redis.Redis:
        """Connect to Redis."""
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
        """Deserialize detection data from Redis."""
        try:
            data = json.loads(detection_data.decode('utf-8'))
            
            detections = []
            for det_data in data.get('detections', []):
                detection = Detection(
                    camera_id=data['camera_id'],
                    frame_id=data['frame_id'],
                    timestamp=datetime.fromisoformat(data['timestamp']),
                    object_class=det_data['class_name'],
                    confidence=det_data['confidence'],
                    bbox=det_data['bbox'],
                    track_id=det_data.get('track_id'),
                    features=det_data.get('features')
                )
                detections.append(detection)
            
            return detections
            
        except Exception as e:
            logger.error(f"Failed to deserialize detections: {e}")
            return []
    
    def _serialize_event(self, event: Event) -> bytes:
        """Serialize event for Redis."""
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
        # This would typically load from a database
        # For now, we'll create some example configurations
        
        # Example zones
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
        
        # Example lines
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
        
        # Organize by camera
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
        """Process detections and generate events."""
        events = []
        
        # Initialize tracker for camera if needed
        if camera_id not in self.trackers:
            self.trackers[camera_id] = ByteTrack()
        
        # Update tracker
        tracks = self.trackers[camera_id].update(detections)
        
        # Get zones and lines for this camera
        zones = self.zones.get(camera_id, [])
        lines = self.lines.get(camera_id, [])
        
        # Run event detectors
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
        
        return events
    
    async def process_detection_queue(self):
        """Process detections from Redis queue."""
        self.running = True
        
        # Load zones and lines
        self._load_zones_and_lines()
        
        logger.info("Event processor started")
        
        while self.running:
            try:
                # Get detection from queue
                detection_data = self.redis_client.lpop('detection_queue')
                if detection_data is None:
                    await asyncio.sleep(0.01)
                    continue
                
                # Deserialize detections
                start_time = time.time()
                detections = self._deserialize_detections(detection_data)
                
                if not detections:
                    continue
                
                # Process detections
                camera_id = detections[0].camera_id
                events = self._process_detections(camera_id, detections)
                
                # Publish events
                for event in events:
                    event_data = self._serialize_event(event)
                    
                    # Send to backend API
                    self.redis_client.rpush('event_queue', event_data)
                    
                    # Also publish to WebSocket clients
                    self.redis_client.publish('surveillance_events', event_data)
                
                # Update stats
                processing_time = time.time() - start_time
                self.stats['detections_processed'] += len(detections)
                self.stats['events_generated'] += len(events)
                self.stats['active_tracks'] = sum(len(tracker.tracks) for tracker in self.trackers.values())
                
                # Update average processing time
                total_processed = self.stats['detections_processed']
                current_avg = self.stats['processing_time_avg']
                self.stats['processing_time_avg'] = (
                    (current_avg * (total_processed - len(detections)) + processing_time) / total_processed
                )
                
                logger.debug(f"Processed {len(detections)} detections, generated {len(events)} events")
                
            except Exception as e:
                logger.error(f"Error processing detections: {e}")
                await asyncio.sleep(0.1)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get processor statistics."""
        return {
            'detections_processed': self.stats['detections_processed'],
            'events_generated': self.stats['events_generated'],
            'active_tracks': self.stats['active_tracks'],
            'processing_time_avg': self.stats['processing_time_avg'],
            'trackers_count': len(self.trackers),
            'zones_count': sum(len(zones) for zones in self.zones.values()),
            'lines_count': sum(len(lines) for lines in self.lines.values())
        }
    
    async def start(self):
        """Start the event processor."""
        await self.process_detection_queue()
    
    def stop(self):
        """Stop the event processor."""
        self.running = False
        logger.info("Event processor stopped")

if __name__ == "__main__":
    processor = EventProcessor()
    
    try:
        asyncio.run(processor.start())
    except KeyboardInterrupt:
        processor.stop()
        logger.info("Event processor stopped by user")
