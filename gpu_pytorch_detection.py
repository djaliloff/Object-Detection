#!/usr/bin/env python3
"""
GPU-Optimized Real-time Detection with PyTorch
Leverages RTX 3070 GPU for maximum performance in real-time object detection.
"""

import time
import numpy as np
import cv2
import torch
from pathlib import Path
from typing import List, Tuple, Dict, Optional
import logging
from dataclasses import dataclass
import argparse
from ultralytics import YOLO

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class Detection:
    """Detection result with normalized coordinates."""
    class_name: str
    confidence: float
    bbox: List[float]  # [x1, y1, x2, y2] normalized (0.0-1.0)

class GPUPyTorchDetector:
    """GPU-optimized PyTorch YOLO detector."""
    
    def __init__(self, model_path: str, conf_threshold: float = 0.25, iou_threshold: float = 0.45, 
                 use_gpu: bool = True):
        """
        Initialize GPU-optimized PyTorch YOLO detector.
        
        Args:
            model_path: Path to PyTorch model file
            conf_threshold: Confidence threshold for detections
            iou_threshold: IoU threshold for Non-Maximum Suppression
            use_gpu: Whether to use GPU acceleration
        """
        self.model_path = Path(model_path)
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.use_gpu = use_gpu and torch.cuda.is_available()
        self.device = 'cuda' if self.use_gpu else 'cpu'
        
        # Load PyTorch model
        self.model = YOLO(str(self.model_path))
        
        # Move model to GPU if requested
        if self.use_gpu:
            self.model.to('cuda')
        
        # Performance metrics
        self.inference_times = []
        self.frame_count = 0
        
        logger.info(f"Loaded model: {model_path}")
        logger.info(f"Device: {self.device.upper()}")
        logger.info(f"GPU acceleration: {'✓ Enabled' if self.use_gpu else '✗ Disabled (CPU only)'}")
        
        if self.use_gpu:
            logger.info(f"GPU: {torch.cuda.get_device_name(0)}")
            logger.info(f"GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
    
    def detect(self, image: np.ndarray) -> Tuple[List[Detection], float]:
        """
        Run object detection on an image.
        
        Args:
            image: Input image in BGR format
            
        Returns:
            detections: List of Detection objects
            inference_time: Time taken for inference in seconds
        """
        # Run inference
        start_time = time.time()
        
        if self.use_gpu:
            torch.cuda.synchronize()
        
        results = self.model(image, conf=self.conf_threshold, iou=self.iou_threshold, 
                           verbose=False, device=self.device)
        
        if self.use_gpu:
            torch.cuda.synchronize()
        
        inference_time = time.time() - start_time
        
        # Convert results to Detection objects
        detections = []
        orig_h, orig_w = image.shape[:2]
        
        for r in results:
            for box in r.boxes:
                class_id = int(box.cls[0])
                confidence = float(box.conf[0])
                
                # Convert pixel boundaries to 0.0-1.0 normalized coordinates
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                
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
        """Get performance statistics."""
        if not self.inference_times:
            return {}
        
        avg_inference_time = np.mean(self.inference_times)
        min_inference_time = np.min(self.inference_times)
        max_inference_time = np.max(self.inference_times)
        fps = 1.0 / avg_inference_time if avg_inference_time > 0 else 0
        
        stats = {
            'avg_inference_time_ms': avg_inference_time * 1000,
            'min_inference_time_ms': min_inference_time * 1000,
            'max_inference_time_ms': max_inference_time * 1000,
            'fps': fps,
            'total_frames': self.frame_count
        }
        
        if self.use_gpu:
            stats['gpu_memory_gb'] = torch.cuda.memory_allocated() / 1024**3
        
        return stats

class GPURealTimeDetectionApp:
    """GPU-accelerated real-time detection application."""
    
    def __init__(self, model_path: str, camera_id: int = 0, conf_threshold: float = 0.25, 
                 iou_threshold: float = 0.45, use_gpu: bool = True):
        """
        Initialize GPU-optimized real-time detection app.
        
        Args:
            model_path: Path to PyTorch model
            camera_id: Camera device ID
            conf_threshold: Confidence threshold
            iou_threshold: IoU threshold
            use_gpu: Whether to use GPU acceleration
        """
        self.detector = GPUPyTorchDetector(model_path, conf_threshold, iou_threshold, use_gpu)
        self.camera_id = camera_id
        self.running = False
        
        # Colors for different classes (BGR format)
        self.colors = self._generate_colors(len(self.detector.model.names))
    
    def _generate_colors(self, num_classes: int) -> List[Tuple[int, int, int]]:
        """Generate distinct colors for each class."""
        np.random.seed(42)  # For consistent colors
        colors = []
        for i in range(num_classes):
            color = (np.random.randint(0, 255), 
                    np.random.randint(0, 255), 
                    np.random.randint(0, 255))
            colors.append(color)
        return colors
    
    def draw_detections(self, image: np.ndarray, detections: List[Detection]) -> np.ndarray:
        """Draw detection results on image."""
        result_image = image.copy()
        
        for detection in detections:
            # Get color for this class
            class_names = list(self.detector.model.names.values())
            if detection.class_name in class_names:
                class_idx = class_names.index(detection.class_name)
                color = self.colors[class_idx % len(self.colors)]
            else:
                color = (0, 255, 0)  # Default green
            
            # Convert normalized coordinates to pixel coordinates
            h, w = image.shape[:2]
            x1 = int(detection.bbox[0] * w)
            y1 = int(detection.bbox[1] * h)
            x2 = int(detection.bbox[2] * w)
            y2 = int(detection.bbox[3] * h)
            
            # Draw bounding box
            cv2.rectangle(result_image, (x1, y1), (x2, y2), color, 2)
            
            # Draw label with confidence
            label = f"{detection.class_name}: {detection.confidence:.2f}"
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
            
            # Draw background for label
            cv2.rectangle(result_image, 
                         (x1, y1 - label_size[1] - 10), 
                         (x1 + label_size[0], y1), 
                         color, -1)
            
            # Draw label text
            cv2.putText(result_image, label, (x1, y1 - 5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        
        return result_image
    
    def run(self, show_stats: bool = True):
        """Run GPU-accelerated real-time detection."""
        # Initialize camera
        cap = cv2.VideoCapture(self.camera_id)
        
        if not cap.isOpened():
            logger.error(f"Failed to open camera {self.camera_id}")
            return
        
        # Set camera properties for better performance
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)  # Higher resolution for better GPU utilization
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cap.set(cv2.CAP_PROP_FPS, 60)  # Higher FPS target
        
        logger.info("Starting GPU-accelerated real-time detection. Press 'q' to quit.")
        logger.info(f"GPU Status: {'✓ RTX 3070 Active' if self.detector.use_gpu else '✗ CPU Only'}")
        self.running = True
        
        frame_count = 0
        start_time = time.time()
        
        while self.running:
            # Read frame
            ret, frame = cap.read()
            
            if not ret:
                logger.error("Failed to read frame from camera")
                break
            
            # Run detection
            detections, inference_time = self.detector.detect(frame)
            
            # Draw results
            result_frame = self.draw_detections(frame, detections)
            
            # Add performance stats
            if show_stats and frame_count % 5 == 0:  # Update stats every 5 frames
                stats = self.detector.get_performance_stats()
                fps = stats.get('fps', 0)
                avg_time = stats.get('avg_inference_time_ms', 0)
                device_status = "GPU" if self.detector.use_gpu else "CPU"
                
                cv2.putText(result_frame, f"FPS: {fps:.1f} ({device_status})", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.putText(result_frame, f"Avg Time: {avg_time:.1f}ms", (10, 70),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.putText(result_frame, f"Detections: {len(detections)}", (10, 110),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                
                # GPU memory usage
                if self.detector.use_gpu and 'gpu_memory_gb' in stats:
                    gpu_memory = stats['gpu_memory_gb']
                    cv2.putText(result_frame, f"GPU Memory: {gpu_memory:.1f}GB", (10, 150),
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            
            # Display frame
            cv2.imshow('GPU-Accelerated Real-time Object Detection', result_frame)
            
            # Check for quit key
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            
            frame_count += 1
        
        # Cleanup
        cap.release()
        cv2.destroyAllWindows()
        self.running = False
        
        # Print final stats
        final_stats = self.detector.get_performance_stats()
        logger.info("=== Final Performance Stats ===")
        for key, value in final_stats.items():
            logger.info(f"{key}: {value:.2f}")

def main():
    parser = argparse.ArgumentParser(description="GPU-Accelerated Real-time Object Detection with PyTorch")
    parser.add_argument('--model', type=str, default='models/yolov8n.pt',
                        help='Path to PyTorch model file')
    parser.add_argument('--camera', type=int, default=0,
                        help='Camera device ID')
    parser.add_argument('--conf', type=float, default=0.25,
                        help='Confidence threshold')
    parser.add_argument('--iou', type=float, default=0.45,
                        help='IoU threshold for NMS')
    parser.add_argument('--benchmark', action='store_true',
                        help='Run quick benchmark instead of real-time detection')
    parser.add_argument('--benchmark-frames', type=int, default=50,
                        help='Number of frames for benchmark')
    parser.add_argument('--no-gpu', action='store_true',
                        help='Force CPU-only mode')
    
    args = parser.parse_args()
    
    if args.benchmark:
        # Quick benchmark
        logger.info("Running quick benchmark...")
        detector = GPUPyTorchDetector(args.model, use_gpu=not args.no_gpu)
        
        # Create test image
        test_image = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
        
        # Warm up
        for _ in range(5):
            detector.detect(test_image)
        
        # Benchmark
        times = []
        for i in range(args.benchmark_frames):
            _, inference_time = detector.detect(test_image)
            times.append(inference_time)
        
        avg_time = np.mean(times) * 1000
        fps = 1.0 / np.mean(times)
        
        logger.info(f"Benchmark Results:")
        logger.info(f"Model: {args.model}")
        logger.info(f"Device: {detector.device.upper()}")
        logger.info(f"Average Time: {avg_time:.1f}ms")
        logger.info(f"FPS: {fps:.1f}")
        
        stats = detector.get_performance_stats()
        if 'gpu_memory_gb' in stats:
            logger.info(f"GPU Memory: {stats['gpu_memory_gb']:.2f} GB")
    else:
        # Real-time detection
        if not Path(args.model).exists():
            logger.error(f"Model file not found: {args.model}")
            return
        
        app = GPURealTimeDetectionApp(
            model_path=args.model,
            camera_id=args.camera,
            conf_threshold=args.conf,
            iou_threshold=args.iou,
            use_gpu=not args.no_gpu
        )
        app.run()

if __name__ == "__main__":
    main()
