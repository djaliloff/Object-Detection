from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import redis
import os
import json
import asyncio

app = FastAPI(title="Surveillance Backend API")

# Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
r = redis.from_url(REDIS_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"status": "online", "message": "Unified Surveillance Multi-Modal API"}

@app.get("/api/v1/health")
async def health():
    return {"status": "healthy"}

@app.get("/api/v1/events")
async def get_recent_events():
    # Fetch last 50 events from Redis stream
    events = r.xrevrange("system:events", count=50)
    return [json.loads(e[1][b'data']) for e in events]

@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    await websocket.accept()
    print("WebSocket client connected")
    
    # Simple tail-follow on the events stream
    last_id = '$' # Start from now
    try:
        while True:
            # Block for events
            streams = r.xread({"system:events": last_id}, count=1, block=5000)
            if streams:
                for stream, messages in streams:
                    for msg_id, payload in messages:
                        event_data = json.loads(payload[b'data'])
                        await websocket.send_json(event_data)
                        last_id = msg_id
            else:
                # Keepalive
                await websocket.send_json({"type": "ping"})
                await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        print("WebSocket client disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")
