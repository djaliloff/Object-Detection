from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, Text, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import uuid

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="viewer")  # admin, operator, viewer
    last_login = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class CameraGroup(Base):
    __tablename__ = "camera_groups"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    location = Column(String(200))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    cameras = relationship("Camera", back_populates="group")

class Camera(Base):
    __tablename__ = "cameras"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    ip = Column(String(45), nullable=False)
    port = Column(Integer, default=554)
    rtsp_url = Column(String(500), nullable=False)
    hls_url = Column(String(500))
    webrtc_url = Column(String(500))
    mjpeg_url = Column(String(500))
    stream_url = Column(String(500))
    credentials = Column(JSONB)  # Encrypted credentials
    modality = Column(String(20), nullable=False, default="rgb")  # rgb, thermal, rgb_t
    group_id = Column(UUID(as_uuid=True), ForeignKey("camera_groups.id"))
    location = Column(String(200))
    resolution = Column(String(20), default="1920x1080")
    fps = Column(Integer, default=30)
    is_active = Column(Boolean, default=True)
    is_recording = Column(Boolean, default=False)
    detection_enabled = Column(Boolean, default=True)
    ptz_enabled = Column(Boolean, default=False)
    thermal_min = Column(Float, default=20.0)
    thermal_max = Column(Float, default=45.0)
    config_json = Column(JSONB)
    status = Column(String(20), default="online")  # online, offline, error
    last_seen = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    group = relationship("CameraGroup", back_populates="cameras")
    frames = relationship("Frame", back_populates="camera", cascade="all, delete-orphan")
    detections = relationship("Detection", back_populates="camera", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="camera", cascade="all, delete-orphan")
    zones = relationship("Zone", back_populates="camera", cascade="all, delete-orphan")

class Frame(Base):
    __tablename__ = "frames"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_id = Column(UUID(as_uuid=True), ForeignKey("cameras.id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    frame_number = Column(Integer, nullable=False)
    modality = Column(String(20), nullable=False)
    resolution = Column(String(20))  # "1920x1080"
    storage_path = Column(String(500))
    file_size = Column(Integer)  # bytes
    
    camera = relationship("Camera", back_populates="frames")
    detections = relationship("Detection", back_populates="frame")

class Detection(Base):
    __tablename__ = "detections"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    frame_id = Column(UUID(as_uuid=True), ForeignKey("frames.id"), nullable=False)
    camera_id = Column(UUID(as_uuid=True), ForeignKey("cameras.id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    object_class = Column(String(50), nullable=False)
    bbox = Column(JSONB, nullable=False)  # {"x1": 0, "y1": 0, "x2": 100, "y2": 100}
    confidence = Column(Float, nullable=False)
    track_id = Column(Integer)
    features_json = Column(JSONB)  # Re-ID features
    
    frame = relationship("Frame", back_populates="detections")
    camera = relationship("Camera", back_populates="detections")

class Track(Base):
    __tablename__ = "tracks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    camera_id = Column(UUID(as_uuid=True), ForeignKey("cameras.id"), nullable=False)
    object_class = Column(String(50), nullable=False)
    first_seen = Column(DateTime(timezone=True), nullable=False)
    last_seen = Column(DateTime(timezone=True), nullable=False)
    track_length = Column(Integer, default=0)
    avg_confidence = Column(Float)
    
    camera = relationship("Camera")

class Event(Base):
    __tablename__ = "events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(50), nullable=False)  # intrusion, loitering, line_crossing, abandoned_object
    camera_id = Column(UUID(as_uuid=True), ForeignKey("cameras.id"), nullable=False)
    track_id = Column(Integer)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True))
    severity = Column(String(20), default="medium")  # low, medium, high, critical
    zone_id = Column(UUID(as_uuid=True), ForeignKey("zones.id"))
    event_data = Column(JSONB)  # Additional event-specific data
    status = Column(String(20), default="new")  # new, viewed, resolved
    snapshot_refs = Column(JSONB)  # Paths to snapshot images
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    camera = relationship("Camera", back_populates="events")
    zone = relationship("Zone", back_populates="events")

class Zone(Base):
    __tablename__ = "zones"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_id = Column(UUID(as_uuid=True), ForeignKey("cameras.id"), nullable=False)
    name = Column(String(100), nullable=False)
    polygon = Column(JSONB)  # For polygon zones: [[x1, y1], [x2, y2], ...]
    zone_type = Column(String(20), nullable=False)  # exclusion, counting, alert
    is_active = Column(Boolean, default=True)
    config_json = Column(JSONB)  # Zone-specific config
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    camera = relationship("Camera", back_populates="zones")
    events = relationship("Event", back_populates="zone")

class AuditLog(Base):
    __tablename__ = "audit_log"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    action = Column(String(100), nullable=False)
    resource = Column(String(100))
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    details_json = Column(JSONB)
    
    user = relationship("User")
