import os
import json
import time
import asyncio
import threading
import base64
import sys
import urllib.request
import queue
import numpy as np
import cv2
import redis
import structlog
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from datetime import datetime
from abc import ABC, abstractmethod
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables from the root .env file
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

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
    
    if os.getenv("CUDA_PATH"):
        cuda_paths.append(os.path.join(os.getenv("CUDA_PATH"), "bin"))

    for cp in cuda_paths:
        if os.path.exists(cp):
            if hasattr(os, 'add_dll_directory'):
                try:
                    os.add_dll_directory(cp)
                except Exception: pass
            if cp not in os.environ['PATH']:
                os.environ['PATH'] = cp + os.pathsep + os.environ['PATH']

logger = structlog.get_logger()

# ─────────────────────────────────────────────────────────────────────────────
# OPTIMISATION KNOBS  (override via .env)
# ─────────────────────────────────────────────────────────────────────────────
# Display stream caps
DISPLAY_MAX_W       = int(os.getenv("DISPLAY_MAX_W", "800"))      # max display width (px)
DISPLAY_JPEG_Q      = int(os.getenv("DISPLAY_JPEG_Q", "65"))      # display JPEG quality
# AI frame caps
AI_MAX_W            = int(os.getenv("AI_MAX_W", "640"))           # max AI inference width (px)
AI_JPEG_Q           = int(os.getenv("AI_JPEG_Q", "65"))           # AI JPEG quality
# Frame-skip: only every Nth frame goes to the AI queue
AI_FRAME_SKIP       = int(os.getenv("AI_FRAME_SKIP", "3"))        # e.g. 3 → 1 in 3 frames
# Redis AI queue depth cap — discard oldest when full
AI_QUEUE_MAX        = int(os.getenv("AI_QUEUE_MAX", "2"))
# RTSP capture ring-buffer depth
RTSP_QUEUE_SIZE     = int(os.getenv("RTSP_QUEUE_SIZE", "2"))      # keep only latest N frames
# Adaptive back-pressure: if Redis frame_queue depth exceeds this, skip AI push
AI_QUEUE_BACKPRESSURE = int(os.getenv("AI_QUEUE_BACKPRESSURE", "4"))
# MJPEG chunk read size
MJPEG_CHUNK         = int(os.getenv("MJPEG_CHUNK", "16384"))      # bytes
# ONNX intra/inter op threads
ONNX_INTRA         = int(os.getenv("ONNX_INTRA", "2"))
ONNX_INTER         = int(os.getenv("ONNX_INTER", "1"))
# ─────────────────────────────────────────────────────────────────────────────


# --- Utility Functions for Direct Detection ---
def nms(boxes, scores, iou_threshold):
    if len(boxes) == 0:
        return []
    x1 = boxes[:, 0]; y1 = boxes[:, 1]; x2 = boxes[:, 2]; y2 = boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]
    keep = []
    while order.size > 0:
        i = order[0]; keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]]); yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]]); yy2 = np.minimum(y2[i], y2[order[1:]])
        w = np.maximum(0.0, xx2 - xx1); h = np.maximum(0.0, yy2 - yy1)
        inter = w * h
        ovr = inter / (areas[i] + areas[order[1:]] - inter)
        inds = np.where(ovr <= iou_threshold)[0]
        order = order[inds + 1]
    return keep

def xywh2xyxy(x):
    y = np.copy(x)
    y[..., 0] = x[..., 0] - x[..., 2] / 2
    y[..., 1] = x[..., 1] - x[..., 3] / 2
    y[..., 2] = x[..., 0] + x[..., 2] / 2
    y[..., 3] = x[..., 1] + x[..., 3] / 2
    return y

@dataclass
class CameraConfig:
    """Camera configuration."""
    id: str
    name: str
    ip: str
    port: int
    rtsp_url: str
    username: Optional[str] = None
    password: Optional[str] = None
    modality: str = "rgb"
    fps_target: int = 8
    enabled: bool = True
    detection_enabled: bool = True
    mjpeg_url: Optional[str] = None
    hls_url: Optional[str] = None
    stream_url: Optional[str] = None

@dataclass
class FrameMetadata:
    """Metadata for captured frames."""
    camera_id: str
    frame_id: str
    timestamp: datetime
    modality: str
    resolution: tuple
    frame_number: int
    metadata: Dict

class CameraAdapter(ABC):
    """Abstract base class for camera adapters."""
    _conn_attempts: int = 0
    
    @abstractmethod
    async def connect(self) -> bool: pass
    
    @abstractmethod
    async def disconnect(self): pass
    
    @abstractmethod
    async def get_frame(self) -> tuple[Optional[np.ndarray], Optional[FrameMetadata]]: pass
    
    @abstractmethod
    def is_connected(self) -> bool: pass

