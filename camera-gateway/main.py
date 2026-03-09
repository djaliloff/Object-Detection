import cv2
import redis
import os
import json
import time
import base64
import numpy as np

# Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
CAMERA_ID = os.getenv("CAMERA_ID", "cam_01")
CAMERA_URL = os.getenv("CAMERA_URL", "0") # 0 for default webcam or RTSP URL
FPS_LIMIT = int(os.getenv("FPS_LIMIT", "5")) # Limit capture to 5 FPS to save resources

def connect_redis():
    while True:
        try:
            r = redis.from_url(REDIS_URL)
            r.ping()
            print(f"Connected to Redis at {REDIS_URL}")
            return r
        except Exception as e:
            print(f"Waiting for Redis... {e}")
            time.sleep(2)

def main():
    r = connect_redis()
    
    # Initialize Camera
    # Using '0' for local machine testing or a dummy video if URL is not provided
    print(f"Opening camera: {CAMERA_URL}")
    cap = cv2.VideoCapture(CAMERA_URL if CAMERA_URL != "0" else 0)
    
    if not cap.isOpened():
        print("Warning: Could not open video source. Using test pattern.")
        using_test_pattern = True
    else:
        using_test_pattern = False

    last_frame_time = 0

    try:
        while True:
            now = time.time()
            if now - last_frame_time < (1.0 / FPS_LIMIT):
                time.sleep(0.01)
                continue

            if using_test_pattern:
                # Generate a dummy frame with a timestamp
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(frame, f"TEST PATTERN {time.strftime('%H:%M:%S')}", 
                            (100, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            else:
                ret, frame = cap.read()
                if not ret:
                    print("Error: Could not read frame. Reconnecting...")
                    cap.release()
                    time.sleep(2)
                    cap = cv2.VideoCapture(CAMERA_URL if CAMERA_URL != "0" else 0)
                    continue

            # Encode frame to JPEG
            _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            jpg_as_text = base64.b64encode(buffer).decode('utf-8')

            # Prepare message
            message = {
                "camera_id": CAMERA_ID,
                "timestamp": now,
                "frame": jpg_as_text
            }

            # Push to Redis Stream (use XADD for low latency stream processing)
            r.xadd("camera:frames", {"data": json.dumps(message)}, maxlen=100, approximate=True)
            
            last_frame_time = now
            # print(f"Pushed frame from {CAMERA_ID} at {last_frame_time}")

    except KeyboardInterrupt:
        print("Stopping Gateway...")
    finally:
        if not using_test_pattern:
            cap.release()

if __name__ == "__main__":
    main()
