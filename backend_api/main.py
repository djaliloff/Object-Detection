from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, APIRouter, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import redis
import json
import asyncio
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
import structlog

# Ensure the backend directory is in the path for reliable imports
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
# pyrefly: ignore [missing-import]
from database import get_db, engine, Base
# pyrefly: ignore [missing-import]
from models import User, Camera, CameraGroup, Event, Zone, Detection
# pyrefly: ignore [missing-import]
from schemas import (
    UserCreate, User as UserSchema, CameraCreate, Camera as CameraSchema,
    CameraGroupCreate, CameraGroup as CameraGroupSchema, EventCreate, Event as EventSchema,
    ZoneCreate, Zone as ZoneSchema, ZoneUpdate, LoginRequest, Token, AnalyticsSummary,
    WebSocketMessage, FrameUpdate, EventAlert, CameraStatusUpdate
)
# pyrefly: ignore [missing-import]
from auth import (
    authenticate_user, create_access_token, get_current_active_user,
    require_admin, require_operator_or_admin, ACCESS_TOKEN_EXPIRE_MINUTES
)

from contextlib import asynccontextmanager

# Configure structured logging
import structlog
logger = structlog.get_logger()

# --- Performance Tunables (via .env) ---
MJPEG_IDLE_SLEEP    = float(os.getenv("MJPEG_IDLE_SLEEP", "0.016"))   # seconds (~60 fps cap)
WS_DETECTION_INTERVAL = float(os.getenv("WS_DETECTION_INTERVAL", "0.1"))  # seconds

