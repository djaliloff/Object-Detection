import redis
import json
import base64
import numpy as np
import cv2
from datetime import datetime

r = redis.Redis(host='localhost', port=6379)

# Create a dummy frame
frame = np.zeros((480, 640, 3), dtype=np.uint8)
cv2.putText(frame, "TEST FRAME", (100, 200), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 0), 3)

_, buffer = cv2.imencode('.jpg', frame)
frame_b64 = base64.b64encode(buffer).decode('utf-8')

camera_id = "61430ba2-4db0-46e0-8878-2f119ef17aca"

data = {
    'camera_id': camera_id,
    'frame_id': f"{camera_id}_test",
    'timestamp': datetime.now().isoformat(),
    'modality': 'rgb',
    'resolution': [480, 640],
    'frame_number': 1,
    'metadata': {},
    'image_data': frame_b64
}

r.rpush('frame_queue', json.dumps(data).encode('utf-8'))
print(f"Pushed test frame for camera {camera_id}")
