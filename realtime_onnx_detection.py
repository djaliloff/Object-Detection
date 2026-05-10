#!/usr/bin/env python3
"""
Real-time Object Detection with ONNX YOLO Models
Optimized for minimal latency and maximum performance using ONNX Runtime.
Supports YOLOv11, YOLOv8, and YOLOv9 models in ONNX format.
"""

import os
import time
import cv2
import numpy as np
import onnxruntime as ort
from pathlib import Path
from typing import List, Tuple, Dict, Optional
import logging
from dataclasses import dataclass
import argparse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class Detection:
    """Detection result with normalized coordinates."""
    class_name: str
    confidence: float
    bbox: List[float]  # [x1, y1, x2, y2] normalized (0.0-1.0)

class ONNXYOLODetector:
    """Optimized YOLO detector using ONNX Runtime for real-time inference."""
    
    # COCO class names
    COCO_CLASSES = [
        'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck',
        'boat', 'traffic light', 'fire hydrant', 'stop sign', 'parking meter', 'bench',
        'bird', 'cat', 'dog', 'horse', 'sheep', 'cow', 'elephant', 'bear', 'zebra',
        'giraffe', 'backpack', 'umbrella', 'handbag', 'tie', 'suitcase', 'frisbee',
        'skis', 'snowboard', 'sports ball', 'kite', 'baseball bat', 'baseball glove',
        'skateboard', 'surfboard', 'tennis racket', 'bottle', 'wine glass', 'cup',
        'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple', 'sandwich', 'orange',
        'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake', 'chair', 'couch',
        'potted plant', 'bed', 'dining table', 'toilet', 'tv', 'laptop', 'mouse',
        'remote', 'keyboard', 'cell phone', 'microwave', 'oven', 'toaster', 'sink',
        'refrigerator', 'book', 'clock', 'vase', 'scissors', 'teddy bear', 'hair drier',
        'toothbrush'
    ]
    
    def __init__(self, model_path: str, conf_threshold: float = 0.25, iou_threshold: float = 0.45):
        """
        Initialize ONNX YOLO detector.
        
        Args:
            model_path: Path to ONNX model file
            conf_threshold: Confidence threshold for detections
            iou_threshold: IoU threshold for Non-Maximum Suppression
        """
        self.model_path = Path(model_path)
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        
        # Load ONNX model with optimal providers
        self.session = self._load_onnx_model()
        
        # Get model input/output info
        self.input_name = self.session.get_inputs()[0].name
        self.input_shape = self.session.get_inputs()[0].shape
        self.output_names = [output.name for output in self.session.get_outputs()]
        
        logger.info(f"Loaded model: {model_path}")
        logger.info(f"Input: {self.input_name}, shape: {self.input_shape}")
        logger.info(f"Outputs: {self.output_names}")
        
        # Performance metrics
        self.inference_times = []
        self.frame_count = 0
    
    def _load_onnx_model(self) -> ort.InferenceSession:
        """Load ONNX model with optimal execution providers."""
        # Try GPU first, fallback to CPU
        providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
        
        try:
            session = ort.InferenceSession(str(self.model_path), providers=providers)
            
            # Check which providers are actually available
            available_providers = session.get_providers()
            logger.info(f"Available providers: {available_providers}")
            
            return session
        except Exception as e:
            logger.error(f"Failed to load ONNX model: {e}")
            raise
    
    def preprocess_image(self, image: np.ndarray) -> Tuple[np.ndarray, float, float]:
        """
        Preprocess image for ONNX inference.
        
        Args:
            image: Input image in BGR format
            
        Returns:
            preprocessed_image: Image ready for model input
            scale_x: X scaling factor for coordinate conversion
            scale_y: Y scaling factor for coordinate conversion
        """
        # Get original dimensions
        orig_h, orig_w = image.shape[:2]
        
        # Get target size from model input shape
        if len(self.input_shape) == 4:
            target_h, target_w = self.input_shape[2], self.input_shape[3]
        else:
            target_h, target_w = 640, 640  # Default YOLO size
        
        # Calculate scaling factors
        scale_x = target_w / orig_w
        scale_y = target_h / orig_h
        
        # Resize image to target size
        resized = cv2.resize(image, (target_w, target_h))
        
        # Convert BGR to RGB
        resized = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        
        # Normalize to [0, 1] and convert to float32
        resized = resized.astype(np.float32) / 255.0
        
        # Transpose to NCHW format if needed
        if len(self.input_shape) == 4 and self.input_shape[1] == 3:
            resized = np.transpose(resized, (2, 0, 1))
        
        # Add batch dimension
        resized = np.expand_dims(resized, axis=0)
        
        return resized, scale_x, scale_y
    
    def postprocess_detections(self, outputs: List[np.ndarray], scale_x: float, scale_y: float, 
                              orig_shape: Tuple[int, int]) -> List[Detection]:
        """
        Postprocess model outputs to detection objects.
        
        Args:
            outputs: Raw model outputs
            scale_x: X scaling factor from preprocessing
            scale_y: Y scaling factor from preprocessing
            orig_shape: Original image shape (height, width)
            
        Returns:
            List of Detection objects
        """
        detections = []
        orig_h, orig_w = orig_shape
        
        # Handle different output formats
        if len(outputs) == 1:
            output = outputs[0]
            
            # YOLOv8/v11 format: [batch, detections, 84] where 84 = 4 bbox + 80 classes
            if len(output.shape) == 3:
                output = output[0]  # Remove batch dimension
                
                # Extract bbox coordinates and class scores
                boxes = output[:, :4]  # [x, y, w, h] or [x1, y1, x2, y2]
                scores = output[:, 4:]  # Class scores
                
                # Get class predictions and max scores
                class_scores = np.max(scores, axis=1)
                class_indices = np.argmax(scores, axis=1)
                
                # Filter by confidence threshold
                valid_mask = class_scores > self.conf_threshold
                
                if np.sum(valid_mask) > 0:
                    valid_boxes = boxes[valid_mask]
                    valid_scores = class_scores[valid_mask]
                    valid_classes = class_indices[valid_mask]
                    
                    # Convert format if needed
                    if valid_boxes.shape[1] == 4:  # [x, y, w, h] format
                        # Convert center format to corner format
                        cx, cy, w, h = valid_boxes.T
                        x1 = cx - w / 2
                        y1 = cy - h / 2
                        x2 = cx + w / 2
                        y2 = cy + h / 2
                        corner_boxes = np.column_stack([x1, y1, x2, y2])
                    else:
                        corner_boxes = valid_boxes
                    
                    # Scale coordinates back to original image size
                    corner_boxes[:, 0] /= scale_x  # x1
                    corner_boxes[:, 1] /= scale_y  # y1
                    corner_boxes[:, 2] /= scale_x  # x2
                    corner_boxes[:, 3] /= scale_y  # y2
                    
                    # Apply Non-Maximum Suppression
                    indices = cv2.dnn.NMSBoxes(
                        corner_boxes.tolist(), 
                        valid_scores.tolist(), 
                        self.conf_threshold, 
                        self.iou_threshold
                    )
                    
                    if len(indices) > 0:
                        indices = indices.flatten()
                        
                        for idx in indices:
                            x1, y1, x2, y2 = corner_boxes[idx]
                            
                            # Clamp to image bounds
                            x1 = max(0, min(x1, orig_w - 1))
                            y1 = max(0, min(y1, orig_h - 1))
                            x2 = max(0, min(x2, orig_w - 1))
                            y2 = max(0, min(y2, orig_h - 1))
                            
                            # Normalize coordinates to [0, 1]
                            x1_norm = x1 / orig_w
                            y1_norm = y1 / orig_h
                            x2_norm = x2 / orig_w
                            y2_norm = y2 / orig_h
                            
                            class_idx = valid_classes[idx]
                            if class_idx < len(self.COCO_CLASSES):
                                class_name = self.COCO_CLASSES[class_idx]
                                confidence = float(valid_scores[idx])
                                
                                detection = Detection(
                                    class_name=class_name,
                                    confidence=confidence,
                                    bbox=[x1_norm, y1_norm, x2_norm, y2_norm]
                                )
                                detections.append(detection)
        
        return detections
    
    def detect(self, image: np.ndarray) -> Tuple[List[Detection], float]:
        """
        Run object detection on an image.
        
        Args:
            image: Input image in BGR format
            
        Returns:
            detections: List of Detection objects
            inference_time: Time taken for inference in seconds
        """
        # Preprocess
        preprocessed, scale_x, scale_y = self.preprocess_image(image)
        
        # Run inference
        start_time = time.time()
        outputs = self.session.run(self.output_names, {self.input_name: preprocessed})
        inference_time = time.time() - start_time
        
        # Postprocess
        detections = self.postprocess_detections(outputs, scale_x, scale_y, image.shape[:2])
        
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
        
        return {
            'avg_inference_time_ms': avg_inference_time * 1000,
            'min_inference_time_ms': min_inference_time * 1000,
            'max_inference_time_ms': max_inference_time * 1000,
            'fps': fps,
            'total_frames': self.frame_count
        }

