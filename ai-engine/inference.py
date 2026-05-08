import os
import sys

# Fix for ONNX Runtime CUDA DLL loading on Windows (MUST BE BEFORE IMPORTING ONNXRUNTIME)
if sys.platform == 'win32':
    cuda_path = r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.9\bin"
    # Also check for torch's bundled cuDNN
    torch_lib = os.path.join(os.path.dirname(__file__), "..", "venv311", "Lib", "site-packages", "torch", "lib")
    
    for path in [torch_lib, cuda_path]:
        if os.path.exists(path):
            if hasattr(os, 'add_dll_directory'):
                os.add_dll_directory(path)
            os.environ['PATH'] = path + os.pathsep + os.environ['PATH']

import base64
import json
import yaml
import time
import numpy as np
import cv2
import onnxruntime
import redis
import structlog
import torch
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
from dotenv import load_dotenv
from ultralytics import YOLO
from collections import defaultdict, deque
import math

# Load environment variables from the root .env file
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

logger = structlog.get_logger()

# ─── Data Classes ────────────────────────────────────────────────────────────

@dataclass
class Detection:
    """Detection result from AI model with tracking information."""
    class_name: str
    confidence: float
    bbox: List[float]           # [x1, y1, x2, y2] normalized
    track_id: Optional[int] = None
    features: Optional[Dict[str, Any]] = None

@dataclass
class TrackedObject:
    """Tracked object with historical trajectory data."""
    track_id: int
    class_name: str
    confidence: float
    bbox: List[float]           # [x1, y1, x2, y2] normalized
    bbox_pixel: List[int]       # [x1, y1, x2, y2] pixel coordinates
    center: Tuple[float, float] # (cx, cy) normalized
    velocity: Optional[Tuple[float, float]] = None  # (vx, vy) pixels/sec
    age: int = 0                # frames since first seen
    hits: int = 0               # total frames detected
    time_since_update: int = 0  # frames since last detection
    trajectory: List[Tuple[float, float]] = field(default_factory=list)  # last N centers

@dataclass
class FrameData:
    """Frame data received from camera gateway."""
    camera_id: str
    frame_id: str
    timestamp: datetime
    modality: str   # rgb, thermal, rgb_t
    image_data: np.ndarray
    metadata: Dict[str, Any]

# ─── Track History Manager ───────────────────────────────────────────────────

class TrackHistoryManager:
    """Manages per-camera track histories for trajectory visualization and event detection."""

    def __init__(self, max_trajectory_length: int = 90, track_timeout_frames: int = 60):
        self.max_trajectory_length = max_trajectory_length
        self.track_timeout_frames = track_timeout_frames
        # camera_id -> { track_id -> TrackedObject }
        self._histories: Dict[str, Dict[int, TrackedObject]] = defaultdict(dict)
        # camera_id -> { track_id -> last_update_frame }
        self._frame_counters: Dict[str, int] = defaultdict(int)
        # camera_id -> { track_id -> deque of (cx, cy) }
        self._trajectories: Dict[str, Dict[int, deque]] = defaultdict(lambda: defaultdict(lambda: deque(maxlen=90)))
        # camera_id -> { track_id -> first_seen_time }
        self._first_seen: Dict[str, Dict[int, float]] = defaultdict(dict)
        # camera_id -> { track_id -> hits_count }
        self._hits: Dict[str, Dict[int, int]] = defaultdict(lambda: defaultdict(int))
        # camera_id -> { track_id -> prev_center }
        self._prev_centers: Dict[str, Dict[int, Tuple[float, float]]] = defaultdict(dict)

    def update(self, camera_id: str, tracked_objects: List[TrackedObject], timestamp: float) -> List[TrackedObject]:
        """Update track histories and compute trajectory/velocity data."""
        self._frame_counters[camera_id] += 1
        frame_num = self._frame_counters[camera_id]
        
        active_track_ids = set()
        enriched = []

        for obj in tracked_objects:
            tid = obj.track_id
            active_track_ids.add(tid)
            
            # Record first seen
            if tid not in self._first_seen[camera_id]:
                self._first_seen[camera_id][tid] = timestamp
            
            # Update hits
            self._hits[camera_id][tid] += 1
            obj.hits = self._hits[camera_id][tid]
            
            # Calculate age
            obj.age = int(timestamp - self._first_seen[camera_id][tid])
            
            # Update trajectory
            cx, cy = obj.center
            self._trajectories[camera_id][tid].append((cx, cy))
            obj.trajectory = list(self._trajectories[camera_id][tid])
            
            # Calculate velocity (normalized units per second)
            prev = self._prev_centers[camera_id].get(tid)
            if prev is not None:
                dt = 1.0 / 15.0  # Approximate frame interval (15fps target)
                vx = (cx - prev[0]) / dt if dt > 0 else 0.0
                vy = (cy - prev[1]) / dt if dt > 0 else 0.0
                obj.velocity = (vx, vy)
            
            self._prev_centers[camera_id][tid] = (cx, cy)
            self._histories[camera_id][tid] = obj
            enriched.append(obj)

        # Clean up stale tracks
        stale_ids = []
        for tid in list(self._histories[camera_id].keys()):
            if tid not in active_track_ids:
                # Track is missing from current frame
                track = self._histories[camera_id][tid]
                track.time_since_update += 1
                if track.time_since_update > self.track_timeout_frames:
                    stale_ids.append(tid)

        for tid in stale_ids:
            self._histories[camera_id].pop(tid, None)
            self._trajectories[camera_id].pop(tid, None)
            self._first_seen[camera_id].pop(tid, None)
            self._hits[camera_id].pop(tid, None)
            self._prev_centers[camera_id].pop(tid, None)

        return enriched

    def get_active_tracks(self, camera_id: str) -> Dict[int, TrackedObject]:
        """Get all active tracks for a camera."""
        return dict(self._histories.get(camera_id, {}))

    def get_track_count(self, camera_id: str) -> int:
        """Get the number of active tracks for a camera."""
        return len(self._histories.get(camera_id, {}))