# Create database tables (only if database is available)
try:
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")
except Exception as e:
    # Use print if logger fails during init
    print(f"Database connection failed: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start background task for Redis messages
    asyncio.create_task(process_redis_messages())
    yield
    # Shutdown logic (if any) could go here

# FastAPI app
app = FastAPI(
    title="Multi-Modal Video Surveillance API",
    description="AI-powered video surveillance platform with RGB/thermal fusion",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:80",
        "http://127.0.0.1:80",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Redis connection and global frame cache
LATEST_FRAMES = {}  # camera_id -> raw JPEG bytes

def _make_redis_client():
    try:
        client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            decode_responses=False,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        client.ping()
        logger.info("Connected to Redis")
        return client
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        return None

redis_client = _make_redis_client()

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.camera_subscriptions: dict = {}  # camera_id -> list of connections
        self.global_subscribers: List[WebSocket] = []
        # --- OPTIMISATION: per-camera last-broadcast time to throttle detection WS spam ---
        self._last_detection_broadcast: dict = {}

    async def connect(self, websocket: WebSocket, camera_id: Optional[str] = None):
        await websocket.accept()
        self.active_connections.append(websocket)
        
        if camera_id:
            if camera_id not in self.camera_subscriptions:
                self.camera_subscriptions[camera_id] = []
            self.camera_subscriptions[camera_id].append(websocket)

    def subscribe_global(self, websocket: WebSocket):
        if websocket not in self.global_subscribers:
            self.global_subscribers.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self.global_subscribers:
            self.global_subscribers.remove(websocket)
        # Remove from camera subscriptions
        for camera_id, connections in self.camera_subscriptions.items():
            if websocket in connections:
                connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: dict, camera_id: Optional[str] = None):
        # --- OPTIMISATION: rate-limit detection broadcasts per camera ---
        if message.get('type') == 'detection' and camera_id:
            now = time.monotonic()
            last = self._last_detection_broadcast.get(camera_id, 0.0)
            if now - last < WS_DETECTION_INTERVAL:
                return  # too soon — skip this broadcast
            self._last_detection_broadcast[camera_id] = now
            
        message_json = json.dumps(message)
        is_event = message.get('event_type') is not None
        
        # Always send events to global subscribers first
        if is_event and self.global_subscribers:
            disconnected_globals = []
            for connection in self.global_subscribers:
                try:
                    await connection.send_text(message_json)
                except:
                    disconnected_globals.append(connection)
            for conn in disconnected_globals:
                self.global_subscribers.remove(conn)
                if conn in self.active_connections:
                    self.active_connections.remove(conn)

        if camera_id and camera_id in self.camera_subscriptions:
            # Send to specific camera subscribers
            disconnected = []
            for connection in self.camera_subscriptions[camera_id]:
                try:
                    await connection.send_text(message_json)
                    if message.get('type') == 'detection':
                        logger.debug(f"Broadcasted detection for camera {camera_id} to a subscriber")
                except:
                    disconnected.append(connection)
            
            # Clean up disconnected connections
            for conn in disconnected:
                self.camera_subscriptions[camera_id].remove(conn)
                if conn in self.active_connections:
                    self.active_connections.remove(conn)
        elif not camera_id:
            # Broadcast to all connections
            disconnected = []
            for connection in self.active_connections:
                try:
                    await connection.send_text(message_json)
                except:
                    disconnected.append(connection)
            
            # Clean up disconnected connections
            for conn in disconnected:
                self.active_connections.remove(conn)

manager = ConnectionManager()

# API v1 Router
api_v1_router = APIRouter()

# Health check endpoint
@app.get("/health")
async def health_check():
    from datetime import UTC
    return {"status": "healthy", "timestamp": datetime.now(UTC)}

@api_v1_router.get("/cameras/{camera_id}/mjpeg")
async def stream_camera_mjpeg(camera_id: str):
    """
    High-speed MJPEG stream — reads from memory cache (pub/sub) with Redis fallback.
    """
    BOUNDARY = b"--frame\r\n"
    CONTENT_TYPE = b"Content-Type: image/jpeg\r\nCache-Control: no-cache\r\n\r\n"

    async def frame_generator():
        last_frame_bytes = None
        idle_cycles = 0

        while True:
            try:
                # 1) Hot path: in-memory cache populated by pub/sub listener
                frame_bytes = LATEST_FRAMES.get(camera_id)

                # 2) Cold / recovery path: poll Redis key directly
                if not frame_bytes and redis_client:
                    try:
                        frame_bytes = await asyncio.to_thread(
                            redis_client.get, f"latest_frame_jpg:{camera_id}"
                        )
                        if frame_bytes:
                            # Populate the cache so future iterations are fast
                            LATEST_FRAMES[camera_id] = frame_bytes
                    except Exception:
                        pass

                if frame_bytes:
                    idle_cycles = 0
                    # --- OPTIMISATION: only send if frame actually changed (pointer comparison) ---
                    if frame_bytes is not last_frame_bytes:
                        last_frame_bytes = frame_bytes
                        yield BOUNDARY + CONTENT_TYPE + frame_bytes + b"\r\n"
                    
                    # --- OPTIMISATION: fixed sleep avoids a hot busy-loop ---
                    await asyncio.sleep(MJPEG_IDLE_SLEEP)
                else:
                    idle_cycles += 1
                    # Fixed small sleep — no exponential backoff that would stall reconnecting streams
                    await asyncio.sleep(0.016)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"MJPEG stream error for {camera_id}: {e}")
                await asyncio.sleep(0.5)

    return StreamingResponse(
        frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Access-Control-Allow-Origin": "*",
            "X-Accel-Buffering": "no",
        },
    )









@api_v1_router.get("/cameras/{camera_id}/snapshot.jpg")
async def get_camera_snapshot(camera_id: str):
    """Return the latest gateway frame as a JPEG snapshot."""
    if not redis_client:
        raise HTTPException(status_code=503, detail="Redis is not available")

    frame_bytes = redis_client.get(f"latest_frame_jpg:{camera_id}")
    if not frame_bytes:
        raise HTTPException(status_code=404, detail="No frame available for this camera")

    return Response(
        content=frame_bytes,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )



# Authentication endpoints
@api_v1_router.post("/auth/login", response_model=Token)
async def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, login_data.username, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role},
        expires_delta=access_token_expires
    )
    
    logger.info(f"User {user.username} logged in successfully")
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }

# User management endpoints
@api_v1_router.get("/users", response_model=List[UserSchema])
async def get_users(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    users = db.query(User).all()
    return users

@api_v1_router.post("/users", response_model=UserSchema)
async def create_user(
    user_data: UserCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    # Check if user already exists
    existing_user = db.query(User).filter(
        (User.username == user_data.username) | (User.email == user_data.email)
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered"
        )
    
    from auth import get_password_hash
    hashed_password = get_password_hash(user_data.password)
    
    db_user = User(
        username=user_data.username,
        email=user_data.email,
        password_hash=hashed_password,
        role=user_data.role
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    logger.info(f"User {user_data.username} created by admin {current_user.username}")
    return db_user

# Camera management endpoints
@api_v1_router.get("/cameras", response_model=List[CameraSchema])
async def get_cameras(
    db: Session = Depends(get_db)
):
    cameras = db.query(Camera).all()
    return cameras

@api_v1_router.post("/cameras", response_model=CameraSchema)
async def create_camera(
    camera_data: CameraCreate,
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db)
):
    db_camera = Camera(**camera_data.dict())
    db.add(db_camera)
    db.commit()
    db.refresh(db_camera)
    
    # Notify gateway to hot-load the new camera
    if redis_client:
        redis_client.publish('camera_updates', json.dumps({
            'action': 'add',
            'camera_id': str(db_camera.id)
        }))
    
    logger.info(f"Camera {camera_data.name} created by {current_user.username}")
    return db_camera

@api_v1_router.get("/cameras/{camera_id}", response_model=CameraSchema)
async def get_camera(
    camera_id: str,
    db: Session = Depends(get_db)
):
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    return camera

@api_v1_router.put("/cameras/{camera_id}", response_model=CameraSchema)
async def update_camera(
    camera_id: str,
    camera_data: dict,
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db)
):
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    for key, value in camera_data.items():
        if hasattr(camera, key) and value is not None:
            setattr(camera, key, value)
    
    db.commit()
    db.refresh(camera)
    
    logger.info(f"Camera {camera.name} updated by {current_user.username}")
    return camera

@api_v1_router.delete("/cameras/{camera_id}")
async def delete_camera(
    camera_id: str,
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db)
):
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    db.delete(camera)
    db.commit()
    
    # Notify other services via Redis
    if redis_client:
        redis_client.publish('camera_updates', json.dumps({
            'action': 'delete',
            'camera_id': camera_id
        }))
    
    logger.info(f"Camera {camera.name} deleted by {current_user.username}")
    return {"message": "Camera deleted successfully"}

# Bulk operations
@api_v1_router.post("/cameras/bulk-delete")
async def bulk_delete_cameras(
    camera_ids: List[str],
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db)
):
    count = db.query(Camera).filter(Camera.id.in_(camera_ids)).delete(synchronize_session=False)
    db.commit()
    return {"message": f"Successfully deleted {count} cameras"}

@api_v1_router.post("/cameras/bulk-update-status")
async def bulk_update_camera_status(
    camera_ids: List[str],
    status: str,
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db)
):
    db.query(Camera).filter(Camera.id.in_(camera_ids)).update({"status": status}, synchronize_session=False)
    db.commit()
    return {"message": f"Successfully updated status for selected cameras"}

# Camera group endpoints
@api_v1_router.get("/camera-groups", response_model=List[CameraGroupSchema])
async def get_camera_groups(
    db: Session = Depends(get_db)
):
    groups = db.query(CameraGroup).all()
    return groups

@api_v1_router.post("/camera-groups", response_model=CameraGroupSchema)
async def create_camera_group(
    group_data: CameraGroupCreate,
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db)
):
    db_group = CameraGroup(**group_data.dict())
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    
    logger.info(f"Camera group {group_data.name} created by {current_user.username}")
    return db_group