class RTSPCameraAdapter(CameraAdapter):
    """RTSP camera adapter using OpenCV.
    
    OPTIMISATION: ring-buffer of RTSP_QUEUE_SIZE frames so the capture thread
    never blocks and always returns the freshest frame available.
    """
    
    def __init__(self, config: CameraConfig):
        self.config = config
        self.cap = None
        self.frame_count = 0
        self.last_frame_time = time.time()
        self.connection_attempts = 0
        self.max_connection_attempts = 5
        self.reconnect_delay = 5
        # ── OPTIMISATION: tighter queue so display is always current ──
        self.frame_queue = queue.Queue(maxsize=RTSP_QUEUE_SIZE)
        self.running = False
        self.capture_thread = None
    
    async def connect(self) -> bool:
        if self.running:
            return True
        try:
            rtsp_url = self.config.rtsp_url
            if self.config.username and self.config.password:
                if "://" in rtsp_url:
                    protocol, rest = rtsp_url.split("://", 1)
                    rtsp_url = f"{protocol}://{self.config.username}:{self.config.password}@{rest}"
            
            if rtsp_url.startswith('http'):
                logger.info(f"Opening HTTP/MJPEG stream for camera {self.config.id}: {rtsp_url}")
                self.cap = cv2.VideoCapture(rtsp_url)
                self.cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            else:
                try:
                    pipeline = (
                        f"rtspsrc location={rtsp_url} latency=0 ! "
                        "rtph264depay ! h264parse ! avdec_h264 ! "
                        "videoconvert ! appsink drop=true max-buffers=1"
                    )
                    self.cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
                    if not self.cap.isOpened():
                        self.cap = cv2.VideoCapture(rtsp_url)
                        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                except Exception:
                    self.cap = cv2.VideoCapture(rtsp_url)
                    self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            if not self.cap.isOpened():
                return False
                
            self.running = True
            self.capture_thread = threading.Thread(
                target=self._capture_thread_run, daemon=True, name=f"rtsp-{self.config.id}"
            )
            self.capture_thread.start()
            logger.info(f"[SUCCESS] Started capture thread for camera {self.config.id}")
            return True
        except Exception as e:
            logger.error(f"Error connecting to RTSP camera {self.config.id}: {e}")
            return False

    def _capture_thread_run(self):
        """Dedicated thread: read frames as fast as the camera produces them,
        keep only the most recent RTSP_QUEUE_SIZE frames to avoid memory growth."""
        while self.running:
            if not self.cap or not self.cap.isOpened():
                time.sleep(0.1)
                continue
            ret, frame = self.cap.read()
            if ret and frame is not None:
                # ── OPTIMISATION: drop oldest if full ──
                if self.frame_queue.full():
                    try:
                        self.frame_queue.get_nowait()
                    except queue.Empty:
                        pass
                self.frame_queue.put(frame)
            else:
                time.sleep(0.01)

    async def disconnect(self):
        self.running = False
        if self.capture_thread:
            self.capture_thread.join(timeout=1.0)
        if self.cap:
            self.cap.release()
            self.cap = None
        logger.info(f"Disconnected from RTSP camera {self.config.id}")
    
    async def get_frame(self) -> tuple[Optional[np.ndarray], Optional[FrameMetadata]]:
        if not self.running:
            return None, None
        try:
            try:
                frame = self.frame_queue.get_nowait()
            except queue.Empty:
                return None, None
            self.frame_count += 1
            current_time = time.time()
            metadata = FrameMetadata(
                camera_id=self.config.id,
                frame_id=f"{self.config.id}_{int(current_time * 1000)}_{self.frame_count}",
                timestamp=datetime.now(),
                modality=self.config.modality,
                resolution=frame.shape[:2],
                frame_number=self.frame_count,
                metadata={'connection_attempts': self.connection_attempts}
            )
            return frame, metadata
        except Exception as e:
            logger.error(f"Error getting frame from camera {self.config.id}: {e}")
            return None, None
    
    def is_connected(self) -> bool:
        return self.cap is not None and self.cap.isOpened()


class ThermalCameraAdapter(CameraAdapter):
    """Thermal camera adapter (placeholder)."""
    
    def __init__(self, config: CameraConfig):
        self.config = config

    async def connect(self) -> bool:
        logger.info(f"Thermal camera adapter for {self.config.id} (placeholder implementation)")
        return True
    
    async def disconnect(self):
        logger.info(f"Disconnected from thermal camera {self.config.id}")
    
    async def get_frame(self) -> tuple[Optional[np.ndarray], Optional[FrameMetadata]]:
        await asyncio.sleep(1)
        return None, None
    
    def is_connected(self) -> bool:
        return True


