import os
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
        """Load a single YOLO model via Ultralytics with ultra-low latency optimizations."""
        model_path = model_config.get('model_path')
        if not os.path.exists(model_path):
            logger.warning(f"Model file not found: {model_path}")
            return
        
        try:
            # Load native YOLO model
            model = YOLO(model_path)
            
            # Determine device
            model_device = model_config.get('device', self.device)
            
            # Apply ultra-low latency optimizations
            optimize_for_latency = model_config.get('optimize_for_latency', True)
            
            if model_device == 'cuda' and torch.cuda.is_available():
                model.to('cuda')
                
                if optimize_for_latency:
                    # Ultra-low latency GPU optimizations
                    model.fuse()  # Fuse Conv2d + BatchNorm + SiLU
                    
                    # Enable TensorFloat-32 for RTX 3070 performance
                    torch.backends.cuda.matmul.allow_tf32 = True
                    torch.backends.cudnn.allow_tf32 = True
                    
                    # Optimize cuDNN for speed
                    torch.backends.cudnn.benchmark = True
                    torch.backends.cudnn.deterministic = False
                    
                    logger.info(f"Applied ultra-low latency optimizations for {model_name}")
                
                logger.info(f"Model {model_name} loaded on GPU with optimizations")
            else:
                logger.info(f"Model {model_name} loaded on {model_device}")
            
            self.models[model_name] = {
                'model': model,
                'config': model_config,
                'device': model_device,
                'optimize_for_latency': optimize_for_latency
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
            
        # Map 'video' modality to standard RGB model
        if modality == 'video':
            return routing_config.get('default_rgb_model', 'rgb_yolov8n_ultra_low_latency')
        
        # Check for GPU-specific routing if GPU is available
        if torch.cuda.is_available():
            gpu_routing = routing_config.get('gpu_routing', {})
            if self.device == 'cuda':
                for gpu_model_name in gpu_routing.values():
                    if gpu_model_name in self.models:
                        return gpu_model_name
        
        # Fall back to default routing
        return routing_config.get('default_rgb_model', 'rgb_yolov8n_ultra_low_latency')
    
    def run_inference_with_tracking(self, frame_data: FrameData, persist: bool = True) -> Tuple[List[Detection], Any]:
        """
        Run inference with integrated multi-object tracking (BoT-SORT/ByteTrack).
        
        Uses Ultralytics model.track() which integrates detection + tracking in one pass.
        BoT-SORT provides StrongSORT-class tracking with:
        - Re-ID appearance features for occlusion recovery
        - Kalman filter for motion prediction
        - Camera motion compensation (CMC)
        
        Args:
            frame_data: Input frame data
            persist: Whether to persist tracks between frames (always True for MOT)
            
        Returns:
            Tuple of (detections_with_track_ids, raw_results)
        """
        model_name = self.get_model_for_modality(frame_data.modality, frame_data.camera_id)
        
        if not model_name or model_name not in self.models:
            logger.warning(f"No model available for modality {frame_data.modality}")
            return [], None
        
        model_info = self.models[model_name]
        model = model_info['model']
        model_config = model_info['config']
        model_device = model_info['device']
        optimize_for_latency = model_info.get('optimize_for_latency', True)
        
        try:
            # Get postprocessing config
            postprocessing = model_config.get('postprocessing', {})
            conf_thresh = postprocessing.get('confidence_threshold', 0.25)
            iou_thresh = postprocessing.get('nms_threshold', 0.45)
            
            image = frame_data.image_data
            orig_h, orig_w = image.shape[:2]
            
            # GPU synchronization for accurate timing
            if model_device == 'cuda' and torch.cuda.is_available():
                torch.cuda.synchronize()
            
            start_time = time.perf_counter()
            
            # ═══════════════════════════════════════════════════════════
            # KEY: Use model.track() instead of model() for MOT
            # This runs detection + BoT-SORT/ByteTrack tracking in one pass
            # ═══════════════════════════════════════════════════════════
            # Debug: Log tracker config path once in a while
            if getattr(self, '_log_tracker_path', True):
                logger.error(f"DEBUG: Using tracker config: {self.tracker_config_path}")
                self._log_tracker_path = False

            results = model.track(
                image,
                conf=conf_thresh,
                iou=iou_thresh,
                verbose=False,
                device=model_device,
                persist=persist,           # Persist tracks across frames
                tracker=self.tracker_config_path,  # BoT-SORT or ByteTrack config
                imgsz=480,
                augment=False,
                agnostic_nms=False,
            )
            
            if model_device == 'cuda' and torch.cuda.is_available():
                torch.cuda.synchronize()
            
            inference_time = time.perf_counter() - start_time
            
            # Extract detections with track IDs
            detections = []
            
            for r in results:
                if hasattr(r, 'boxes') and r.boxes is not None:
                    boxes = r.boxes.xyxy.cpu().numpy()        # [N, 4]
                    confidences = r.boxes.conf.cpu().numpy()   # [N]
                    classes = r.boxes.cls.cpu().numpy().astype(int)  # [N]
                    
                    # Extract track IDs (key difference from plain detection)
                    track_ids = None
                    if r.boxes.id is not None:
                        track_ids = r.boxes.id.cpu().numpy().astype(int)
                    
                    for i in range(len(boxes)):
                        x1, y1, x2, y2 = boxes[i]
                        confidence = float(confidences[i])
                        class_id = classes[i]
                        
                        # Normalize bounding box coordinates
                        x1_norm = max(0.0, min(x1, orig_w - 1)) / orig_w
                        y1_norm = max(0.0, min(y1, orig_h - 1)) / orig_h
                        x2_norm = max(0.0, min(x2, orig_w - 1)) / orig_w
                        y2_norm = max(0.0, min(y2, orig_h - 1)) / orig_h
                        
                        class_name = model.names[class_id]
                        
                        # Get track ID from tracker
                        track_id = int(track_ids[i]) if track_ids is not None else None
                        
                        detection = Detection(
                            class_name=class_name,
                            confidence=confidence,
                            bbox=[x1_norm, y1_norm, x2_norm, y2_norm],
                            track_id=track_id
                        )
                        detections.append(detection)
            
            # Enhanced logging
            tracked_count = sum(1 for d in detections if d.track_id is not None)
            device_info = f" ({model_device.upper()})" if model_device == 'cuda' else ""
            tracker_info = "BoT-SORT" if "botsort" in self.tracker_type else "ByteTrack"
            logger.debug(
                f"[{tracker_info}]{device_info} {len(detections)} detections, "
                f"{tracked_count} tracked in {inference_time*1000:.1f}ms"
            )
            
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
        """Connect to Redis for frame queue."""
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
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
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
                trajectory_data.append([round(tx, 4), round(ty, 4)])
            
            detection_dict = {
                'class_name': obj.class_name,
                'confidence': round(obj.confidence, 2),
                'bbox': [x1_norm, y1_norm, x2_norm, y2_norm],
                'bbox_pixel': [x1, y1, x2, y2],
                'center': {
                    'x': round(obj.center[0], 4),
                    'y': round(obj.center[1], 4),
                },
                'size': {
                    'width': x2 - x1,
                    'height': y2 - y1
                },
                # ─── MOT fields ───
                'track_id': obj.track_id,
                'track_color': get_track_color(obj.track_id),
                'class_color': get_class_color(obj.class_name),
                'velocity': {
                    'vx': round(obj.velocity[0], 4) if obj.velocity else 0.0,
                    'vy': round(obj.velocity[1], 4) if obj.velocity else 0.0,
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
        
        result = {
            'camera_id': frame_data.camera_id,
            'frame_id': frame_data.frame_id,
            'timestamp': frame_data.timestamp.isoformat(),
            'modality': frame_data.modality,
            'detections': detection_list,
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
            
        logger.info(f"[DEBUG] Processing frame from camera {camera_id} | MOT: {self.tracker_type}")
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
                    await asyncio.sleep(0.01)
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
            start_time = time.time()
            
            # ═══════════════════════════════════════════════════════════
            # Run detection + tracking in one pass (BoT-SORT / ByteTrack)
            # ═══════════════════════════════════════════════════════════
            # Debug: Log frame info periodically
            counter = getattr(self, '_debug_counter', 0)
            if counter % 30 == 0:
                img_mean = np.mean(frame.image_data)
                logger.error(f"DEBUG: Processing frame {frame.frame_id} from {cam_id}, shape: {frame.image_data.shape}, mean: {img_mean:.2f}")
                # Save a sample frame to verify what the AI sees
                debug_path = os.path.join(os.path.dirname(__file__), f"debug_frame_{cam_id}.jpg")
                cv2.imwrite(debug_path, frame.image_data)
                logger.error(f"DEBUG: Saved debug frame to {debug_path}")
            
            self._debug_counter = counter + 1

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
            
            if len(detections) > 0:
                logger.info(
                    f"✅ [MOT] Camera {cam_id}: {len(detections)} detections, "
                    f"{tracked_count} tracked, {inference_time*1000:.1f}ms"
                )
            else:
                # Log even for 0 detections once in a while to confirm activity
                if counter % 30 == 0:
                    logger.error(f"DEBUG: Camera {cam_id}: 0 detections, {inference_time*1000:.1f}ms")
                else:
                    logger.debug(
                        f"[MOT] Camera {cam_id}: 0 detections, "
                        f"{inference_time*1000:.1f}ms"
                    )
            
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
    parser.add_argument('--frame-skip', type=int, default=1,
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