# Zone management endpoints
@api_v1_router.get("/zones", response_model=List[ZoneSchema])
async def get_zones(
    camera_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Zone)
    if camera_id:
        query = query.filter(Zone.camera_id == camera_id)
    return query.all()

@api_v1_router.post("/zones", response_model=ZoneSchema)
async def create_zone(
    zone_data: ZoneCreate,
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db)
):
    db_zone = Zone(**zone_data.dict())
    db.add(db_zone)
    db.commit()
    db.refresh(db_zone)
    
    logger.info(f"Zone {zone_data.name} created by {current_user.username}")
    return db_zone

@api_v1_router.put("/zones/{zone_id}", response_model=ZoneSchema)
async def update_zone(
    zone_id: str,
    zone_data: ZoneUpdate,
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db)
):
    db_zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not db_zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    
    update_data = zone_data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_zone, key, value)
    
    db.commit()
    db.refresh(db_zone)
    logger.info(f"Zone {zone_id} updated by {current_user.username}")
    return db_zone

@api_v1_router.delete("/zones/{zone_id}")
async def delete_zone(
    zone_id: str,
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db)
):
    db_zone = db.query(Zone).filter(Zone.id == zone_id).first()
    if not db_zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    
    db.delete(db_zone)
    db.commit()
    logger.info(f"Zone {zone_id} deleted by {current_user.username}")
    return {"message": "Zone deleted successfully"}

