import os
import sys

# Fix for ONNX Runtime CUDA DLL loading on Windows (MUST BE BEFORE IMPORTING ONNXRUNTIME)
if sys.platform == 'win32':
    cuda_path = r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.9\bin"
    if os.path.exists(cuda_path):
        if hasattr(os, 'add_dll_directory'):
            os.add_dll_directory(cuda_path)
        os.environ['PATH'] = cuda_path + os.pathsep + os.environ['PATH']

import base64
import json
import time
import numpy as np
import cv2
import onnxruntime as ort
import redis
import argparse

def nms(boxes, scores, iou_threshold):
    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]

    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]

    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)

        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])

        w = np.maximum(0.0, xx2 - xx1)
        h = np.maximum(0.0, yy2 - yy1)
        inter = w * h

        ovr = inter / (areas[i] + areas[order[1:]] - inter)

        inds = np.where(ovr <= iou_threshold)[0]
        order = order[inds + 1]

    return keep

def xywh2xyxy(x):
    # Convert nx4 boxes from [cx, cy, w, h] to [x1, y1, x2, y2] 
    y = np.copy(x)
    y[..., 0] = x[..., 0] - x[..., 2] / 2  # top left x
    y[..., 1] = x[..., 1] - x[..., 3] / 2  # top left y
    y[..., 2] = x[..., 0] + x[..., 2] / 2  # bottom right x
    y[..., 3] = x[..., 1] + x[..., 3] / 2  # bottom right y
    return y

def detect_video(video_path, model_path, camera_id, conf_thres=0.5, iou_thres=0.45, show=False):
    print(f"Loading model: {model_path}")
    
    # Initialize Redis client (optional)
    redis_client = None
    try:
        redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            decode_responses=False
        )
        redis_client.ping()
        print("Connected to Redis")
    except:
        print("Redis not available, continuing without publishing.")

    # Initialize ONNX session with GPU support
    providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
    try:
        session = ort.InferenceSession(model_path, providers=providers)
    except Exception as e:
        print(f"GPU not available, using CPU: {e}")
        session = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
        
    input_name = session.get_inputs()[0].name
    input_shape = session.get_inputs()[0].shape
    input_h, input_w = 640, 640
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error opening video file: {video_path}")
        return

    if show:
        cv2.namedWindow("Thermal Detection", cv2.WINDOW_NORMAL)
        # Set window size to match camera aspect ratio
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if width > 0 and height > 0:
            cv2.resizeWindow("Thermal Detection", width, height)

    prev_time = time.time()

    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = cap.read()
            if not ret or frame is None: break
        
        # --- OPTIMIZATION: Initial Resize ---
        # If frame is too large, downscale it immediately to improve processing speed
        original_h, original_w = frame.shape[:2]
        if original_w > 1280:
            scale = 1280 / original_w
            frame = cv2.resize(frame, (1280, int(original_h * scale)))
            original_h, original_w = frame.shape[:2]

        # Preprocess
        img = cv2.resize(frame, (input_w, input_h))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = img.astype(np.float32) / 255.0
        img = np.transpose(img, (2, 0, 1))
        img = np.expand_dims(img, axis=0)
        
        # Inference
        outputs = session.run(None, {input_name: img})
        predictions = np.squeeze(outputs[0]).T
        
        # Postprocess
        boxes = predictions[:, :4]
        scores = np.max(predictions[:, 4:], axis=1)
        
        mask = scores > conf_thres
        boxes = boxes[mask]
        scores = scores[mask]
        
        if len(boxes) > 0:
            boxes[:, 0] *= (original_w / input_w) # cx
            boxes[:, 2] *= (original_w / input_w) # w
            boxes[:, 1] *= (original_h / input_h) # cy
            boxes[:, 3] *= (original_h / input_h) # h
            
            boxes_xyxy = xywh2xyxy(boxes)
            indices = nms(boxes_xyxy, scores, iou_thres)
            
            for i in indices:
                x1, y1, x2, y2 = map(int, boxes_xyxy[i])
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                cv2.putText(frame, f"Person: {scores[i]:.2f}", (x1, y1 - 10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                
        # Calculate FPS
        curr_time = time.time()
        fps = 1 / (curr_time - prev_time)
        prev_time = curr_time
        cv2.putText(frame, f"FPS: {fps:.1f}", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        if show:
            cv2.imshow("Thermal Detection", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'): break

        # Publish to Redis
        if redis_client:
            output_frame = frame
            if original_w > 640:
                scale = 640 / original_w
                output_frame = cv2.resize(frame, (640, int(original_h * scale)))

            _, buffer = cv2.imencode('.jpg', output_frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
            frame_b64 = base64.b64encode(buffer).decode('utf-8')
            msg = {"camera_id": camera_id, "image_data": frame_b64, "type": "surveillance_frames"}
            try:
                redis_client.publish('surveillance_frames', json.dumps(msg))
            except: pass
            
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Thermal Person Detection using YOLOv8 ONNX")
    parser.add_argument("--video", type=str, required=True, help="Path to input thermal video")
    parser.add_argument("--model", type=str, default=r"Models\yolov8s_thermal.onnx", help="Path to ONNX model")
    parser.add_argument("--camera_id", type=str, required=True, help="Camera ID to publish frames to")
    parser.add_argument("--conf", type=float, default=0.5, help="Confidence threshold")
    parser.add_argument("--iou", type=float, default=0.45, help="NMS IOU threshold")
    parser.add_argument("--show", action="store_true", help="Show local window")
    args = parser.parse_args()
    
    detect_video(args.video, args.model, args.camera_id, args.conf, args.iou, args.show)
