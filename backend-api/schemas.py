from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum

class UserRole(str, Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"

class CameraModality(str, Enum):
    RGB = "rgb"
    THERMAL = "thermal"
    RGB_T = "rgb_t"
    MJPEG = "mjpeg"
    FUSED = "fused"
    VIDEO = "video"

class CameraStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"

class EventType(str, Enum):
    INTRUSION = "intrusion"
    LOITERING = "loitering"
    LINE_CROSSING = "line_crossing"
    ABANDONED_OBJECT = "abandoned_object"

class EventSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class EventStatus(str, Enum):
    NEW = "new"
    VIEWED = "viewed"
    RESOLVED = "resolved"

class ZoneType(str, Enum):
    EXCLUSION = "exclusion"
    COUNTING = "counting"
    ALERT = "alert"

# User schemas
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., pattern=r'^[^@]+@[^@]+\.[^@]+$')
    role: UserRole = UserRole.VIEWER

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[str] = Field(None, pattern=r'^[^@]+@[^@]+\.[^@]+$')
    role: Optional[UserRole] = None
    password: Optional[str] = Field(None, min_length=8)

class User(UserBase):
    id: UUID
    last_login: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

# Camera schemas
class CameraBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    ip: str = Field(..., pattern=r'^(\d{1,3}\.){3}\d{1,3}$')
    port: int = Field(default=554, ge=0, le=65535)
    rtsp_url: str = Field(..., min_length=1)
    hls_url: Optional[str] = None
    webrtc_url: Optional[str] = None
    mjpeg_url: Optional[str] = None
    stream_url: Optional[str] = None
    modality: CameraModality = CameraModality.RGB
    group_id: Optional[UUID] = None
    location: Optional[str] = None
    resolution: str = "1920x1080"
    fps: int = 30
    is_active: bool = True
    is_recording: bool = False
    detection_enabled: bool = True
    ptz_enabled: bool = False
    thermal_min: float = 20.0
    thermal_max: float = 45.0
    config_json: Optional[Dict[str, Any]] = None

class CameraCreate(CameraBase):
    status: CameraStatus = CameraStatus.ONLINE
    credentials: Optional[Dict[str, str]] = None

class CameraUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    ip: Optional[str] = Field(None, pattern=r'^(\d{1,3}\.){3}\d{1,3}$')
    port: Optional[int] = Field(None, ge=0, le=65535)
    rtsp_url: Optional[str] = Field(None, min_length=1)
    hls_url: Optional[str] = None
    webrtc_url: Optional[str] = None
    mjpeg_url: Optional[str] = None
    stream_url: Optional[str] = None
    modality: Optional[CameraModality] = None
    group_id: Optional[UUID] = None
    location: Optional[str] = None
    resolution: Optional[str] = None
    fps: Optional[int] = None
    is_active: Optional[bool] = None
    is_recording: Optional[bool] = None
    detection_enabled: Optional[bool] = None
    ptz_enabled: Optional[bool] = None
    thermal_min: Optional[float] = None
    thermal_max: Optional[float] = None
    status: Optional[CameraStatus] = None
    config_json: Optional[Dict[str, Any]] = None
    credentials: Optional[Dict[str, str]] = None

class Camera(CameraBase):
    id: UUID
    status: CameraStatus
    last_seen: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

class CameraHealth(BaseModel):
    camera_id: UUID
    fps: float
    frame_count: int
    errors: int
    last_frame: Optional[datetime]
    uptime_percentage: float

# Camera Group schemas
class CameraGroupBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    location: Optional[str] = None

class CameraGroupCreate(CameraGroupBase):
    pass

class CameraGroup(CameraGroupBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

# Detection schemas
class BBox(BaseModel):
    x1: float = Field(..., ge=0)
    y1: float = Field(..., ge=0)
    x2: float = Field(..., ge=0)
    y2: float = Field(..., ge=0)

class DetectionBase(BaseModel):
    object_class: str = Field(..., min_length=1)
    bbox: BBox
    confidence: float = Field(..., ge=0.0, le=1.0)
    track_id: Optional[int] = None
    features_json: Optional[Dict[str, Any]] = None

class DetectionCreate(DetectionBase):
    frame_id: UUID
    camera_id: UUID
    timestamp: datetime

class Detection(DetectionBase):
    id: UUID
    frame_id: UUID
    camera_id: UUID
    timestamp: datetime

    class Config:
        from_attributes = True

# Event schemas
class EventBase(BaseModel):
    event_type: EventType
    camera_id: UUID
    track_id: Optional[int] = None
    severity: EventSeverity = EventSeverity.MEDIUM
    zone_id: Optional[UUID] = None
    event_data: Optional[Dict[str, Any]] = None

class EventCreate(EventBase):
    start_time: datetime
    end_time: Optional[datetime] = None

class EventUpdate(BaseModel):
    status: EventStatus
    end_time: Optional[datetime] = None

class Event(EventBase):
    id: UUID
    start_time: datetime
    end_time: Optional[datetime]
    status: EventStatus
    snapshot_refs: Optional[Dict[str, str]] = None
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

# Zone schemas
class ZoneBase(BaseModel):
    camera_id: UUID
    name: str = Field(..., min_length=1, max_length=100)
    polygon: Optional[List[List[float]]] = None  # [[x1, y1], [x2, y2], ...]
    zone_type: ZoneType
    is_active: bool = True
    config_json: Optional[Dict[str, Any]] = None

class ZoneCreate(ZoneBase):
    pass

class ZoneUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    polygon: Optional[List[List[float]]] = None
    zone_type: Optional[ZoneType] = None
    is_active: Optional[bool] = None
    config_json: Optional[Dict[str, Any]] = None

class Zone(ZoneBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

# Authentication schemas
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

# Analytics schemas
class AnalyticsSummary(BaseModel):
    total_cameras: int
    online_cameras: int
    total_detections: int
    total_events: int
    new_events: int
    avg_fps: float
    uptime_percentage: float

class DetectionStats(BaseModel):
    object_class: str
    count: int
    confidence_avg: float
    timeline: List[Dict[str, Any]]  # [{"timestamp": "...", "count": 123}, ...]

class EventStats(BaseModel):
    event_type: str
    count: int
    severity_breakdown: Dict[str, int]

# WebSocket message schemas
class WebSocketMessage(BaseModel):
    type: str
    data: Dict[str, Any]
    timestamp: datetime

class FrameUpdate(BaseModel):
    camera_id: UUID
    frame_data: str  # base64 encoded
    detections: List[Detection]
    timestamp: datetime

class EventAlert(BaseModel):
    event_id: UUID
    event_type: EventType
    severity: EventSeverity
    camera_id: UUID
    camera_name: str
    timestamp: datetime
    thumbnail: Optional[str] = None  # base64 encoded

class CameraStatusUpdate(BaseModel):
    camera_id: UUID
    status: CameraStatus
    message: Optional[str] = None
    timestamp: datetime
