#!/usr/bin/env python3
"""
Ultra-Low Latency Detection for IP Webcam
Optimized for phone camera streaming with minimal latency.
"""

import time
import numpy as np
import cv2
import torch
import threading
import queue
import requests
from pathlib import Path
from typing import List, Tuple, Dict, Optional
import logging
from dataclasses import dataclass
import argparse
from ultralytics import YOLO
import urllib.request

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class Detection:
    """Detection result with normalized coordinates."""
    class_name: str
    confidence: float
    bbox: List[float]  # [x1, y1, x2, y2] normalized (0.0-1.0)

class UltraLowLatencyDetector:
    """Ultra-low latency GPU-optimized YOLO detector."""
    
    def __init__(self, model_path: str, conf_threshold: float = 0.25, iou_threshold: float = 0.45, 
                 use_gpu: bool = True, optimize_for_latency: bool = True):
        """
        Initialize ultra-low latency detector.
        
        Args:
            model_path: Path to PyTorch model file
            conf_threshold: Confidence threshold for detections
            iou_threshold: IoU threshold for NMS
            use_gpu: Whether to use GPU acceleration
            optimize_for_latency: Whether to optimize for minimal latency
        """
        self.model_path = Path(model_path)
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.use_gpu = use_gpu and torch.cuda.is_available()
        self.optimize_for_latency = optimize_for_latency
        self.device = 'cuda' if self.use_gpu else 'cpu'
        
        # Load and optimize model
        self.model = self._load_optimized_model()
        
        # Performance metrics
        self.inference_times = []
        self.frame_count = 0
        self.last_sync_time = time.time()
        
        logger.info(f"Ultra-low latency detector initialized")
        logger.info(f"Model: {model_path}")
        logger.info(f"Device: {self.device.upper()}")
        logger.info(f"Latency optimization: {'✅ Enabled' if optimize_for_latency else '❌ Disabled'}")
        
        if self.use_gpu:
            logger.info(f"GPU: {torch.cuda.get_device_name(0)}")
    
    def _load_optimized_model(self) -> YOLO:
        """Load and optimize model for minimal latency."""
        model = YOLO(str(self.model_path))
        
        if self.use_gpu:
            # Move to GPU
            model.to('cuda')
            
            if self.optimize_for_latency:
                # Optimize for inference speed
                model.fuse()  # Fuse Conv2d + BatchNorm + SiLU
                
                # Enable TensorFloat-32 for better performance on RTX 3070
                torch.backends.cuda.matmul.allow_tf32 = True
                torch.backends.cudnn.allow_tf32 = True
                
                # Optimize cuDNN for speed
                torch.backends.cudnn.benchmark = True
                torch.backends.cudnn.deterministic = False
                
                logger.info("Applied GPU latency optimizations")
        
        return model
    
    def detect(self, image: np.ndarray) -> Tuple[List[Detection], float]:
        """
        Run ultra-low latency detection on an image.
        
        Args:
            image: Input image in BGR format
            
        Returns:
            detections: List of Detection objects
            inference_time: Time taken for inference in seconds
        """
        # Pre-allocate for speed
        orig_h, orig_w = image.shape[:2]
        
        # GPU synchronization for accurate timing
        if self.use_gpu:
            torch.cuda.synchronize()
        
        start_time = time.perf_counter()
        
        # Run inference with minimal overhead
        results = self.model(
            image, 
            conf=self.conf_threshold, 
            iou=self.iou_threshold, 
            verbose=False,
            device=self.device,
            # Latency optimizations
            imgsz=640,  # Fixed size for no resizing
            augment=False,  # No augmentation for speed
            agnostic_nms=False,  # Class-specific NMS is faster
        )
        
        if self.use_gpu:
            torch.cuda.synchronize()
        
        inference_time = time.perf_counter() - start_time
        
        # Fast post-processing
        detections = []
        for r in results:
            if hasattr(r, 'boxes') and r.boxes is not None:
                # Vectorized processing for speed
                boxes = r.boxes.xyxy.cpu().numpy()  # [N, 4]
                confidences = r.boxes.conf.cpu().numpy()  # [N]
                classes = r.boxes.cls.cpu().numpy().astype(int)  # [N]
                
                # Batch process all detections
                for i in range(len(boxes)):
                    x1, y1, x2, y2 = boxes[i]
                    confidence = float(confidences[i])
                    class_id = classes[i]
                    
                    # Fast normalization
                    x1_norm = max(0.0, min(x1, orig_w - 1)) / orig_w
                    y1_norm = max(0.0, min(y1, orig_h - 1)) / orig_h
                    x2_norm = max(0.0, min(x2, orig_w - 1)) / orig_w
                    y2_norm = max(0.0, min(y2, orig_h - 1)) / orig_h
                    
                    class_name = self.model.names[class_id]
                    
                    detection = Detection(
                        class_name=class_name,
                        confidence=confidence,
                        bbox=[x1_norm, y1_norm, x2_norm, y2_norm]
                    )
                    detections.append(detection)
        
        # Update metrics
        self.inference_times.append(inference_time)
        self.frame_count += 1
        
        return detections, inference_time
    
    def get_performance_stats(self) -> Dict[str, float]:
        """Get ultra-low latency performance statistics."""
        if not self.inference_times:
            return {}
        
        times = np.array(self.inference_times)
        avg_time = np.mean(times) * 1000
        min_time = np.min(times) * 1000
        max_time = np.max(times) * 1000
        p95_time = np.percentile(times, 95) * 1000
        p99_time = np.percentile(times, 99) * 1000
        fps = 1.0 / np.mean(times)
        
        stats = {
            'avg_inference_time_ms': avg_time,
            'min_inference_time_ms': min_time,
            'max_inference_time_ms': max_time,
            'p95_inference_time_ms': p95_time,
            'p99_inference_time_ms': p99_time,
            'fps': fps,
            'total_frames': self.frame_count
        }
        
        if self.use_gpu:
            stats['gpu_memory_gb'] = torch.cuda.memory_allocated() / 1024**3
        
        return stats

