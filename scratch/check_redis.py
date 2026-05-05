import redis
import os
from dotenv import load_dotenv

load_dotenv()

r = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=False
)

try:
    print(f"Frame queue length: {r.llen('frame_queue')}")
    print(f"Detection queue length: {r.llen('detection_queue')}")
    
    # Check for recent detections
    detections = r.lrange('detection_queue', -1, -1)
    if detections:
        print(f"Latest detection: {detections[0][:100]}...")
    else:
        print("No detections in queue.")
except Exception as e:
    print(f"Error: {e}")