class MJPEGCameraAdapter(CameraAdapter):
    """Robust MJPEG over HTTP camera adapter using urllib.
    
    OPTIMISATION: larger chunk read (MJPEG_CHUNK) reduces sys-call overhead;
    ring-buffer queue discards stale frames immediately.
    """
    
    def __init__(self, config: CameraConfig):
        self.config = config
        self.stream = None
        self.frame_count = 0
        self.last_frame_time = time.time()
        self.frame_queue = queue.Queue(maxsize=RTSP_QUEUE_SIZE)
        self.running = False
        self.capture_thread = None
        
    async def connect(self) -> bool:
        if self.running:
            return True
        try:
            logger.info(f"Connecting to MJPEG stream: {self.config.rtsp_url}")
            self.stream = urllib.request.urlopen(self.config.rtsp_url, timeout=10)
            self.running = True
            self.capture_thread = threading.Thread(
                target=self._capture_thread_run, daemon=True, name=f"mjpeg-{self.config.id}"
            )
            self.capture_thread.start()
            return True
        except Exception as e:
            err_msg = str(e)
            if "10061" in err_msg:
                logger.error(
                    f"Failed to connect to MJPEG stream {self.config.id}: "
                    f"Connection refused. Is the camera app running on {self.config.rtsp_url}?"
                )
            else:
                logger.error(f"Failed to connect to MJPEG stream {self.config.id}: {e}")
            return False
            
    def _capture_thread_run(self):
        bytes_data = b''
        while self.running and self.stream:
            try:
                # ── OPTIMISATION: larger read chunk reduces loop overhead ──
                chunk = self.stream.read(MJPEG_CHUNK)
                if not chunk:
                    break
                bytes_data += chunk
                a = bytes_data.find(b'\xff\xd8')
                b = bytes_data.find(b'\xff\xd9')
                if a != -1 and b != -1:
                    jpg = bytes_data[a:b+2]
                    bytes_data = bytes_data[b+2:]
                    frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                    if frame is not None:
                        if self.frame_queue.full():
                            try:
                                self.frame_queue.get_nowait()
                            except queue.Empty:
                                pass
                        self.frame_queue.put(frame)
                # ── OPTIMISATION: cap bytes_data growth (prevents RAM blowup on corrupt streams)
                if len(bytes_data) > MJPEG_CHUNK * 4:
                    bytes_data = bytes_data[-MJPEG_CHUNK:]
            except Exception as e:
                logger.error(f"MJPEG thread error ({self.config.id}): {e}")
                time.sleep(1)

    async def disconnect(self):
        self.running = False
        if self.capture_thread:
            self.capture_thread.join(timeout=1.0)
        if self.stream:
            self.stream.close()
            self.stream = None
            
    async def get_frame(self) -> tuple[Optional[np.ndarray], Optional[FrameMetadata]]:
        if not self.running:
            return None, None
        try:
            try:
                frame = self.frame_queue.get_nowait()
            except queue.Empty:
                return None, None
            self.frame_count += 1
            current_time = time.time()
            metadata = FrameMetadata(
                camera_id=self.config.id,
                frame_id=f"{self.config.id}_{int(current_time * 1000)}_{self.frame_count}",
                timestamp=datetime.now(),
                modality=self.config.modality,
                resolution=frame.shape[:2],
                frame_number=self.frame_count,
                metadata={'detection_enabled': self.config.detection_enabled}
            )
            return frame, metadata
        except Exception as e:
            logger.error(f"Error getting MJPEG frame {self.config.id}: {e}")
            return None, None
            
    def is_connected(self) -> bool:
        return self.running and self.stream is not None


class VideoFileCameraAdapter(CameraAdapter):
    """Camera adapter for looped video files."""
    
    def __init__(self, config: CameraConfig):
        self.config = config
        self.cap = None
        self.frame_count = 0
        self.last_frame_time = time.time()
        self.source_fps = None
    
    async def connect(self) -> bool:
        try:
            video_path = self.config.rtsp_url
            if not os.path.exists(video_path):
                logger.error(f"Video file not found for camera {self.config.id}: {video_path}")
                return False
            self.cap = cv2.VideoCapture(video_path)
            if not self.cap.isOpened():
                logger.error(f"Failed to open video file for camera {self.config.id}")
                return False
            source_fps = float(self.cap.get(cv2.CAP_PROP_FPS) or 0)
            if 1.0 <= source_fps <= 120.0:
                max_file_fps = float(os.getenv("VIDEO_FILE_MAX_FPS", "60"))
                self.source_fps = min(source_fps, max_file_fps)
                self.config.fps_target = max(1, int(round(self.source_fps)))
            logger.info(
                f"Opened video file for camera {self.config.id} "
                f"(source_fps={source_fps:.2f}, capture_fps={self.config.fps_target})"
            )
            return True
        except Exception as e:
            logger.error(f"Error opening video file {self.config.id}: {e}")
            return False
            
    async def disconnect(self):
        if self.cap:
            self.cap.release()
            self.cap = None
            
    async def get_frame(self) -> tuple[Optional[np.ndarray], Optional[FrameMetadata]]:
        return await asyncio.to_thread(self._get_frame_sync)

    def _get_frame_sync(self) -> tuple[Optional[np.ndarray], Optional[FrameMetadata]]:
        if not self.cap or not self.cap.isOpened():
            return None, None
        try:
            ret, frame = self.cap.read()
            if not ret or frame is None:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self.cap.read()
                if not ret or frame is None:
                    self.cap.release()
                    self.cap = cv2.VideoCapture(self.config.rtsp_url)
                    if self.cap.isOpened():
                        ret, frame = self.cap.read()
                if not ret or frame is None:
                    return None, None
            self.frame_count += 1
            current_time = time.time()
            metadata = FrameMetadata(
                camera_id=self.config.id,
                frame_id=f"{self.config.id}_{int(current_time * 1000)}_{self.frame_count}",
                timestamp=datetime.now(),
                modality=self.config.modality,
                resolution=frame.shape[:2],
                frame_number=self.frame_count,
                metadata={'looping': True}
            )
            return frame, metadata
        except Exception as e:
            logger.error(f"Error reading video frame {self.config.id}: {e}")
            return None, None
            
    def is_connected(self) -> bool:
        return self.cap is not None and self.cap.isOpened()