class RealTimeDetectionApp:
    """Real-time detection application with camera input."""
    
    def __init__(self, model_path: str, camera_id: int = 0, conf_threshold: float = 0.25, 
                 iou_threshold: float = 0.45):
        """
        Initialize real-time detection app.
        
        Args:
            model_path: Path to ONNX model
            camera_id: Camera device ID
            conf_threshold: Confidence threshold
            iou_threshold: IoU threshold
        """
        self.detector = ONNXYOLODetector(model_path, conf_threshold, iou_threshold)
        self.camera_id = camera_id
        self.running = False
        
        # Colors for different classes (BGR format)
        self.colors = self._generate_colors(len(self.detector.COCO_CLASSES))
    
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
            class_idx = self.detector.COCO_CLASSES.index(detection.class_name)
            color = self.colors[class_idx % len(self.colors)]
            
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
        """Run real-time detection."""
        # Initialize camera
        cap = cv2.VideoCapture(self.camera_id)
        
        if not cap.isOpened():
            logger.error(f"Failed to open camera {self.camera_id}")
            return
        
        # Set camera properties for better performance
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 640)
        cap.set(cv2.CAP_PROP_FPS, 30)
        
        logger.info("Starting real-time detection. Press 'q' to quit.")
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
            if show_stats and frame_count % 10 == 0:  # Update stats every 10 frames
                stats = self.detector.get_performance_stats()
                fps = stats.get('fps', 0)
                avg_time = stats.get('avg_inference_time_ms', 0)
                
                cv2.putText(result_frame, f"FPS: {fps:.1f}", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.putText(result_frame, f"Avg Time: {avg_time:.1f}ms", (10, 70),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.putText(result_frame, f"Detections: {len(detections)}", (10, 110),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            
            # Display frame
            cv2.imshow('Real-time Object Detection', result_frame)
            
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

def benchmark_models(model_dir: str = "models", num_frames: int = 100):
    """Benchmark all available ONNX models."""
    model_dir = Path(model_dir)
    onnx_models = list(model_dir.glob("*.onnx"))
    
    if not onnx_models:
        logger.error(f"No ONNX models found in {model_dir}")
        return
    
    logger.info(f"Found {len(onnx_models)} ONNX models")
    
    # Create test image
    test_image = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
    
    results = {}
    
    for model_path in onnx_models:
        logger.info(f"Benchmarking {model_path.name}...")
        
        try:
            detector = ONNXYOLODetector(str(model_path))
            
            # Warm up
            for _ in range(5):
                detector.detect(test_image)
            
            # Benchmark
            times = []
            for i in range(num_frames):
                _, inference_time = detector.detect(test_image)
                times.append(inference_time)
                
                if (i + 1) % 20 == 0:
                    logger.info(f"  Processed {i + 1}/{num_frames} frames")
            
            avg_time = np.mean(times) * 1000
            fps = 1.0 / np.mean(times)
            
            results[model_path.name] = {
                'avg_time_ms': avg_time,
                'fps': fps,
                'min_time_ms': np.min(times) * 1000,
                'max_time_ms': np.max(times) * 1000
            }
            
            logger.info(f"  ✓ {model_path.name}: {avg_time:.1f}ms avg, {fps:.1f} FPS")
            
        except Exception as e:
            logger.error(f"  ✗ Failed to benchmark {model_path.name}: {e}")
    
    # Print comparison
    logger.info("\n=== Benchmark Results ===")
    sorted_results = sorted(results.items(), key=lambda x: x[1]['avg_time_ms'])
    
    for model_name, stats in sorted_results:
        logger.info(f"{model_name:20} | {stats['avg_time_ms']:6.1f}ms | {stats['fps']:5.1f} FPS")

def main():
    parser = argparse.ArgumentParser(description="Real-time Object Detection with ONNX YOLO Models")
    parser.add_argument('--model', type=str, default='models/yolov8n.onnx',
                        help='Path to ONNX model file')
    parser.add_argument('--camera', type=int, default=0,
                        help='Camera device ID')
    parser.add_argument('--conf', type=float, default=0.25,
                        help='Confidence threshold')
    parser.add_argument('--iou', type=float, default=0.45,
                        help='IoU threshold for NMS')
    parser.add_argument('--benchmark', action='store_true',
                        help='Run benchmark instead of real-time detection')
    parser.add_argument('--benchmark-frames', type=int, default=100,
                        help='Number of frames for benchmark')
    parser.add_argument('--models-dir', type=str, default='models',
                        help='Directory containing ONNX models')
    
    args = parser.parse_args()
    
    if args.benchmark:
        benchmark_models(args.models_dir, args.benchmark_frames)
    else:
        if not Path(args.model).exists():
            logger.error(f"Model file not found: {args.model}")
            return
        
        app = RealTimeDetectionApp(
            model_path=args.model,
            camera_id=args.camera,
            conf_threshold=args.conf,
            iou_threshold=args.iou
        )
        app.run()

if __name__ == "__main__":
    main()
