import os
import json
import time
import base64
import cv2
import numpy as np
import redis
from ultralytics import YOLO

# Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
MODEL_PATH = os.getenv("MODEL_PATH", "yolov8n.pt") # Default to Nano for speed
AI_BACKEND = os.getenv("AI_BACKEND", "onnxruntime-cpu")

def connect_redis():
    while True:
        try:
            r = redis.from_url(REDIS_URL)
            r.ping()
            print(f"AI Engine connected to Redis at {REDIS_URL}")
            return r
        except Exception as e:
            print(f"AI Engine waiting for Redis... {e}")
            time.sleep(2)

def main():
    r = connect_redis()
    
    # Load Model (YOLOv8 automatically downloads it if not found)
    print(f"Loading model: {MODEL_PATH}...")
    model = YOLO(MODEL_PATH)
    print("Model loaded successfully.")

    # Redis Stream setup
    stream_name = "camera:frames"
    group_name = "ai_engine_group"
    consumer_name = "consumer_01"

    # Create consumer group if it doesn't exist
    try:
        r.xgroup_create(stream_name, group_name, id='0', mkstream=True)
    except redis.exceptions.ResponseError:
        pass # Group already exists

    print("Starting inference loop...")
    while True:
        try:
            # Read messages from the stream
            # Block for 1000ms, get 1 message
            messages = r.xreadgroup(group_name, consumer_name, {stream_name: ">"}, count=1, block=1000)
            
            if not messages:
                continue

            for stream, msgs in messages:
                for msg_id, payload in msgs:
                    data = json.loads(payload[b'data'])
                    
                    # Decode frame
                    fps_start = time.time()
                    jpg_original = base64.b64decode(data['frame'])
                    jpg_as_np = np.frombuffer(jpg_original, dtype=np.uint8)
                    frame = cv2.imdecode(jpg_as_np, flags=cv2.IMREAD_COLOR)

                    # Run Inference
                    results = model(frame, verbose=False)[0]
                    
                    detections = []
                    for box in results.boxes:
                        # Extract data: [x1, y1, x2, y2], confidence, class_id
                        b = box.xyxy[0].tolist() 
                        conf = float(box.conf[0])
                        cls = int(box.cls[0])
                        name = results.names[cls]
                        
                        detections.append({
                            "bbox": b,
                            "conf": conf,
                            "class": name,
                            "class_id": cls
                        })

                    # Prepare result
                    result_message = {
                        "camera_id": data['camera_id'],
                        "timestamp": data['timestamp'],
                        "inference_time_ms": (time.time() - fps_start) * 1000,
                        "detections": detections
                    }

                    # Push detections to results stream
                    r.xadd("camera:detections", {"data": json.dumps(result_message)}, maxlen=100, approximate=True)
                    
                    # Acknowledge message
                    r.xack(stream_name, group_name, msg_id)
                    
                    # print(f"Processed frame for {data['camera_id']}: found {len(detections)} objects")

        except Exception as e:
            print(f"Error in inference loop: {e}")
            time.sleep(1)

if __name__ == "__main__":
    main()