class IPCameraCapture:
    """Optimized IP camera capture for phone streaming."""
    
    def __init__(self, ip_address: str, port: int = 8080, username: Optional[str] = None, 
                 password: Optional[str] = None, buffer_size: int = 1):
        """
        Initialize IP camera capture.
        
        Args:
            ip_address: IP address of the phone
            port: Port number (default 8080 for IP Webcam)
            username: Optional username for authentication
            password: Optional password for authentication
            buffer_size: Frame buffer size (1 = minimal latency)
        """
        self.ip_address = ip_address
        self.port = port
        self.username = username
        self.password = password
        self.buffer_size = buffer_size
        
        self.cap = None
        self.running = False
        self.capture_thread = None
        self.frame_queue = queue.Queue(maxsize=buffer_size)
        
        # Performance metrics
        self.actual_fps = 0
        self.frame_count = 0
        self.last_fps_time = time.time()
        self.connection_errors = 0
        
        # Build URL
        self.stream_url = self._build_stream_url()
        
    def _build_stream_url(self) -> str:
        """Build the stream URL for IP Webcam."""
        if self.username and self.password:
            auth = f"{self.username}:{self.password}@"
        else:
            auth = ""
        
        # IP Webcam app typically uses this URL format
        return f"http://{auth}{self.ip_address}:{self.port}/video"
    
    def start(self):
        """Start IP camera capture in separate thread."""
        try:
            # Test connection first
            self._test_connection()
            
            self.cap = cv2.VideoCapture(self.stream_url)
            
            if not self.cap.isOpened():
                raise RuntimeError(f"Failed to open IP camera stream: {self.stream_url}")
            
            # Optimize for low latency
            self._configure_camera()
            
            self.running = True
            self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.capture_thread.start()
            
            logger.info(f"IP camera capture started: {self.stream_url}")
            
        except Exception as e:
            logger.error(f"Failed to start IP camera: {e}")
            raise
    
    def _test_connection(self):
        """Test connection to IP camera."""
        try:
            # Simple HTTP request to test connectivity
            test_url = f"http://{self.ip_address}:{self.port}/status.json"
            response = requests.get(test_url, timeout=5)
            if response.status_code == 200:
                logger.info(f"Successfully connected to IP camera at {self.ip_address}:{self.port}")
            else:
                logger.warning(f"IP camera returned status {response.status_code}")
        except Exception as e:
            logger.warning(f"Could not test IP camera connection: {e}")
            logger.info("Make sure IP Webcam app is running and accessible")
    
    def _configure_camera(self):
        """Configure camera for optimal performance."""
        # Set buffer size to minimal for low latency
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, self.buffer_size)
        
        # Try to set optimal resolution
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        
        # Set FPS target
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        
        logger.info("IP camera configured for low latency")
    
    def _capture_loop(self):
        """Main capture loop running in separate thread."""
        consecutive_errors = 0
        max_errors = 10
        
        while self.running:
            try:
                ret, frame = self.cap.read()
                
                if not ret:
                    consecutive_errors += 1
                    if consecutive_errors >= max_errors:
                        logger.error(f"Too many consecutive errors ({max_errors}), stopping capture")
                        break
                    
                    logger.warning(f"Failed to capture frame (error {consecutive_errors}/{max_errors})")
                    time.sleep(0.1)
                    continue
                
                # Reset error counter on successful capture
                consecutive_errors = 0
                
                # Update FPS counter
                self.frame_count += 1
                current_time = time.time()
                if current_time - self.last_fps_time >= 1.0:
                    self.actual_fps = self.frame_count / (current_time - self.last_fps_time)
                    self.frame_count = 0
                    self.last_fps_time = current_time
                
                # Add frame to queue (non-blocking)
                try:
                    self.frame_queue.put_nowait(frame)
                except queue.Full:
                    # Drop oldest frame if queue is full
                    try:
                        self.frame_queue.get_nowait()
                        self.frame_queue.put_nowait(frame)
                    except queue.Empty:
                        pass
                
            except Exception as e:
                logger.error(f"Capture loop error: {e}")
                consecutive_errors += 1
                if consecutive_errors >= max_errors:
                    break
                time.sleep(0.1)
    
    def get_frame(self) -> Optional[np.ndarray]:
        """Get latest frame (non-blocking)."""
        try:
            return self.frame_queue.get_nowait()
        except queue.Empty:
            return None
    
    def stop(self):
        """Stop IP camera capture."""
        self.running = False
        if self.capture_thread:
            self.capture_thread.join(timeout=1.0)
        if self.cap:
            self.cap.release()
        logger.info("IP camera capture stopped")

