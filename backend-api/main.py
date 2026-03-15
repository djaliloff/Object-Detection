from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import redis
import json
import asyncio
import os
from datetime import datetime, timedelta
import structlog

from database import get_db, engine, Base
from models import User, Camera, CameraGroup, Event, Zone, Detection
from schemas import (
    UserCreate, User as UserSchema, CameraCreate, Camera as CameraSchema,
    CameraGroupCreate, CameraGroup as CameraGroupSchema, EventCreate, Event as EventSchema,
    ZoneCreate, Zone as ZoneSchema, LoginRequest, Token, AnalyticsSummary,
    WebSocketMessage, FrameUpdate, EventAlert, CameraStatusUpdate
)
from auth import (
    authenticate_user, create_access_token, get_current_active_user,
    require_admin, require_operator_or_admin, ACCESS_TOKEN_EXPIRE_MINUTES
)

from contextlib import asynccontextmanager

# Configure structured logging
logger = structlog.get_logger()

# Create database tables (only if database is available)
try:
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")
except Exception as e:
    logger.warning(f"Database connection failed, running without database: {e}")

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
    allow_origins=["http://localhost:3000", "http://localhost:80"],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Redis connection
try:
    redis_client = redis.Redis(
        host=os.getenv("REDIS_HOST", "localhost"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        decode_responses=False
    )
    redis_client.ping()
    logger.info("Connected to Redis")
except Exception as e:
    logger.error(f"Failed to connect to Redis: {e}")
    redis_client = None

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.camera_subscriptions: dict = {}  # camera_id -> list of connections

    async def connect(self, websocket: WebSocket, camera_id: Optional[str] = None):
        await websocket.accept()
        self.active_connections.append(websocket)
        
        if camera_id:
            if camera_id not in self.camera_subscriptions:
                self.camera_subscriptions[camera_id] = []
            self.camera_subscriptions[camera_id].append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        
        # Remove from camera subscriptions
        for camera_id, connections in self.camera_subscriptions.items():
            if websocket in connections:
                connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: dict, camera_id: Optional[str] = None):
        message_json = json.dumps(message)
        
        if camera_id and camera_id in self.camera_subscriptions:
            # Send to specific camera subscribers
            disconnected = []
            for connection in self.camera_subscriptions[camera_id]:
                try:
                    await connection.send_text(message_json)
                except:
                    disconnected.append(connection)
            
            # Clean up disconnected connections
            for conn in disconnected:
                self.camera_subscriptions[camera_id].remove(conn)
                if conn in self.active_connections:
                    self.active_connections.remove(conn)
        else:
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
    return {"status": "healthy", "timestamp": datetime.utcnow()}

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
    current_user: User = Depends(get_current_active_user),
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
    
    logger.info(f"Camera {camera_data.name} created by {current_user.username}")
    return db_camera

@api_v1_router.get("/cameras/{camera_id}", response_model=CameraSchema)
async def get_camera(
    camera_id: str,
    current_user: User = Depends(get_current_active_user),
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
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    db.delete(camera)
    db.commit()
    
    logger.info(f"Camera {camera.name} deleted by {current_user.username}")
    return {"message": "Camera deleted successfully"}

# Bulk operations
@api_v1_router.post("/cameras/bulk-delete")
async def bulk_delete_cameras(
    camera_ids: List[str],
    current_user: User = Depends(require_admin),
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
    current_user: User = Depends(get_current_active_user),
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
    current_user: User = Depends(get_current_active_user),
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

# Event endpoints
@api_v1_router.get("/events", response_model=List[EventSchema])
async def get_events(
    camera_id: Optional[str] = None,
    event_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    current_user: User = Depends(get_current_active_user),
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
    current_user: User = Depends(get_current_active_user),
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
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Background task to process Redis messages and broadcast to WebSocket clients
async def process_redis_messages():
    """Process messages from Redis and broadcast to WebSocket clients."""
    if not redis_client:
        return
    
    pubsub = redis_client.pubsub()
    pubsub.subscribe("surveillance_events", "surveillance_frames", "camera_status", "surveillance_detections")
    
    while True:
        try:
            message = pubsub.get_message(timeout=0.001)
            if message and message["type"] == "message":
                channel = message["channel"]
                data = json.loads(message["data"])
                
                # Broadcast to appropriate clients
                if channel == "surveillance_events":
                    await manager.broadcast(data, data.get("camera_id"))
                elif channel == "surveillance_frames":
                    await manager.broadcast(data, data.get("camera_id"))
                elif channel == "camera_status":
                    await manager.broadcast(data, data.get("camera_id"))
                elif channel == "surveillance_detections" or channel == b"surveillance_detections":
                    # Add type so the frontend recognizes it
                    if 'type' not in data:
                        data['type'] = 'detection'
                    await manager.broadcast(data, data.get("camera_id"))
            
            await asyncio.sleep(0.01)        
        except Exception as e:
            logger.error(f"Error processing Redis message: {e}")
            await asyncio.sleep(1)

# Background task task already started via lifespan context manager

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