class ThermalDetectionVideoAdapter(VideoFileCameraAdapter):
    """
    Enhanced video file adapter that performs person detection on thermal video frames
    using YOLOv8 ONNX, burning the boxes directly into the frame.
    
    OPTIMISATIONS:
    - Shared ONNX session (unchanged, already good).
    - Pre-allocated input buffer reused across frames.
    - Reduced ONNX intra/inter threads via env vars.
    - Confidence threshold raised to 0.55 to reduce NMS work.
    """

    _shared_session = None
    _shared_input_info = None

    def __init__(self, config: CameraConfig):
        super().__init__(config)
        self.input_h = 640
        self.input_w = 640
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.model_path = os.path.join(root, "models", "yolov8s_thermal.onnx")
        # ── OPTIMISATION: pre-allocated numpy buffer for preprocessing ──
        self._input_buf: Optional[np.ndarray] = None

    async def connect(self) -> bool:
        success = await super().connect()
        if not success:
            return False
        try:
            import onnxruntime as ort
            if ThermalDetectionVideoAdapter._shared_session is None:
                if not os.path.exists(self.model_path):
                    logger.warning(f"Thermal model not found at {self.model_path}")
                    return True
                providers = (
                    ['CUDAExecutionProvider', 'CPUExecutionProvider']
                    if 'CUDAExecutionProvider' in ort.get_available_providers()
                    else ['CPUExecutionProvider']
                )
                logger.info(f"Initializing shared thermal session with providers: {providers}")
                options = ort.SessionOptions()
                # ── OPTIMISATION: configurable thread counts via env ──
                options.intra_op_num_threads = ONNX_INTRA
                options.inter_op_num_threads = ONNX_INTER
                # ── OPTIMISATION: enable graph optimisations ──
                options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                session = ort.InferenceSession(self.model_path, sess_options=options, providers=providers)
                input_name = session.get_inputs()[0].name
                input_shape = session.get_inputs()[0].shape
                h, w = 640, 640
                if len(input_shape) >= 4:
                    if not isinstance(input_shape[2], str): h = input_shape[2]
                    if not isinstance(input_shape[3], str): w = input_shape[3]
                ThermalDetectionVideoAdapter._shared_session = session
                ThermalDetectionVideoAdapter._shared_input_info = {'name': input_name, 'h': h, 'w': w}
            info = ThermalDetectionVideoAdapter._shared_input_info
            self.input_h = info['h']
            self.input_w = info['w']
            # ── OPTIMISATION: allocate reusable buffer once ──
            self._input_buf = np.empty((1, 3, self.input_h, self.input_w), dtype=np.float32)
            logger.info(f"Thermal adapter for {self.config.id} ready (shared session)")
            return True
        except Exception as e:
            logger.error(f"Failed to setup thermal model for {self.config.id}: {e}")
            return True

    def _get_frame_sync(self) -> tuple[Optional[np.ndarray], Optional[FrameMetadata]]:
        frame, metadata = super()._get_frame_sync()
        session = ThermalDetectionVideoAdapter._shared_session
        if frame is None or session is None:
            return frame, metadata
        try:
            info = ThermalDetectionVideoAdapter._shared_input_info
            original_h, original_w = frame.shape[:2]

            # ── OPTIMISATION: reuse pre-allocated buffer; avoid extra copies ──
            resized = cv2.resize(frame, (info['w'], info['h']))
            rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            # Normalise into pre-allocated buffer in-place
            np.divide(rgb.transpose(2, 0, 1).astype(np.float32), 255.0,
                      out=self._input_buf[0])

            outputs = session.run(None, {info['name']: self._input_buf})
            predictions = np.squeeze(np.asarray(outputs[0], dtype=np.float32)).T

            boxes = predictions[:, :4]
            scores = np.max(predictions[:, 4:], axis=1)
            class_ids = np.argmax(predictions[:, 4:], axis=1)

            # ── OPTIMISATION: slightly higher threshold → fewer boxes → less NMS work ──
            mask = scores > 0.55
            boxes = boxes[mask]; scores = scores[mask]; class_ids = class_ids[mask]

            if len(boxes) > 0:
                boxes[:, 0] *= (original_w / info['w']); boxes[:, 2] *= (original_w / info['w'])
                boxes[:, 1] *= (original_h / info['h']); boxes[:, 3] *= (original_h / info['h'])
                boxes_xyxy = xywh2xyxy(boxes)
                indices = nms(boxes_xyxy, scores, 0.45)

                class_names = ['person', 'car', 'bicycle', 'dog', 'motorcycle']
                detections = []
                for idx, i in enumerate(indices):
                    x1, y1, x2, y2 = map(int, boxes_xyxy[i])
                    score = float(scores[i])
                    class_id = class_ids[i]
                    class_name = (class_names[class_id] if class_id < len(class_names)
                                  else f"class_{class_id}")
                    label = f"{class_name.capitalize()}: {score:.2f}"
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                    cv2.putText(frame, label, (x1, max(y1 - 10, 20)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                    detections.append({
                        'class_name': class_name,
                        'confidence': score,
                        'bbox': [
                            max(0.0, x1 / original_w), max(0.0, y1 / original_h),
                            min(1.0, x2 / original_w), min(1.0, y2 / original_h),
                        ],
                        'track_id': -1000 - idx,
                        'center': {
                            'x': ((x1 + x2) / 2.0) / original_w,
                            'y': ((y1 + y2) / 2.0) / original_h
                        }
                    })
                metadata.metadata['direct_detections'] = detections

            metadata.metadata['detection_enabled'] = False
            metadata.metadata['direct_detection'] = True
            return frame, metadata
        except Exception as e:
            logger.error(f"Error drawing detections ({self.config.id}): {e}")
            return frame, metadata


class CameraManager:
    """Manages multiple camera connections and frame capture.
    
    KEY OPTIMISATIONS vs original:
    1. Display JPEG: capped at DISPLAY_MAX_W px, quality DISPLAY_JPEG_Q.
    2. AI JPEG: capped at AI_MAX_W px, quality AI_JPEG_Q.
    3. Frame-skip counter: only every AI_FRAME_SKIP-th frame is pushed to the
       AI inference queue, drastically cutting serialisation/network overhead.
    4. Back-pressure: if the Redis `frame_queue` depth already exceeds
       AI_QUEUE_BACKPRESSURE we skip pushing more work — AI engine stays
       responsive instead of drowning.
    5. AI queue capped to AI_QUEUE_MAX entries (drop oldest), preventing Redis
       memory growth when AI engine falls behind.
    6. encode_display_frame uses INTER_NEAREST for speed (perceptually fine at
       display sizes).
    """

    def __init__(self):
        self.cameras: Dict[str, CameraAdapter] = {}
        self.camera_configs: Dict[str, CameraConfig] = {}
        self.frame_callbacks: List[Callable] = []
        self.running = False
        self.redis_client = self._connect_redis()
        self.stats = {
            'total_frames': 0,
            'frames_per_camera': {},
            'errors': {},
            'last_frame_time': {}
        }
        stream_fps = float(os.getenv("STREAM_PUBLISH_FPS", "25"))
        self.stream_publish_interval = 1.0 / max(stream_fps, 1.0)
        self._last_stream_publish: Dict[str, float] = {}
        # ── OPTIMISATION: per-camera AI frame counter for frame-skip ──
        self._ai_frame_counter: Dict[str, int] = {}

    def _connect_redis(self) -> redis.Redis:
        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", 6379))
        while True:
            try:
                client = redis.Redis(host=host, port=port, decode_responses=False)
                client.ping()
                logger.info("Connected to Redis")
                return client
            except Exception as e:
                logger.warning(f"Redis not ready, retrying in 3s: {e}")
                time.sleep(3)

    def add_camera(self, config: CameraConfig):
        self.camera_configs[config.id] = config

        if config.rtsp_url and (
            config.modality == "video"
            or os.path.isfile(config.rtsp_url)
            or str(config.rtsp_url).lower().endswith(('.mp4', '.avi', '.mkv', '.mov'))
        ):
            adapter = ThermalDetectionVideoAdapter(config) if config.modality == "thermal" else VideoFileCameraAdapter(config)
        elif config.rtsp_url and config.rtsp_url.startswith('http'):
            adapter = MJPEGCameraAdapter(config)
        elif config.rtsp_url and (config.rtsp_url.startswith('rtsp') or "://" in str(config.rtsp_url)):
            adapter = RTSPCameraAdapter(config)
        elif config.modality == "thermal":
            adapter = ThermalCameraAdapter(config)
        else:
            adapter = RTSPCameraAdapter(config)

        self.cameras[config.id] = adapter
        self.stats['frames_per_camera'][config.id] = 0
        self.stats['errors'][config.id] = 0
        self.stats['last_frame_time'][config.id] = None
        self._ai_frame_counter[config.id] = 0
        logger.info(f"Added camera {config.id} ({config.modality})")

    def remove_camera(self, camera_id: str):
        if camera_id in self.cameras:
            asyncio.create_task(self.cameras[camera_id].disconnect())
            del self.cameras[camera_id]
            del self.camera_configs[camera_id]
            self.stats['frames_per_camera'].pop(camera_id, None)
            self.stats['errors'].pop(camera_id, None)
            self.stats['last_frame_time'].pop(camera_id, None)
            self._ai_frame_counter.pop(camera_id, None)
            logger.info(f"Removed camera {camera_id}")

    async def connect_camera(self, camera_id: str) -> bool:
        if camera_id not in self.cameras:
            logger.error(f"Camera {camera_id} not found")
            return False
        return await self.cameras[camera_id].connect()

    async def disconnect_camera(self, camera_id: str):
        if camera_id in self.cameras:
            await self.cameras[camera_id].disconnect()

    async def connect_all_cameras(self):
        tasks = [self.connect_camera(cid) for cid in self.cameras]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def disconnect_all_cameras(self):
        for camera_id in self.cameras:
            await self.disconnect_camera(camera_id)

    # ─────────────────────────────────────────────────────────────────────────
    # Encoding helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _encode_display_frame(self, frame: np.ndarray, camera_id: str) -> bytes:
        """Encode display JPEG and push to Redis SET + PUBLISH.
        
        OPTIMISATIONS:
        - Max width capped to DISPLAY_MAX_W (env, default 800).
        - JPEG quality DISPLAY_JPEG_Q (env, default 65) — saves ~15-20% bandwidth vs 70.
        - INTER_NEAREST is 3-4× faster than INTER_LINEAR at display sizes; imperceptible.
        """
        try:
            h, w = frame.shape[:2]
            if w > DISPLAY_MAX_W:
                new_w = DISPLAY_MAX_W
                new_h = int(h * new_w / w)
                # ── OPTIMISATION: INTER_NEAREST — display doesn't need bicubic quality ──
                disp_frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_NEAREST)
            else:
                disp_frame = frame

            _, disp_buf = cv2.imencode('.jpg', disp_frame, [cv2.IMWRITE_JPEG_QUALITY, DISPLAY_JPEG_Q])
            disp_bytes = disp_buf.tobytes()

            pipe = self.redis_client.pipeline()
            pipe.set(f'latest_frame_jpg:{camera_id}', disp_bytes, ex=2)
            pipe.publish(f'display_frame:{camera_id}', disp_bytes)
            pipe.execute()
            return disp_bytes
        except Exception as e:
            logger.warning(f"Display encode failed ({camera_id}): {e}")
            return b""

    def _encode_ai_frame_binary(self, frame: np.ndarray, metadata: FrameMetadata) -> bytes:
        """Binary serialisation for the AI queue.
        Format: [header_size(4b)][header_json][raw_jpeg_bytes]
        
        OPTIMISATION: AI_MAX_W (default 640) and AI_JPEG_Q (default 65).
        """
        try:
            import struct
            orig_h, orig_w = frame.shape[:2]
            ai_w = AI_MAX_W
            ai_h = int(orig_h * ai_w / orig_w)
            ai_frame = cv2.resize(frame, (ai_w, ai_h), interpolation=cv2.INTER_LINEAR)
            _, ai_buf = cv2.imencode('.jpg', ai_frame, [cv2.IMWRITE_JPEG_QUALITY, AI_JPEG_Q])
            ai_bytes = ai_buf.tobytes()
            header = {
                'c': metadata.camera_id,
                'f': metadata.frame_id,
                't': metadata.timestamp.isoformat(),
                'm': metadata.modality,
                'r': [ai_h, ai_w],
                'n': metadata.frame_number
            }
            header_bytes = json.dumps(header).encode('utf-8')
            return struct.pack("I", len(header_bytes)) + header_bytes + ai_bytes
        except Exception as e:
            logger.error(f"AI binary encode failed ({metadata.camera_id}): {e}")
            return b""

    # Keep for backward compatibility
    def _serialize_frame(self, frame: np.ndarray, metadata: FrameMetadata) -> bytes:
        self._encode_display_frame(frame, metadata.camera_id)
        return self._encode_ai_frame_binary(frame, metadata)

    def _store_frame_data(self, camera_id: str, frame_data: bytes):
        """Push AI-quality frame to inference queue.
        
        OPTIMISATION: hard cap at AI_QUEUE_MAX entries and back-pressure check:
        if the queue is already deep we drop this frame entirely so the AI engine
        is never flooded and Redis memory stays bounded.
        """
        try:
            # ── OPTIMISATION: back-pressure — check current depth before pushing ──
            depth = self.redis_client.llen('frame_queue')
            if depth >= AI_QUEUE_BACKPRESSURE:
                return  # AI engine is already busy; discard this frame

            pipe = self.redis_client.pipeline()
            pipe.rpush('frame_queue', frame_data)
            # ── OPTIMISATION: keep only the newest AI_QUEUE_MAX frames ──
            pipe.ltrim('frame_queue', -AI_QUEUE_MAX, -1)
            pipe.execute()
        except Exception as e:
            logger.debug(f"AI queue store skipped ({camera_id}): {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # Capture loop
    # ─────────────────────────────────────────────────────────────────────────

    async def _capture_camera_frames(self, camera_id: str):
        """Capture and publish frames: display FIRST (instant push), AI SECOND (background).
        
        KEY OPTIMISATION — frame-skip for AI:
          Only every AI_FRAME_SKIP-th frame is forwarded to the inference queue.
          Display stream is unaffected (every frame is published).
        """
        adapter = self.cameras[camera_id]
        config = self.camera_configs[camera_id]
        next_frame_time = time.monotonic()
        empty_streak = 0

        while self.running and config.enabled:
            try:
                # ── Connection check ──────────────────────────────────────────
                if not adapter.is_connected():
                    attempt = getattr(adapter, '_conn_attempts', 0) + 1
                    adapter._conn_attempts = attempt
                    if attempt % 5 == 1:
                        logger.warning(
                            f"Camera {camera_id} disconnected, reconnect attempt {attempt}"
                        )
                    if not await adapter.connect():
                        await asyncio.sleep(5.0)
                        next_frame_time = time.monotonic()
                        continue
                    adapter._conn_attempts = 0

                # ── Fetch frame ───────────────────────────────────────────────
                frame, metadata = await adapter.get_frame()

                if frame is None or metadata is None:
                    empty_streak += 1
                    await asyncio.sleep(min(0.008 * empty_streak, 0.04))
                    continue

                empty_streak = 0
                self.stats['total_frames'] += 1
                self.stats['frames_per_camera'][camera_id] += 1
                self.stats['last_frame_time'][camera_id] = datetime.now()

                # ── STEP 1: Encode display JPEG + publish (priority path) ─────
                await asyncio.to_thread(self._encode_display_frame, frame, camera_id)

                # ── STEP 2: AI encoding — frame-skip + back-pressure ──────────
                if metadata.metadata.get('direct_detection') and 'direct_detections' in metadata.metadata:
                    # Direct detection path (thermal video) — always forward
                    det_payload = {
                        'camera_id': camera_id,
                        'frame_id': metadata.frame_id,
                        'timestamp': metadata.timestamp.isoformat(),
                        'modality': config.modality,
                        'detections': metadata.metadata['direct_detections']
                    }
                    pipe = self.redis_client.pipeline()
                    pipe.rpush('detection_queue', json.dumps(det_payload).encode('utf-8'))
                    pipe.ltrim('detection_queue', -100, -1)
                    pipe.execute()
                else:
                    # ── OPTIMISATION: frame-skip — only forward every Nth frame ──
                    self._ai_frame_counter[camera_id] = (
                        self._ai_frame_counter.get(camera_id, 0) + 1
                    )
                    if self._ai_frame_counter[camera_id] % AI_FRAME_SKIP == 0:
                        asyncio.create_task(self._ai_encode_and_queue(frame, metadata))

                # ── Steady-rate pacing ────────────────────────────────────────
                frame_time = 1.0 / max(config.fps_target, 1)
                next_frame_time += frame_time
                sleep_time = next_frame_time - time.monotonic()
                if sleep_time < -frame_time * 2:
                    next_frame_time = time.monotonic()
                    sleep_time = 0
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

            except Exception as e:
                logger.error(f"Error capturing frames from camera {camera_id}: {e}")
                self.stats['errors'][camera_id] += 1
                await asyncio.sleep(1.0)

    async def _ai_encode_and_queue(self, frame: np.ndarray, metadata: FrameMetadata):
        """Background task: encode AI frame and push to inference queue."""
        try:
            ai_data = await asyncio.to_thread(self._encode_ai_frame_binary, frame, metadata)
            if ai_data:
                await asyncio.to_thread(self._store_frame_data, metadata.camera_id, ai_data)
        except Exception as e:
            logger.debug(f"AI queue push skipped ({metadata.camera_id}): {e}")

    async def start_capture(self):
        """Start frame capture from all cameras, staggered to avoid simultaneous encoding bursts."""
        self.running = True
        await self.connect_all_cameras()
        tasks = []
        for idx, camera_id in enumerate(self.cameras):
            if idx > 0:
                await asyncio.sleep(0.15)
            task = asyncio.create_task(self._capture_camera_frames(camera_id))
            tasks.append(task)
        logger.info(f"Started frame capture from {len(self.cameras)} cameras (staggered)")
        await asyncio.gather(*tasks, return_exceptions=True)

    def stop_capture(self):
        self.running = False
        logger.info("Stopping frame capture")

    def get_stats(self) -> Dict[str, Any]:
        return {
            'total_cameras': len(self.cameras),
            'connected_cameras': sum(1 for cam in self.cameras.values() if cam.is_connected()),
            'total_frames': self.stats['total_frames'],
            'frames_per_camera': self.stats['frames_per_camera'],
            'errors_per_camera': self.stats['errors'],
            'last_frame_time': self.stats['last_frame_time']
        }


class ONVIFDiscovery:
    """ONVIF camera discovery service."""

    def __init__(self):
        self.discovered_cameras = []

    async def discover_cameras(self, timeout: int = 5) -> List[Dict]:
        discovered = []
        try:
            from onvif import ONVIFCamera
            ip_ranges = ['192.168.1.', '192.168.0.', '10.0.0.']
            for prefix in ip_ranges:
                for i in range(1, 255):
                    ip = f"{prefix}{i}"
                    try:
                        cam = ONVIFCamera(ip, 80, 'admin', 'admin')
                        if cam:
                            dev_info = cam.devicemgmt.GetDeviceInformation()
                            camera_info = {
                                'ip': ip,
                                'manufacturer': dev_info.Manufacturer,
                                'model': dev_info.Model,
                                'firmware': dev_info.FirmwareVersion,
                                'serial_number': dev_info.SerialNumber,
                                'hardware_id': dev_info.HardwareId
                            }
                            discovered.append(camera_info)
                            logger.info(f"Discovered ONVIF camera: {ip} ({dev_info.Model})")
                    except Exception:
                        continue
                    await asyncio.sleep(0.01)
            self.discovered_cameras = discovered
            logger.info(f"Discovered {len(discovered)} ONVIF cameras")
        except Exception as e:
            logger.error(f"ONVIF discovery failed: {e}")
        return discovered


class CameraGateway:
    """Main camera gateway service."""

    def __init__(self):
        self.camera_manager = CameraManager()
        self.onvif_discovery = ONVIFDiscovery()
        self.running = False

    async def _listen_for_updates(self):
        """Listen for camera configuration updates from Redis."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        import sys
        ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        BACKEND_DIR = os.path.join(ROOT_DIR, "backend_api")
        for _p in [ROOT_DIR, BACKEND_DIR]:
            if _p not in sys.path:
                sys.path.insert(0, _p)

        _default_db = f"sqlite:///{os.path.join(ROOT_DIR, 'backend_api', 'surveillance.db')}"
        DATABASE_URL = os.getenv("DATABASE_URL", _default_db)
        _engine = create_engine(
            DATABASE_URL,
            connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
        )
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)

        pubsub = self.camera_manager.redis_client.pubsub()
        pubsub.subscribe('camera_updates')
        logger.info("Listening for camera updates on Redis...")

        while self.running:
            try:
                message = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message:
                    raw_data = message.get('data')
                    if not raw_data:
                        continue
                    data = json.loads(raw_data)
                    action = data.get('action')
                    camera_id = data.get('camera_id')

                    if action == 'delete' and camera_id:
                        logger.info(f"Dynamic removal request for camera {camera_id}")
                        self.camera_manager.remove_camera(camera_id)

                    elif action == 'add' and camera_id:
                        logger.info(f"Dynamic add request for camera {camera_id}")
                        try:
                            from models import Camera as CameraModel
                            db = _SessionLocal()
                            c = db.query(CameraModel).filter(CameraModel.id == camera_id).first()
                            if c and camera_id not in self.camera_manager.cameras:
                                capture_url = c.rtsp_url
                                if c.config_json:
                                    if "stream_url" in c.config_json:
                                        capture_url = c.config_json["stream_url"]
                                    elif "mjpeg_url" in c.config_json:
                                        capture_url = c.config_json["mjpeg_url"]
                                if not capture_url and c.mjpeg_url:
                                    capture_url = c.mjpeg_url
                                config = CameraConfig(
                                    id=str(c.id), name=c.name, ip=c.ip, port=c.port,
                                    rtsp_url=capture_url, username=None, password=None,
                                    modality=c.modality, fps_target=c.fps or 15,
                                    enabled=c.is_active if c.is_active is not None else True,
                                    detection_enabled=(c.detection_enabled
                                                       if hasattr(c, 'detection_enabled') else True),
                                    mjpeg_url=c.mjpeg_url, hls_url=c.hls_url,
                                    stream_url=c.stream_url
                                )
                                self.camera_manager.add_camera(config)
                                asyncio.create_task(
                                    self.camera_manager._capture_camera_frames(camera_id)
                                )
                                logger.info(f"Dynamically added and started camera: {config.name}")
                            db.close()
                        except Exception as add_err:
                            logger.error(f"Failed to dynamically add camera {camera_id}: {add_err}")

                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Error in camera updates listener: {e}")
                await asyncio.sleep(1.0)

    async def start(self):
        self.running = True
        logger.info("Camera gateway service started")
        capture_task = asyncio.create_task(self.camera_manager.start_capture())
        listener_task = asyncio.create_task(self._listen_for_updates())
        await asyncio.gather(capture_task, listener_task)

    def stop(self):
        self.running = False
        self.camera_manager.stop_capture()
        logger.info("Camera gateway service stopped")

    def get_stats(self) -> Dict[str, Any]:
        return {
            'camera_manager': self.camera_manager.get_stats(),
            'discovered_cameras': len(self.onvif_discovery.discovered_cameras)
        }


if __name__ == "__main__":
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import uuid
    import sys

    ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    BACKEND_DIR = os.path.join(ROOT_DIR, "backend_api")
    for _p in [ROOT_DIR, BACKEND_DIR]:
        if _p not in sys.path:
            sys.path.insert(0, _p)

    _default_db = f"sqlite:///{os.path.join(ROOT_DIR, 'backend_api', 'surveillance.db')}"
    DATABASE_URL = os.getenv("DATABASE_URL", _default_db)
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    gateway = CameraGateway()

    while True:
        db = SessionLocal()
        try:
            from models import Camera
            cameras = db.query(Camera).filter(Camera.status == 'online').all()
            for c in cameras:
                capture_url = c.rtsp_url
                if c.config_json:
                    if "stream_url" in c.config_json:
                        capture_url = c.config_json["stream_url"]
                    elif "mjpeg_url" in c.config_json:
                        capture_url = c.config_json["mjpeg_url"]
                if not capture_url and c.mjpeg_url:
                    capture_url = c.mjpeg_url
                config = CameraConfig(
                    id=str(c.id), name=c.name, ip=c.ip, port=c.port,
                    rtsp_url=capture_url, username=None, password=None,
                    modality=c.modality, fps_target=c.fps or 15,
                    enabled=c.is_active if c.is_active is not None else True,
                    detection_enabled=(c.detection_enabled
                                       if hasattr(c, 'detection_enabled') else True),
                    mjpeg_url=c.mjpeg_url, hls_url=c.hls_url, stream_url=c.stream_url
                )
                gateway.camera_manager.add_camera(config)
                logger.info(
                    f"Loaded camera: {config.name} | "
                    f"Capture URL: {capture_url} | Detection: {config.detection_enabled}"
                )
            break
        except Exception as e:
            logger.error(f"Failed to load cameras from DB (retrying in 5s): {e}")
            time.sleep(5)
        finally:
            db.close()

    try:
        asyncio.run(gateway.start())
    except KeyboardInterrupt:
        gateway.stop()
        logger.info("Camera gateway stopped by user")
    except Exception as e:
        import traceback
        logger.error(f"FATAL: Camera Gateway crashed: {e}\n{traceback.format_exc()}")
        gateway.stop()
        sys.exit(1)
