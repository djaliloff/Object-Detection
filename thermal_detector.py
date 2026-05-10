import cv2
import numpy as np
import onnxruntime as ort
import argparse
import time
import redis
import json
import base64
import os
import sys

# Fix for ONNX Runtime CUDA DLL loading on Windows
if sys.platform == 'win32':
    cuda_paths = []
    try:
        import onnxruntime
        ort_path = os.path.join(os.path.dirname(onnxruntime.__file__), "capi")
        if os.path.exists(ort_path): cuda_paths.append(ort_path)
    except ImportError: pass
    try:
        import torch
        torch_lib = os.path.join(os.path.dirname(torch.__file__), "lib")
        if os.path.exists(torch_lib): cuda_paths.append(torch_lib)
    except ImportError: pass
    cuda_paths.extend([
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.9\bin",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin",
        r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.8\bin"
    ])
    for cp in cuda_paths:
        if os.path.exists(cp):
            if hasattr(os, 'add_dll_directory'):
                try: os.add_dll_directory(cp)
                except Exception: pass
            if cp not in os.environ['PATH']:
                os.environ['PATH'] = cp + os.pathsep + os.environ['PATH']

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

def detect_video(video_path, model_path, camera_id, conf_thres=0.5, iou_thres=0.45):
    print(f"Loading model: {model_path}")
    
    # Initialize Redis client
    try:
        redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            decode_responses=False
        )
        redis_client.ping()
        print("Connected to Redis")
    except Exception as e:
        print(f"Failed to connect to Redis: {e}")
        return

    # Initialize ONNX session with GPU support
    providers = ['CUDAExecutionProvider', 'CPUExecutionProvider'] if 'CUDAExecutionProvider' in ort.get_available_providers() else ['CPUExecutionProvider']
    session = ort.InferenceSession(model_path, providers=providers)
    input_name = session.get_inputs()[0].name
    input_shape = session.get_inputs()[0].shape
    
    # Typically YOLOv8 inputs are [1, 3, 640, 640]
    input_h, input_w = input_shape[2], input_shape[3]
    if isinstance(input_h, str):
        input_h, input_w = 640, 640
        
    print(f"Model Input Shape: {input_shape}")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error opening video file: {video_path}")
        return

    # To calculate FPS
    prev_time = time.time()

    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            # Loop the video
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = cap.read()
            if not ret or frame is None:
                # If setting frame to 0 fails, re-open the file
                cap.release()
                cap = cv2.VideoCapture(video_path)
                ret, frame = cap.read()
                if not ret or frame is None:
                    print("End of video or error reading frame.")
                    break
        
        # Preprocess
        original_h, original_w = frame.shape[:2]
        
        # Resize to expected input size
        img = cv2.resize(frame, (input_w, input_h))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # Normalize and transpose to CHW
        img = img.astype(np.float32) / 255.0
        img = np.transpose(img, (2, 0, 1))
        img = np.expand_dims(img, axis=0)
        
        # Inference
        outputs = session.run(None, {input_name: img})
        
        # Postprocess
        # YOLOv8 output shape is usually (1, num_classes + 4, num_anchors)
        # Transpose to (1, num_anchors, num_classes + 4)
        predictions = np.squeeze(np.asarray(outputs[0], dtype=np.float32)).T
        
        # The first 4 columns are bbox (cx, cy, w, h), the rest are class scores
        boxes = predictions[:, :4]
        scores = np.max(predictions[:, 4:], axis=1)
        class_ids = np.argmax(predictions[:, 4:], axis=1)
        
        # Filter by confidence
        mask = scores > conf_thres
        boxes = boxes[mask]
        scores = scores[mask]
        class_ids = class_ids[mask]
        
        if len(boxes) > 0:
            # Rescale boxes to original image dimensions
            boxes[:, 0] *= (original_w / input_w) # cx
            boxes[:, 2] *= (original_w / input_w) # w
            boxes[:, 1] *= (original_h / input_h) # cy
            boxes[:, 3] *= (original_h / input_h) # h
            
            boxes_xyxy = xywh2xyxy(boxes)
            
            # NMS
            indices = nms(boxes_xyxy, scores, iou_thres)
            
            # Draw boxes
            for i in indices:
                x1, y1, x2, y2 = map(int, boxes_xyxy[i])
                score = scores[i]
                class_id = class_ids[i]
                
                # Assuming the main class is 'Person' (e.g. class 0)
                # You can change the label if your model has multiple classes
                label = f"Person: {score:.2f}" 
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2) # Red bounding box
                cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                
        # Calculate and display FPS
        curr_time = time.time()
        elapsed = curr_time - prev_time
        fps = 1.0 / elapsed if elapsed > 0 else 25.0
        prev_time = curr_time
        cv2.putText(frame, f"FPS: {fps:.1f}", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        # --- Optimize and Publish for Frontend ---
        h, w = frame.shape[:2]
        display_frame = frame
        if w > 960:
            scale = 960 / w
            display_frame = cv2.resize(frame, (960, int(h * scale)), interpolation=cv2.INTER_LINEAR)

        # Encode as raw JPEG
        _, buffer = cv2.imencode('.jpg', display_frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        frame_bytes = buffer.tobytes()
        
        # High-performance publish path (matches gateway.py)
        try:
            pipe = redis_client.pipeline()
            pipe.set(f'latest_frame_jpg:{camera_id}', frame_bytes, ex=5)
            pipe.publish(f'display_frame:{camera_id}', frame_bytes)
            pipe.execute()
        except Exception as e:
            print(f"Redis publish failed: {e}")
        
        # Sleep to maintain ~20-25 FPS
        time.sleep(max(0.005, (1.0 / 25.0) - (time.time() - curr_time)))
            
    cap.release()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Thermal Person Detection using YOLOv8 ONNX")
    parser.add_argument("--video", type=str, required=True, help="Path to input thermal video")
    parser.add_argument("--model", type=str, default=r"Models\yolov8s_thermal.onnx", help="Path to ONNX model")
    parser.add_argument("--camera_id", type=str, required=True, help="Camera ID to publish frames to")
    parser.add_argument("--conf", type=float, default=0.5, help="Confidence threshold")
    parser.add_argument("--iou", type=float, default=0.45, help="NMS IOU threshold")
    args = parser.parse_args()
    
    detect_video(args.video, args.model, args.camera_id, args.conf, args.iou)