# ─── Model Registry ─────────────────────────────────────────────────────────

class ModelRegistry:
    """Registry for AI models with tracking-enabled inference."""
    
    def __init__(self, config_path: str = "model_registry.yaml"):
        self.config = self._load_config(config_path)
        self.models = {}
        self.device = self._setup_device()
        self.session_options = self._create_session_options()
        
        # Tracker configuration
        tracker_config = self.config.get('tracking', {})
        self.tracker_type = tracker_config.get('default_tracker', 'botsort')
        self.tracker_config_path = os.path.join(
            os.path.dirname(__file__),
            tracker_config.get('config_file', f'{self.tracker_type}.yaml')
        )
        
        self._load_models()
        self._log_tracker_path = True  # Used for one-time debug logging
    
    def _setup_device(self) -> str:
        """Setup and return the best available device (GPU/CPU)."""
        if torch.cuda.is_available():
            device = 'cuda'
            gpu_name = torch.cuda.get_device_name(0)
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
            logger.info(f"GPU detected: {gpu_name} ({gpu_memory:.1f}GB)")
            logger.info(f"Using GPU acceleration for inference + tracking")
        else:
            device = 'cpu'
            logger.info("No GPU detected, using CPU for inference")
        
        return device
    
    def _load_config(self, config_path: str) -> Dict:
        """Load model configuration from YAML file."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load model config: {e}")
            raise
    
    def _create_session_options(self) -> onnxruntime.SessionOptions:
        """Create ONNX Runtime session options."""
        options = onnxruntime.SessionOptions()
        options.graph_optimization_level = onnxruntime.GraphOptimizationLevel.ORT_ENABLE_ALL
        options.execution_mode = onnxruntime.ExecutionMode.ORT_SEQUENTIAL
        return options
    
    def _load_models(self):
        """Load all models defined in the registry."""
        models_config = self.config.get('models', {})
        
        for model_name, model_config in models_config.items():
            try:
                self._load_single_model(model_name, model_config)
            except Exception as e:
                logger.error(f"Failed to load model {model_name}: {e}")
    
    def _load_single_model(self, model_name: str, model_config: Dict):
        """Load a single model: ONNX via onnxruntime or .pt via Ultralytics YOLO."""
        model_path = model_config.get('model_path')
        if not os.path.exists(model_path):
            logger.warning(f"Model file not found: {model_path}")
            return
        
        try:
            if model_path.endswith('.onnx'):
                # --- Native ONNX Runtime path (thermal model) ---
                providers = (['CUDAExecutionProvider', 'CPUExecutionProvider']
                             if torch.cuda.is_available() else ['CPUExecutionProvider'])
                sess = onnxruntime.InferenceSession(model_path,
                                                    sess_options=self.session_options,
                                                    providers=providers)
                input_name  = sess.get_inputs()[0].name
                input_shape = sess.get_inputs()[0].shape
                ih = input_shape[2] if not isinstance(input_shape[2], str) else 640
                iw = input_shape[3] if not isinstance(input_shape[3], str) else 640

                model_device = 'cuda' if torch.cuda.is_available() else 'cpu'
                classes = model_config.get('classes', ['person'])

                self.models[model_name] = {
                    'model': sess,
                    'model_type': 'onnx',
                    'input_name': input_name,
                    'input_h': ih,
                    'input_w': iw,
                    'classes': classes,
                    'config': model_config,
                    'device': model_device,
                    'optimize_for_latency': True,
                }
                logger.info(f"Successfully loaded ONNX model: {model_name} "
                            f"[{ih}x{iw}] on {model_device}")

            else:
                # --- Ultralytics YOLO path (.pt models) ---
                model = YOLO(model_path)
                model_device = model_config.get('device', self.device)
                optimize_for_latency = model_config.get('optimize_for_latency', True)

                if model_device == 'cuda' and torch.cuda.is_available():
                    model.to('cuda')
                    if optimize_for_latency:
                        model.fuse()
                        torch.backends.cuda.matmul.allow_tf32 = True
                        torch.backends.cudnn.allow_tf32 = True
                        torch.backends.cudnn.benchmark = True
                        torch.backends.cudnn.deterministic = False
                        logger.info(f"Applied ultra-low latency optimizations for {model_name}")
                    logger.info(f"Model {model_name} loaded on GPU with optimizations")
                else:
                    logger.info(f"Model {model_name} loaded on {model_device}")

                self.models[model_name] = {
                    'model': model,
                    'model_type': 'yolo',
                    'config': model_config,
                    'device': model_device,
                    'optimize_for_latency': optimize_for_latency,
                }
                logger.info(f"Successfully loaded model: {model_name}")

        except Exception as e:
            logger.error(f"Failed to load model {model_name} from {model_path}: {e}")
            raise
    
    def get_model_for_modality(self, modality: str, camera_id: str = None) -> str:
        """Determine which model to use based on modality and camera with GPU preference."""
        routing_config = self.config.get('routing', {})
        
        # Check for camera-specific routing first
        camera_models = routing_config.get('camera_models', {})
        if camera_id and camera_id in camera_models:
            return camera_models[camera_id]
            
        if modality == 'thermal':
            return routing_config.get('default_thermal_model', 'thermal_yolov8n')

        if modality == 'rgb_t' or modality == 'fused':
            return routing_config.get('default_fusion_model', 'rgb_t_fusion')

        # GPU-specific routing for RGB models
        if torch.cuda.is_available() and self.device == 'cuda':
            gpu_routing = routing_config.get('gpu_routing', {})
            for gpu_model_name in gpu_routing.values():
                if gpu_model_name in self.models:
                    return gpu_model_name

        return routing_config.get('default_rgb_model', 'rgb_yolov8n_ultra_low_latency')

    def run_inference_with_tracking(self, frame_data: FrameData, persist: bool = True) -> Tuple[List[Detection], Any]:
        """
        Run inference with integrated multi-object tracking.
        ONNX models (thermal) use onnxruntime directly with manual NMS.
        .pt models use Ultralytics model.track() with ByteTrack/BoT-SORT.
        """
        model_name = self.get_model_for_modality(frame_data.modality, frame_data.camera_id)

        if not model_name or model_name not in self.models:
            logger.warning(f"No model available for modality {frame_data.modality}")
            return [], None

        model_info  = self.models[model_name]
        model_type  = model_info.get('model_type', 'yolo')
        model_config = model_info['config']
        postproc    = model_config.get('postprocessing', {})
        conf_thresh = postproc.get('confidence_threshold', 0.25)
        iou_thresh  = postproc.get('nms_threshold', 0.45)

        image   = frame_data.image_data
        orig_h, orig_w = image.shape[:2]

        try:
            # ── ONNX path (thermal model) ────────────────────────────────
            if model_type == 'onnx':
                sess        = model_info['model']
                input_name  = model_info['input_name']
                ih, iw      = model_info['input_h'], model_info['input_w']
                classes     = model_info['classes']

                # Preprocess exactly as in the working standalone script
                img = cv2.resize(image, (iw, ih))
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                img = img.astype(np.float32) / 255.0
                img = np.transpose(img, (2, 0, 1))[np.newaxis]  # [1,3,H,W]

                outputs     = sess.run(None, {input_name: img})
                predictions = np.squeeze(outputs[0]).T  # [N, 4+classes]

                boxes_raw   = predictions[:, :4]                           # cx,cy,w,h
                scores      = np.max(predictions[:, 4:], axis=1)
                class_ids   = np.argmax(predictions[:, 4:], axis=1)

                mask        = scores > conf_thresh
                boxes_raw   = boxes_raw[mask]
                scores      = scores[mask]
                class_ids   = class_ids[mask]

                detections  = []
                if len(boxes_raw) > 0:
                    # Rescale to original image
                    b = boxes_raw.copy()
                    b[:, 0] *= orig_w / iw   # cx
                    b[:, 2] *= orig_w / iw   # w
                    b[:, 1] *= orig_h / ih   # cy
                    b[:, 3] *= orig_h / ih   # h

                    # Convert cx,cy,w,h -> x1,y1,x2,y2
                    boxes_xyxy      = np.copy(b)
                    boxes_xyxy[:, 0] = b[:, 0] - b[:, 2] / 2
                    boxes_xyxy[:, 1] = b[:, 1] - b[:, 3] / 2
                    boxes_xyxy[:, 2] = b[:, 0] + b[:, 2] / 2
                    boxes_xyxy[:, 3] = b[:, 1] + b[:, 3] / 2

                    # NMS (manual, same as standalone script)
                    x1 = boxes_xyxy[:, 0]; y1 = boxes_xyxy[:, 1]
                    x2 = boxes_xyxy[:, 2]; y2 = boxes_xyxy[:, 3]
                    areas = (x2 - x1) * (y2 - y1)
                    order = scores.argsort()[::-1]
                    keep  = []
                    while order.size > 0:
                        i = order[0]; keep.append(i)
                        xx1 = np.maximum(x1[i], x1[order[1:]])
                        yy1 = np.maximum(y1[i], y1[order[1:]])
                        xx2 = np.minimum(x2[i], x2[order[1:]])
                        yy2 = np.minimum(y2[i], y2[order[1:]])
                        inter = np.maximum(0, xx2-xx1) * np.maximum(0, yy2-yy1)
                        ovr   = inter / (areas[i] + areas[order[1:]] - inter)
                        order = order[np.where(ovr <= iou_thresh)[0] + 1]

                    for idx, i in enumerate(keep):
                        x1v, y1v, x2v, y2v = boxes_xyxy[i]
                        cls_name = classes[class_ids[i]] if class_ids[i] < len(classes) else 'person'
                        detections.append(Detection(
                            class_name=cls_name,
                            confidence=float(scores[i]),
                            bbox=[
                                max(0.0, x1v / orig_w), max(0.0, y1v / orig_h),
                                min(1.0, x2v / orig_w), min(1.0, y2v / orig_h),
                            ],
                            track_id=idx + 1,   # simple sequential ID for ONNX
                        ))

                if detections:
                    logger.info(f"🎯 DETECTED (ONNX thermal) on {frame_data.camera_id}: "
                                f"{len(detections)} object(s)")
                return detections, None

            # ── Ultralytics YOLO path (.pt models) ──────────────────────
            model        = model_info['model']
            model_device = model_info['device']

            if model_device == 'cuda' and torch.cuda.is_available():
                torch.cuda.synchronize()

            if getattr(self, '_log_tracker_path', True):
                logger.debug(f"Using tracker config: {self.tracker_config_path}")
                self._log_tracker_path = False

            results = model.track(
                image,
                conf=conf_thresh,
                iou=iou_thresh,
                verbose=False,
                device=model_device,
                persist=persist,
                tracker=self.tracker_config_path,
                imgsz=480,
                augment=False,
                agnostic_nms=False,
            )

            if model_device == 'cuda' and torch.cuda.is_available():
                torch.cuda.synchronize()

            detections = []
            for r in results:
                if hasattr(r, 'boxes') and r.boxes is not None:
                    boxes_r      = r.boxes.xyxy.cpu().numpy()
                    confidences  = r.boxes.conf.cpu().numpy()
                    classes_r    = r.boxes.cls.cpu().numpy().astype(int)
                    track_ids    = (r.boxes.id.cpu().numpy().astype(int)
                                    if r.boxes.id is not None else None)

                    for i in range(len(boxes_r)):
                        x1, y1, x2, y2 = boxes_r[i]
                        detections.append(Detection(
                            class_name=model.names[classes_r[i]],
                            confidence=float(confidences[i]),
                            bbox=[
                                max(0.0, min(x1, orig_w-1)) / orig_w,
                                max(0.0, min(y1, orig_h-1)) / orig_h,
                                max(0.0, min(x2, orig_w-1)) / orig_w,
                                max(0.0, min(y2, orig_h-1)) / orig_h,
                            ],
                            track_id=(int(track_ids[i]) if track_ids is not None else None),
                        ))

            tracked_count = sum(1 for d in detections if d.track_id is not None)
            class_counts  = defaultdict(int)
            for d in detections:
                class_counts[d.class_name] += 1
            summary = ", ".join(f"{v} {k}(s)" for k, v in class_counts.items())
            tracker_info = "BoT-SORT" if "botsort" in self.tracker_type else "ByteTrack"
            device_info  = " (GPU)" if model_device == 'cuda' else ""

            if summary:
                logger.info(f"🎯 DETECTED on {frame_data.camera_id}: {summary}")
            logger.debug(f"[{tracker_info}]{device_info} {len(detections)} detections, "
                         f"{tracked_count} tracked")

            return detections, results

        except Exception as e:
            logger.error(f"Inference+tracking failed for model {model_name}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return [], None
    
    # Backward compatibility: plain inference without tracking
    def run_inference(self, frame_data: FrameData) -> List[Detection]:
        """Run inference without tracking (backward compatible)."""
        detections, _ = self.run_inference_with_tracking(frame_data, persist=False)
        return detections

# ─── Color Palette ───────────────────────────────────────────────────────────

# Distinct colors for track IDs (up to 32 unique, then cycles)
TRACK_COLORS = [
    '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
    '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9',
    '#F0B27A', '#82E0AA', '#F1948A', '#AED6F1', '#D7BDE2',
    '#A3E4D7', '#FAD7A0', '#A9CCE3', '#D5DBDB', '#F9E79F',
    '#ABEBC6', '#F5CBA7', '#D2B4DE', '#AED6F1', '#A9DFBF',
    '#FADBD8', '#D4EFDF', '#FCF3CF', '#D6EAF8', '#FDEDEC',
    '#E8DAEF', '#D5F5E3',
]

def get_track_color(track_id: int) -> str:
    """Get a consistent color for a track ID."""
    if track_id is None:
        return '#FFFFFF'
    return TRACK_COLORS[track_id % len(TRACK_COLORS)]

def get_class_color(class_name: str) -> str:
    """Get consistent color for each class."""
    color_map = {
        'person': '#FF6B6B',
        'car': '#4CAF50',
        'truck': '#FF9800',
        'bicycle': '#2196F3',
        'motorcycle': '#795548',
        'bus': '#9C27B0',
        'dog': '#F44336',
        'cat': '#E91E63',
        'chair': '#9E9E9E',
        'bottle': '#00BCD4',
        'cell phone': '#9C27B0',
        'laptop': '#607D8B',
        'tv': '#795548'
    }
    return color_map.get(class_name, '#FFEB3B')

# ─── Inference Engine ────────────────────────────────────────────────────────

class InferenceEngine:
    """Main inference engine with integrated multi-object tracking (BoT-SORT/StrongSORT)."""
    
    def __init__(self, frame_skip: int = 2, tracker_type: str = 'botsort'):
        """
        Initialize inference engine with multi-object tracking.
        
        Args:
            frame_skip: Number of frames to skip between processing
            tracker_type: 'botsort' (StrongSORT-class with Re-ID) or 'bytetrack' (fast, motion-only)
        """
        self.model_registry = ModelRegistry()
        self.redis_client = self._connect_redis()
        self.running = False
        
        # Multi-Object Tracking
        self.track_history = TrackHistoryManager(
            max_trajectory_length=90,
            track_timeout_frames=60
        )
        self.tracker_type = tracker_type
        self.tracker_config_path = os.path.join(os.path.dirname(__file__), f"{tracker_type}.yaml")
        
        # Sync with model registry
        self.model_registry.tracker_type = tracker_type
        self.model_registry.tracker_config_path = self.tracker_config_path
        logger.info(f"Tracker path: {self.tracker_config_path}")
        
        # Frame skipping
        self.frame_skip = frame_skip
        self.frame_counters = {}
        self.parallel_processing_time = 0
        
        # Performance metrics
        self.stats = {
            'frames_processed': 0,
            'frames_skipped': 0,
            'total_detections': 0,
            'total_tracked_objects': 0,
            'unique_track_ids': set(),
            'avg_inference_time': 0.0,
            'avg_tracking_time': 0.0,
            'start_time': time.time(),
            'gpu_enabled': torch.cuda.is_available(),
            'device': self.model_registry.device,
            'frame_skip': frame_skip,
            'tracker_type': tracker_type,
            'active_tracks_per_camera': {},
        }
        
        # Log initialization
        tracker_label = "BoT-SORT (StrongSORT-class)" if tracker_type == 'botsort' else "ByteTrack"
        if self.stats['gpu_enabled']:
            logger.info(f"🚀 GPU Inference Engine + {tracker_label} MOT initialized on {torch.cuda.get_device_name(0)}")
        else:
            logger.info(f"🖥️ CPU Inference Engine + {tracker_label} MOT initialized")
        
        logger.info(f"Frame skip: {frame_skip} | Tracker: {tracker_label}")
    
    def _connect_redis(self) -> redis.Redis:
        """Connect to Redis for frame queue with retry logic."""
        while True:
            try:
                client = redis.Redis(
                    host=os.getenv("REDIS_HOST", "localhost"),
                    port=int(os.getenv("REDIS_PORT", 6379)),
                    decode_responses=False
                )
                client.ping()
                logger.info("Connected to Redis")
                return client
            except Exception as e:
                logger.error(f"Failed to connect to Redis (retrying in 5s): {e}")
                time.sleep(5)
    
    def _deserialize_frame(self, frame_data: bytes) -> FrameData:
        """Deserialize frame data from Redis."""
        try:
            data = json.loads(frame_data.decode('utf-8'))
            
            import base64
            image_bytes = base64.b64decode(data['image_data'])
            image_array = np.frombuffer(image_bytes, dtype=np.uint8)
            image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
            
            return FrameData(
                camera_id=data['camera_id'],
                frame_id=data['frame_id'],
                timestamp=datetime.fromisoformat(data['timestamp']),
                modality=data['modality'],
                image_data=image,
                metadata=data.get('metadata', {})
            )
        except Exception as e:
            logger.error(f"Failed to deserialize frame: {e}")
            raise
    
    def _serialize_detections(self, tracked_objects: List[TrackedObject], frame_data: FrameData) -> bytes:
        """Serialize tracked detection results with full MOT metadata."""
        detection_list = []
        
        h, w = frame_data.image_data.shape[:2]
        
        for obj in tracked_objects:
            x1_norm, y1_norm, x2_norm, y2_norm = obj.bbox
            x1 = int(x1_norm * w)
            y1 = int(y1_norm * h)
            x2 = int(x2_norm * w)
            y2 = int(y2_norm * h)
            
            # Trajectory as list of [x, y] normalized coordinates
            trajectory_data = []
            for tx, ty in obj.trajectory[-30:]:  # Last 30 points for frontend rendering
                trajectory_data.append([round(float(tx), 4), round(float(ty), 4)])
            
            detection_dict = {
                'class_name': obj.class_name,
                'confidence': round(float(obj.confidence), 2),
                'bbox': [float(obj.bbox[0]), float(obj.bbox[1]), float(obj.bbox[2]), float(obj.bbox[3])],
                'bbox_pixel': [int(x1), int(y1), int(x2), int(y2)],
                'center': {
                    'x': round(float(obj.center[0]), 4),
                    'y': round(float(obj.center[1]), 4),
                },
                'size': {
                    'width': int(x2 - x1),
                    'height': int(y2 - h)
                },
                # ─── MOT fields ───
                'track_id': int(obj.track_id) if obj.track_id is not None else None,
                'track_color': get_track_color(obj.track_id),
                'class_color': get_class_color(obj.class_name),
                'velocity': {
                    'vx': round(float(obj.velocity[0]), 4) if obj.velocity else 0.0,
                    'vy': round(float(obj.velocity[1]), 4) if obj.velocity else 0.0,
                } if obj.velocity else None,
                'age': obj.age,
                'hits': obj.hits,
                'trajectory': [],
                # ─── Display labels ───
                'label': f"#{obj.track_id} {obj.class_name} {obj.confidence:.0%}" if obj.track_id else f"{obj.class_name} {obj.confidence:.0%}",
                'color': get_track_color(obj.track_id) if obj.track_id else get_class_color(obj.class_name),
                'features': None,  # Reserved for Re-ID features
            }
            detection_list.append(detection_dict)
        
        # Count unique track IDs
        active_track_ids = [d['track_id'] for d in detection_list if d['track_id'] is not None]
        
        # Save a snapshot of the frame for alerts if detections exist
        snapshot_rel_path = None
        if detection_list:
            try:
                # Save snapshot to the backend_api/uploads folder so it can be served statically
                snapshot_dir = os.path.join(os.getcwd(), "..", "backend_api", "uploads", "snapshots")
                os.makedirs(snapshot_dir, exist_ok=True)
                
                snapshot_filename = f"snap_{frame_data.camera_id}_{int(time.time() * 1000)}.jpg"
                snapshot_path = os.path.join(snapshot_dir, snapshot_filename)
                
                # Save JPEG with decent quality
                cv2.imwrite(snapshot_path, frame_data.image_data, [cv2.IMWRITE_JPEG_QUALITY, 80])
                snapshot_rel_path = f"/uploads/snapshots/{snapshot_filename}"
            except Exception as e:
                logger.error(f"Failed to save snapshot: {e}")

        result = {
            'camera_id': frame_data.camera_id,
            'frame_id': frame_data.frame_id,
            'timestamp': frame_data.timestamp.isoformat(),
            'modality': frame_data.modality,
            'detections': detection_list,
            'snapshot_path': snapshot_rel_path,
            'frame_info': {
                'width': w,
                'height': h,
                'total_detections': len(detection_list),
                'total_tracked': len(active_track_ids),
                'unique_tracks': len(set(active_track_ids)),
            },
            'tracking_info': {
                'tracker_type': self.tracker_type,
                'active_tracks': len(active_track_ids),
            },
            'inference_time': time.time(),
        }
        
        logger.info(f"[MOT] {frame_data.camera_id}: {len(detection_list)} objects | {len(active_track_ids)} tracked")
        return json.dumps(result).encode('utf-8')
    
    def _update_stats(self, inference_time: float, detection_count: int, tracked_count: int, camera_id: str):
        """Update performance statistics."""
        self.stats['frames_processed'] += 1
        self.stats['total_detections'] += detection_count
        self.stats['total_tracked_objects'] += tracked_count
        self.stats['active_tracks_per_camera'][camera_id] = tracked_count
        
        # Update average inference time  
        self.stats['frames_processed'] += 1
        self.stats['total_detections'] += detection_count
        self.stats['total_tracked_objects'] += tracked_count
    
    def _should_process_frame(self, camera_id: str) -> bool:
        """Determine if frame should be processed based on frame skipping logic."""
        if camera_id not in self.frame_counters:
            self.frame_counters[camera_id] = 0
        
        self.frame_counters[camera_id] += 1
        
        should_process = self.frame_counters[camera_id] % (self.frame_skip + 1) == 0
        
        if not should_process:
            self.stats['frames_skipped'] += 1
            return False
            
        logger.debug(f"Processing frame from camera {camera_id} | MOT: {self.tracker_type}")
        return True
    
    async def process_frames(self):
        """Main processing loop for frames from Redis queue with MOT tracking."""
        self.running = True
        logger.info("Inference engine started with multi-object tracking (MOT)")
        
        while self.running:
            try:
                # Atomically pull all frames and flush queue
                pipe = self.redis_client.pipeline()
                pipe.lrange('frame_queue', 0, -1)
                pipe.delete('frame_queue')
                queue_content = pipe.execute()[0]
                
                if not queue_content:
                    await asyncio.sleep(0.005)
                    continue
                
                # Keep only the latest frame from each camera
                latest_frames = {}
                for frame_data in queue_content:
                    try:
                        frame = self._deserialize_frame(frame_data)
                        latest_frames[frame.camera_id] = frame
                    except Exception as e:
                        logger.error(f"Error deserializing frame: {e}")
                
                # Process cameras
                if latest_frames:
                    parallel_start = time.time()
                    
                    processing_tasks = []
                    for cam_id, frame in latest_frames.items():
                        if not self._should_process_frame(cam_id):
                            logger.debug(f"Skipped frame from {cam_id}")
                            continue
                        
                        task = asyncio.create_task(self._process_single_camera(cam_id, frame))
                        processing_tasks.append(task)
                    
                    if processing_tasks:
                        await asyncio.gather(*processing_tasks, return_exceptions=True)
                    
                    parallel_time = time.time() - parallel_start
                    self.parallel_processing_time += parallel_time
                    
            except Exception as e:
                import traceback
                logger.error(f"Error processing frame: {e}\n{traceback.format_exc()}")
                await asyncio.sleep(0.1)
    
    async def _process_single_camera(self, cam_id: str, frame: FrameData):
        """Process a single camera frame with MOT tracking."""
        try:
            # Check if detection is enabled for this camera
            detection_enabled = frame.metadata.get('detection_enabled', True)
            if not detection_enabled:
                logger.debug(f"Detection disabled for camera {cam_id}, skipping")
                return
            
            logger.info(f"🔍 Processing frame for camera: {cam_id}")
            start_time = time.time()
            
            # ═══════════════════════════════════════════════════════════
            # Run detection + tracking in one pass (BoT-SORT / ByteTrack)
            # ═══════════════════════════════════════════════════════════
            detections, raw_results = self.model_registry.run_inference_with_tracking(frame, persist=True)
            
            inference_time = time.time() - start_time
            
            # Build TrackedObject list from detections
            orig_h, orig_w = frame.image_data.shape[:2]
            tracked_objects = []
            
            for det in detections:
                x1_n, y1_n, x2_n, y2_n = det.bbox
                cx = (x1_n + x2_n) / 2.0
                cy = (y1_n + y2_n) / 2.0
                
                tracked_obj = TrackedObject(
                    track_id=det.track_id if det.track_id is not None else -1,
                    class_name=det.class_name,
                    confidence=det.confidence,
                    bbox=det.bbox,
                    bbox_pixel=[
                        int(x1_n * orig_w), int(y1_n * orig_h),
                        int(x2_n * orig_w), int(y2_n * orig_h)
                    ],
                    center=(cx, cy),
                )
                tracked_objects.append(tracked_obj)
            
            # Enrich with trajectory/velocity data from TrackHistoryManager
            enriched_objects = self.track_history.update(
                cam_id, tracked_objects, time.time()
            )
            
            # Update stats
            tracked_count = sum(1 for o in enriched_objects if o.track_id >= 0)
            self._update_stats(inference_time, len(detections), tracked_count, cam_id)
            
            # Update unique track ID set
            for o in enriched_objects:
                if o.track_id >= 0:
                    self.stats['unique_track_ids'].add(o.track_id)
            
            # Serialize and publish results with full tracking data
            detection_data = self._serialize_detections(enriched_objects, frame)
            
            # Send to detection queue for event processor
            self.redis_client.rpush('detection_queue', detection_data)
            
            # Also publish to WebSocket clients
            self.redis_client.publish('surveillance_detections', detection_data)
            
            # ── Annotate frame and stream to frontend (like standalone script) ──
            # Optimized: resize before encode to minimize WebSocket payload.
            try:
                annotated = frame.image_data.copy()
                for o in enriched_objects:
                    x1_n, y1_n, x2_n, y2_n = o.bbox
                    x1 = int(x1_n * orig_w); y1 = int(y1_n * orig_h)
                    x2 = int(x2_n * orig_w); y2 = int(y2_n * orig_h)
                    color = (0, 200, 255)
                    label = f"{o.class_name} {o.confidence:.0%}"
                    if o.track_id and o.track_id > 0:
                        label += f" #{o.track_id}"
                    cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(annotated, label, (x1, max(y1 - 8, 14)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

                # Downscale to max 480px wide → smaller payload, faster transport
                max_w = 480
                if orig_w > max_w:
                    scale = max_w / orig_w
                    new_w = max_w
                    new_h = int(orig_h * scale)
                    annotated = cv2.resize(annotated, (new_w, new_h),
                                           interpolation=cv2.INTER_LINEAR)

                _, buf = cv2.imencode('.jpg', annotated,
                                      [cv2.IMWRITE_JPEG_QUALITY, 60])
                img_b64 = base64.b64encode(buf.tobytes()).decode('utf-8')
                frame_msg = json.dumps({
                    'type': 'surveillance_frames',
                    'camera_id': cam_id,
                    'image_data': img_b64,
                    'timestamp': frame.timestamp.isoformat(),
                })
                self.redis_client.publish('surveillance_frames', frame_msg)
            except Exception as ann_e:
                logger.warning(f"Frame annotation failed for {cam_id}: {ann_e}")

            if len(detections) > 0:
                logger.info(
                    f"✅ [MOT] Camera {cam_id}: {len(detections)} detections, "
                    f"{tracked_count} tracked, {inference_time*1000:.1f}ms"
                )
            else:
                logger.debug(f"[MOT] Camera {cam_id}: 0 detections, {inference_time*1000:.1f}ms")
            
        except Exception as e:
            import traceback
            logger.error(f"Error processing camera {cam_id}: {e}\n{traceback.format_exc()}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current performance statistics."""
        uptime = time.time() - self.stats['start_time']
        fps = self.stats['frames_processed'] / uptime if uptime > 0 else 0
        
        stats = {
            'frames_processed': self.stats['frames_processed'],
            'frames_skipped': self.stats['frames_skipped'],
            'total_detections': self.stats['total_detections'],
            'total_tracked_objects': self.stats['total_tracked_objects'],
            'unique_track_ids_seen': len(self.stats['unique_track_ids']),
            'avg_inference_time': self.stats['avg_inference_time'],
            'fps': fps,
            'uptime_seconds': uptime,
            'models_loaded': len(self.model_registry.models),
            'gpu_enabled': self.stats['gpu_enabled'],
            'device': self.stats['device'],
            'frame_skip': self.stats['frame_skip'],
            'tracker_type': self.stats['tracker_type'],
            'active_tracks_per_camera': self.stats['active_tracks_per_camera'],
            'skip_ratio': self.stats['frames_skipped'] / (self.stats['frames_processed'] + self.stats['frames_skipped']) if (self.stats['frames_processed'] + self.stats['frames_skipped']) > 0 else 0,
            'parallel_processing_efficiency': self.parallel_processing_time / uptime if uptime > 0 else 0,
        }
        
        # GPU-specific stats
        if self.stats['gpu_enabled']:
            stats['gpu_memory_gb'] = torch.cuda.memory_allocated() / 1024**3
            stats['gpu_memory_total_gb'] = torch.cuda.get_device_properties(0).total_memory / 1024**3
            stats['gpu_utilization_percent'] = (stats['gpu_memory_gb'] / stats['gpu_memory_total_gb']) * 100
        
        return stats
    
    async def start(self):
        """Start the inference engine."""
        await self.process_frames()
    
    def stop(self):
        """Stop the inference engine."""
        self.running = False
        logger.info("Inference engine stopped")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="AI Inference Engine with Multi-Object Tracking")
    parser.add_argument('--frame-skip', type=int, default=0,
                        help='Number of frames to skip between processing (0=no skip, 1=skip 1, etc)')
    parser.add_argument('--tracker', type=str, default='bytetrack', choices=['botsort', 'bytetrack'],
                        help='Tracker type: botsort (StrongSORT-class with Re-ID) or bytetrack (fast, motion-only)')
    
    args = parser.parse_args()
    
    engine = InferenceEngine(frame_skip=args.frame_skip, tracker_type=args.tracker)
    
    try:
        tracker_label = "BoT-SORT (StrongSORT-class)" if args.tracker == 'botsort' else "ByteTrack"
        logger.info(f"Starting AI engine | Tracker: {tracker_label} | Frame skip: {args.frame_skip}")
        asyncio.run(engine.start())
    except KeyboardInterrupt:
        engine.stop()
        logger.info("Inference engine stopped by user")
    except Exception as e:
        import traceback
        logger.error(f"FATAL: AI Engine crashed at startup: {e}\n{traceback.format_exc()}")
        engine.stop()
        sys.exit(1)