# Event endpoints
@api_v1_router.get("/events", response_model=List[EventSchema])
async def get_events(
    camera_id: Optional[str] = None,
    event_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    query = db.query(Event)
    
    if camera_id:
        query = query.filter(Event.camera_id == camera_id)
    if event_type:
        query = query.filter(Event.event_type == event_type)
    if status:
        query = query.filter(Event.status == status)
    
    return query.order_by(Event.created_at.desc()).offset(offset).limit(limit).all()

@api_v1_router.put("/events/{event_id}/status")
async def update_event_status(
    event_id: str,
    status_data: dict,
    current_user: User = Depends(require_operator_or_admin),
    db: Session = Depends(get_db)
):
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    event.status = status_data.get("status", event.status)
    db.commit()
    
    logger.info(f"Event {event_id} status updated to {event.status} by {current_user.username}")
    return {"message": "Event status updated successfully"}

# Analytics endpoint
@api_v1_router.get("/analytics/summary", response_model=AnalyticsSummary)
async def get_analytics_summary(
    db: Session = Depends(get_db)
):
    total_cameras = db.query(Camera).count()
    online_cameras = db.query(Camera).filter(Camera.status == "online").count()
    total_detections = db.query(Detection).count()
    total_events = db.query(Event).count()
    new_events = db.query(Event).filter(Event.status == "new").count()
    
    # Calculate average FPS and uptime from Redis or database
    avg_fps = 15.0  # Default value
    uptime_percentage = 95.0  # Default value
    
    return AnalyticsSummary(
        total_cameras=total_cameras,
        online_cameras=online_cameras,
        total_detections=total_detections,
        total_events=total_events,
        new_events=new_events,
        avg_fps=avg_fps,
        uptime_percentage=uptime_percentage
    )

# Include API Router
# Upload video file for looped detection
@api_v1_router.post("/cameras/upload-video")
async def upload_video(
    file: UploadFile = File(...),
    modality: str = "rgb",  # "rgb" or "thermal"
    current_user: User = Depends(get_current_active_user)
):
    # Route to the correct subfolder based on modality
    modality_clean = modality.strip().lower()
    subfolder = "Thermal" if modality_clean == "thermal" else "RGB"
    
    upload_dir = os.path.join(os.getcwd(), "uploads", "tactical_archives", subfolder)
    os.makedirs(upload_dir, exist_ok=True)
    
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is missing or invalid")
        
    file_path = os.path.join(upload_dir, file.filename)
    with open(file_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
    
    web_url = f"/uploads/tactical_archives/{subfolder}/{file.filename}"
    return {
        "filename": file.filename,
        "file_path": os.path.abspath(file_path),
        "web_url": web_url,
        "modality": modality_clean,
        "subfolder": subfolder,
    }


from fastapi.staticfiles import StaticFiles

os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.include_router(api_v1_router, prefix="/api/v1")

# WebSocket endpoint
@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket, camera_id: Optional[str] = None):
    await manager.connect(websocket, camera_id)
    try:
        while True:
            data_str = await websocket.receive_text()
            try:
                msg = json.loads(data_str)
                if msg.get("type") == "subscribe" and "camera_id" in msg:
                    cam_id = msg["camera_id"]
                    if cam_id not in manager.camera_subscriptions:
                        manager.camera_subscriptions[cam_id] = []
                    if websocket not in manager.camera_subscriptions[cam_id]:
                        manager.camera_subscriptions[cam_id].append(websocket)
                elif msg.get("type") == "subscribe_global":
                    # Register this connection to receive ALL events regardless of camera
                    manager.subscribe_global(websocket)
                    logger.info("Client subscribed to global event stream")
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Background task to process Redis messages and broadcast to WebSocket clients
async def process_redis_messages():
    """Ultra-reliable Redis Pub/Sub processor with auto-reconnect."""
    import threading
    global redis_client  # allow reconnection

    def redis_listener_thread():
        """Synchronous thread to handle blocking Redis listen() with reconnect."""
        while True:
            rc = redis_client
            if not rc:
                time.sleep(3)
                rc = _make_redis_client()
                if rc:
                    globals()['redis_client'] = rc  # type: ignore[name-defined]
                continue
            try:
                pubsub = rc.pubsub()
                pubsub.subscribe("surveillance_events", "camera_status", "surveillance_detections")
                pubsub.psubscribe("display_frame:*")
                logger.info("Redis Pub/Sub listener thread (re)started")

                for message in pubsub.listen():
                    msg_type = message.get("type")
                    if msg_type in ["message", "pmessage"]:
                        channel = message.get("channel")
                        if isinstance(channel, bytes):
                            channel = channel.decode('utf-8')
                        if channel and "display_frame:" in channel:
                            try:
                                cam_id = channel.split(":", 1)[1]
                                LATEST_FRAMES[cam_id] = message.get("data")
                            except:
                                pass
            except Exception as e:
                logger.warning(f"Redis listener disconnected, reconnecting in 3s: {e}")
                time.sleep(3)
                new_rc = _make_redis_client()
                if new_rc:
                    globals()['redis_client'] = new_rc  # type: ignore[name-defined]

    threading.Thread(target=redis_listener_thread, daemon=True).start()

    # Second Pub/Sub for regular events (non-performance critical)
    while True:
        try:
            rc = redis_client
            if not rc:
                await asyncio.sleep(3)
                new_rc = _make_redis_client()
                if new_rc:
                    redis_client = new_rc
                continue

            event_pubsub = rc.pubsub()
            event_pubsub.subscribe("surveillance_events", "camera_status", "surveillance_detections")

            while True:
                msg = await asyncio.to_thread(event_pubsub.get_message, ignore_subscribe_messages=True)
                if msg and msg.get("type") == "message":
                    channel_raw = msg.get("channel")
                    if channel_raw is None:
                        await asyncio.sleep(0.01)
                        continue

                    channel = channel_raw.decode('utf-8') if isinstance(channel_raw, bytes) else channel_raw
                    raw_data = msg.get("data")
                    if raw_data is None:
                        await asyncio.sleep(0.01)
                        continue

                    data = json.loads(raw_data)
                    if channel in ["surveillance_events", "camera_status"]:
                        await manager.broadcast(data, data.get("camera_id"))
                    elif channel == "surveillance_detections":
                        if 'type' not in data:
                            data['type'] = 'detection'
                        await manager.broadcast(data, data.get("camera_id"))

                await asyncio.sleep(0.01)

        except Exception as e:
            logger.error(f"Error in Event processor: {e}")
            await asyncio.sleep(3)

# Background task task already started via lifespan context manager

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)