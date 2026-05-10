from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os
from datetime import datetime, timedelta
import structlog

logger = structlog.get_logger()

# Simple in-memory user store for demo
DEMO_USERS = {
    "admin": {
        "username": "admin",
        "password": "changeme",  # In production, this would be hashed
        "role": "admin"
    }
}

app = FastAPI(
    title="Multi-Modal Video Surveillance API",
    description="AI-powered video surveillance platform with RGB/thermal fusion",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:80"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class LoginRequest(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

class User(BaseModel):
    username: str
    role: str

# Health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy", 
        "timestamp": datetime.utcnow(),
        "database": "disconnected",
        "redis": "disconnected"
    }

# Simple authentication endpoint
@app.post("/api/v1/auth/login", response_model=Token)
async def login(login_data: LoginRequest):
    user = DEMO_USERS.get(login_data.username)
    
    if not user or user["password"] != login_data.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Generate a simple token (in production, use JWT)
    access_token = f"demo_token_{user['username']}_{datetime.utcnow().timestamp()}"
    
    logger.info(f"User {user['username']} logged in successfully")
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": 8 * 60 * 60  # 8 hours
    }

# Get current user
@app.get("/api/v1/users/me", response_model=User)
async def get_current_user():
    # For demo, return admin user
    return User(username="admin", role="admin")

# Mock cameras endpoint
@app.get("/api/v1/cameras")
async def get_cameras():
    return [
        {
            "id": "cam_001",
            "name": "Front Door",
            "ip": "192.168.1.100",
            "port": 554,
            "rtsp_url": "rtsp://192.168.1.100:554/stream",
            "modality": "rgb",
            "status": "online",
            "last_seen": datetime.utcnow().isoformat()
        },
        {
            "id": "cam_002",
            "name": "Thermal Camera",
            "ip": "192.168.1.101",
            "port": 554,
            "rtsp_url": "rtsp://192.168.1.101:554/stream",
            "modality": "thermal",
            "status": "offline",
            "last_seen": None
        }
    ]

# Mock events endpoint
@app.get("/api/v1/events")
async def get_events():
    return [
        {
            "id": "event_001",
            "event_type": "intrusion",
            "camera_id": "cam_001",
            "camera_name": "Front Door",
            "severity": "medium",
            "start_time": datetime.utcnow().isoformat(),
            "status": "new",
            "event_data": {
                "object_class": "person",
                "confidence": 0.85
            }
        }
    ]

# Mock analytics endpoint
@app.get("/api/v1/analytics/summary")
async def get_analytics_summary():
    return {
        "total_cameras": 2,
        "online_cameras": 1,
        "total_detections": 156,
        "total_events": 23,
        "new_events": 3,
        "avg_fps": 15.2,
        "uptime_percentage": 98.5
    }

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting simple backend API server")
    uvicorn.run(app, host="0.0.0.0", port=8000)
