import redis
import json
import os
import time

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=False
)

def check_detections():
    pubsub = redis_client.pubsub()
    pubsub.subscribe("surveillance_detections")
    
    print("Listening for detections on Redis 'surveillance_detections' channel...")
    start_time = time.time()
    
    while time.time() - start_time < 15:
        message = pubsub.get_message(timeout=1.0)
        if message and message["type"] == "message":
            data = json.loads(message["data"])
            detections = data.get("detections", [])
            print(f"[{data.get('camera_id')}] Detected {len(detections)} objects. Detections: {detections}")
            if len(detections) > 0:
                print("Successful detection captured!")
                return
    
    print("No detections received within 15 seconds.")

if __name__ == "__main__":
    check_detections()