class IPCameraStreamingApp:
    """Ultra-low latency real-time detection with IP camera streaming."""
    
    def __init__(self, model_path: str, ip_address: str, port: int = 8080, 
                 conf_threshold: float = 0.25, iou_threshold: float = 0.45, 
                 use_gpu: bool = True, target_fps: int = 30, frame_skip: int = 1,
                 username: Optional[str] = None, password: Optional[str] = None):
        """
        Initialize IP camera streaming app.
        
        Args:
            model_path: Path to PyTorch model
            ip_address: IP address of phone with IP Webcam
            port: Port number for IP Webcam
            conf_threshold: Confidence threshold
            iou_threshold: IoU threshold
            use_gpu: Whether to use GPU acceleration
            target_fps: Target FPS for smooth streaming
            frame_skip: Number of frames to skip between detections
            username: Optional username for authentication
            password: Optional password for authentication
        """
        self.detector = UltraLowLatencyDetector(
            model_path, conf_threshold, iou_threshold, use_gpu, optimize_for_latency=True
        )
        self.camera = IPCameraCapture(
            ip_address, port, username, password, buffer_size=1
        )
        self.target_fps = target_fps
        self.frame_skip = frame_skip
        self.running = False
        
        # Threading for smooth streaming
        self.detection_thread = None
        self.detection_queue = queue.Queue(maxsize=1)
        self.latest_detections = []
        
        # Performance tracking
        self.frame_times = []
        self.display_times = []
        self.last_frame_time = 0
        
        # Colors for different classes
        self.colors = self._generate_colors(len(self.detector.model.names))
        
        logger.info(f"IP camera streaming app initialized")
        logger.info(f"Camera: {ip_address}:{port}")
        logger.info(f"Target FPS: {target_fps}")
        logger.info(f"Frame skip: {frame_skip}")
        logger.info(f"GPU acceleration: {'✅' if use_gpu else '❌'}")
    
    def _generate_colors(self, num_classes: int) -> List[Tuple[int, int, int]]:
        """Generate distinct colors for each class."""
        np.random.seed(42)
        colors = []
        for i in range(num_classes):
            color = (np.random.randint(0, 255), 
                    np.random.randint(0, 255), 
                    np.random.randint(0, 255))
            colors.append(color)
        return colors
    
    def _detect_objects(self):
        """Detection thread for parallel processing."""
        frame_count = 0
        
        while self.running:
            try:
                # Get frame from camera
                frame = self.camera.get_frame()
                if frame is None:
                    time.sleep(0.01)
                    continue
                
                # Skip frames for performance
                if frame_count % (self.frame_skip + 1) == 0:
                    detections, inference_time = self.detector.detect(frame)
                    
                    # Update latest detections
                    self.latest_detections = detections
                    
                    # Add to detection queue
                    try:
                        self.detection_queue.put_nowait((frame.copy(), detections, inference_time))
                    except queue.Full:
                        pass
                else:
                    # Use latest detections for skipped frames
                    try:
                        self.detection_queue.put_nowait((frame.copy(), self.latest_detections, 0))
                    except queue.Full:
                        pass
                
                frame_count += 1
                
            except Exception as e:
                logger.error(f"Detection error: {e}")
                time.sleep(0.01)
    
    def draw_detections(self, image: np.ndarray, detections: List[Detection], 
                      inference_time: float) -> np.ndarray:
        """Draw detection results with minimal overhead."""
        result_image = image.copy()
        
        # Pre-calculate dimensions
        h, w = image.shape[:2]
        
        for detection in detections:
            # Get color for this class
            class_names = list(self.detector.model.names.values())
            if detection.class_name in class_names:
                class_idx = class_names.index(detection.class_name)
                color = self.colors[class_idx % len(self.colors)]
            else:
                color = (0, 255, 0)
            
            # Convert normalized coordinates to pixel coordinates
            x1 = int(detection.bbox[0] * w)
            y1 = int(detection.bbox[1] * h)
            x2 = int(detection.bbox[2] * w)
            y2 = int(detection.bbox[3] * h)
            
            # Draw bounding box
            cv2.rectangle(result_image, (x1, y1), (x2, y2), color, 2)
            
            # Draw label with confidence (simplified for speed)
            label = f"{detection.class_name}: {detection.confidence:.2f}"
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
            
            # Background for label
            cv2.rectangle(result_image, (x1, y1 - label_size[1] - 10), 
                        (x1 + label_size[0], y1), color, -1)
            
            # Label text
            cv2.putText(result_image, label, (x1, y1 - 5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        
        # Add performance stats
        stats = self.detector.get_performance_stats()
        fps = stats.get('fps', 0)
        avg_time = stats.get('avg_inference_time_ms', 0)
        device_status = "GPU" if self.detector.use_gpu else "CPU"
        camera_fps = self.camera.actual_fps
        
        # Performance overlay
        cv2.putText(result_image, f"Camera: {camera_fps:.1f} FPS", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(result_image, f"AI: {fps:.1f} FPS ({device_status})", (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(result_image, f"Avg: {avg_time:.1f}ms", (10, 90),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(result_image, f"Detections: {len(detections)}", (10, 120),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        if inference_time > 0:
            cv2.putText(result_image, f"Current: {inference_time*1000:.1f}ms", (10, 150),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        return result_image
    
    def run(self):
        """Run ultra-low latency IP camera streaming."""
        logger.info("Starting ultra-low latency IP camera streaming")
        logger.info("Press 'q' to quit, 's' to toggle stats, 'f' to change frame skip")
        
        try:
            # Start camera
            self.camera.start()
        except Exception as e:
            logger.error(f"Failed to start camera: {e}")
            return
        
        self.running = True
        
        # Start detection thread
        self.detection_thread = threading.Thread(target=self._detect_objects, daemon=True)
        self.detection_thread.start()
        
        # Main display loop
        frame_count = 0
        start_time = time.perf_counter()
        show_stats = True
        
        while self.running:
            loop_start = time.perf_counter()
            
            try:
                # Get detection result
                frame, detections, inference_time = self.detection_queue.get(timeout=0.1)
                
                # Draw results
                result_frame = self.draw_detections(frame, detections, inference_time)
                
                # Display
                cv2.imshow('Ultra-Low Latency IP Camera Detection', result_frame)
                
                # Handle keys
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q') or key == 27:  # q or ESC
                    break
                elif key == ord('s'):
                    show_stats = not show_stats
                elif key == ord('f'):
                    self.frame_skip = (self.frame_skip + 1) % 4
                    logger.info(f"Frame skip: {self.frame_skip}")
                
                # Track display performance
                display_time = time.perf_counter() - loop_start
                self.display_times.append(display_time)
                
                frame_count += 1
                
                # Print stats periodically
                if frame_count % 60 == 0 and show_stats:
                    elapsed = time.perf_counter() - start_time
                    actual_fps = frame_count / elapsed
                    
                    stats = self.detector.get_performance_stats()
                    logger.info(f"Performance: Camera={self.camera.actual_fps:.1f} FPS, "
                              f"AI={stats.get('fps', 0):.1f} FPS, "
                              f"Avg Latency: {stats.get('avg_inference_time_ms', 0):.1f}ms")
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Display error: {e}")
                break
        
        # Cleanup
        self.running = False
        cv2.destroyAllWindows()
        
        # Wait for threads to finish
        if self.detection_thread:
            self.detection_thread.join(timeout=1.0)
        self.camera.stop()
        
        # Final stats
        final_stats = self.detector.get_performance_stats()
        logger.info("=== Final Performance Stats ===")
        for key, value in final_stats.items():
            logger.info(f"{key}: {value:.2f}")

def main():
    parser = argparse.ArgumentParser(description="Ultra-Low Latency IP Camera Detection")
    parser.add_argument('--model', type=str, default='models/yolov8n.pt',
                        help='Path to PyTorch model file')
    parser.add_argument('--ip', type=str, required=True,
                        help='IP address of phone with IP Webcam app')
    parser.add_argument('--port', type=int, default=8080,
                        help='Port number for IP Webcam (default: 8080)')
    parser.add_argument('--username', type=str, default=None,
                        help='Username for IP Webcam authentication')
    parser.add_argument('--password', type=str, default=None,
                        help='Password for IP Webcam authentication')
    parser.add_argument('--conf', type=float, default=0.25,
                        help='Confidence threshold')
    parser.add_argument('--iou', type=float, default=0.45,
                        help='IoU threshold for NMS')
    parser.add_argument('--fps', type=int, default=30,
                        help='Target FPS')
    parser.add_argument('--frame-skip', type=int, default=1,
                        help='Number of frames to skip between detections (0=no skip, 1=skip 1, etc)')
    parser.add_argument('--benchmark', action='store_true',
                        help='Run ultra-low latency benchmark')
    parser.add_argument('--benchmark-frames', type=int, default=100,
                        help='Number of frames for benchmark')
    parser.add_argument('--no-gpu', action='store_true',
                        help='Force CPU-only mode')
    
    args = parser.parse_args()
    
    if args.benchmark:
        # Ultra-low latency benchmark
        logger.info("Running ultra-low latency benchmark...")
        detector = UltraLowLatencyDetector(
            args.model, 
            use_gpu=not args.no_gpu,
            optimize_for_latency=True
        )
        
        # Create test image
        test_image = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
        
        # Warm up
        logger.info("Warming up...")
        for _ in range(10):
            detector.detect(test_image)
        
        # Benchmark
        logger.info(f"Benchmarking {args.benchmark_frames} frames...")
        times = []
        for i in range(args.benchmark_frames):
            _, inference_time = detector.detect(test_image)
            times.append(inference_time)
            
            if (i + 1) % 20 == 0:
                logger.info(f"  Processed {i + 1}/{args.benchmark_frames} frames")
        
        # Results
        stats = detector.get_performance_stats()
        logger.info("=== Ultra-Low Latency Benchmark Results ===")
        logger.info(f"Model: {args.model}")
        logger.info(f"Device: {detector.device.upper()}")
        logger.info(f"Average Latency: {stats['avg_inference_time_ms']:.1f}ms")
        logger.info(f"Min Latency: {stats['min_inference_time_ms']:.1f}ms")
        logger.info(f"P95 Latency: {stats['p95_inference_time_ms']:.1f}ms")
        logger.info(f"P99 Latency: {stats['p99_inference_time_ms']:.1f}ms")
        logger.info(f"FPS: {stats['fps']:.1f}")
        
        if detector.use_gpu:
            logger.info(f"GPU Memory: {stats['gpu_memory_gb']:.2f} GB")
        
    else:
        # Real-time detection with IP camera
        if not Path(args.model).exists():
            logger.error(f"Model file not found: {args.model}")
            return
        
        app = IPCameraStreamingApp(
            model_path=args.model,
            ip_address=args.ip,
            port=args.port,
            username=args.username,
            password=args.password,
            conf_threshold=args.conf,
            iou_threshold=args.iou,
            use_gpu=not args.no_gpu,
            target_fps=args.fps,
            frame_skip=args.frame_skip
        )
        app.run()

if __name__ == "__main__":
    main()
