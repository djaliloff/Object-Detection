import os
import json
import yaml
import time
import numpy as np
import cv2
import onnxruntime
import redis
import structlog
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import asyncio
from dotenv import load_dotenv
from ultralytics import YOLO

# Load environment variables from the root .env file
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

logger = structlog.get_logger()

@dataclass
class Detection:
    """Detection result from AI model."""
    class_name: str
    confidence: float
    bbox: List[float]  # [x1, y1, x2, y2]
    track_id: Optional[int] = None
    features: Optional[Dict[str, Any]] = None

@dataclass
class FrameData:
    """Frame data received from camera gateway."""
    camera_id: str
    frame_id: str
    timestamp: datetime
    modality: str  # rgb, thermal, rgb_t
    image_data: np.ndarray
    metadata: Dict[str, Any]

class ModelRegistry:
    """Registry for AI models with loading and inference capabilities."""
    
    def __init__(self, config_path: str = "model_registry.yaml"):
        self.config = self._load_config(config_path)
        self.models = {}
        self.session_options = self._create_session_options()
        self._load_models()
    
    def _load_config(self, config_path: str) -> Dict:
        """Load model configuration from YAML file."""
        try:
            with open(config_path, 'r') as f:
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
        """Load a single YOLO model via Ultralytics."""
        model_path = model_config.get('model_path')
        if not os.path.exists(model_path):
            logger.warning(f"Model file not found: {model_path}")
            return
        
        try:
            # Load native YOLOv8 torch model
            model = YOLO(model_path)
            
            self.models[model_name] = {
                'model': model,
                'config': model_config
            }
            
            logger.info(f"Loaded model: {model_name}")
            
        except Exception as e:
            logger.error(f"Failed to load model {model_name} from {model_path}: {e}")
            raise
    
    def get_model_for_modality(self, modality: str, camera_id: str = None) -> str:
        """Determine which model to use based on modality and camera. Forced to RGB only."""
        routing_config = self.config.get('routing', {})
        return routing_config.get('default_rgb_model', 'rgb_yolov8n')
    
    # Removed preprocess_image as Ultralytics handles preprocessing internally
    # def preprocess_image(self, image: np.ndarray, model_config: Dict) -> np.ndarray:
    #     """Preprocess image for model inference."""
    #     preprocessing = model_config.get('preprocessing', {})
        
    #     # Convert grayscale to RGB if needed (for thermal)
    #     if preprocessing.get('convert_grayscale_to_rgb', False):
    #         if len(image.shape) == 2:
    #             image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    #         elif image.shape[2] == 1:
    #             image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        
    #     # Resize image
    #     if preprocessing.get('resize', True):
    #         input_size = model_config.get('input_size', [640, 640])
    #         image = cv2.resize(image, (input_size[1], input_size[0]))
        
    #     # Normalize pixel values
    #     if preprocessing.get('normalize', True):
    #         image = image.astype(np.float32) / 255.0
        
    #     # Add padding to maintain aspect ratio
    #     if preprocessing.get('pad', True):
    #         h, w = image.shape[:2]
    #         input_size = model_config.get('input_size', [640, 640])
            
    #         # Calculate padding
    #         scale = min(input_size[0] / h, input_size[1] / w)
    #         new_h, new_w = int(h * scale), int(w * scale)
            
    #         # Resize with aspect ratio
    #         image = cv2.resize(image, (new_w, new_h))
            
    #         # Pad to input size
    #         pad_h = input_size[0] - new_h
    #         pad_w = input_size[1] - new_w
            
    #         image = cv2.copyMakeBorder(
    #             image, 
    #             pad_h // 2, pad_h - pad_h // 2,
    #             pad_w // 2, pad_w - pad_w // 2,
    #             cv2.BORDER_CONSTANT, value=(114, 114, 114)
    #         )
        
    #     # Convert to NCHW format
    #     if len(image.shape) == 3:
    #         image = np.transpose(image, (2, 0, 1))
        
    #     # Add batch dimension
    #     image = np.expand_dims(image, axis=0)
        
    #     return image
    
    # Removed postprocess_detections as Ultralytics handles postprocessing and NMS internally
    # def postprocess_detections(self, outputs: List[np.ndarray], model_config: Dict, 
    #                           original_shape: Tuple[int, int]) -> List[Detection]:
    #     """Postprocess model outputs to detection objects."""
    #     postprocessing = model_config.get('postprocessing', {})
    #     confidence_threshold = postprocessing.get('confidence_threshold', 0.25)
    #     nms_threshold = postprocessing.get('nms_threshold', 0.45)
    #     max_detections = postprocessing.get('max_detections', 1000)
        
    #     # Get classes from config
    #     classes = model_config.get('classes', [])
        
    #     # Process YOLO output (assuming standard YOLOv8 format)
    #     detections = []
        
    #     if len(outputs) > 0:
    #         output = outputs[0]  # Take first output
            
    #         # YOLOv8 ONNX format is typically [batch, boxes+classes, num_anchors] -> [1, 84, 8400]
    #         if len(output.shape) == 3:
    #             # Transpose to [batch, num_anchors, boxes+classes] -> [1, 8400, 84]
    #             if output.shape[1] < output.shape[2]:
    #                 output = np.transpose(output, (0, 2, 1))
                    
    #             # Now output is [1, 8400, 84]
    #             # Filter by confidence max class prob
    #             class_probs = output[0, :, 4:]  # Class probabilities
    #             confidences = np.max(class_probs, axis=1)
                
    #             valid_mask = confidences > confidence_threshold
                
    #             if np.sum(valid_mask) > 0:
    #                 valid_boxes = output[0, valid_mask, :4]  # cx, cy, w, h
    #                 final_scores = confidences[valid_mask]
    #                 class_indices = np.argmax(class_probs[valid_mask], axis=1)
                    
    #                 # Convert cx, cy, w, h to x1, y1, x2, y2
    #                 boxes = np.zeros_like(valid_boxes)
    #                 boxes[:, 0] = valid_boxes[:, 0] - valid_boxes[:, 2] / 2  # x1
    #                 boxes[:, 1] = valid_boxes[:, 1] - valid_boxes[:, 3] / 2  # y1
    #                 boxes[:, 2] = valid_boxes[:, 0] + valid_boxes[:, 2] / 2  # x2
    #                 boxes[:, 3] = valid_boxes[:, 1] + valid_boxes[:, 3] / 2  # y2
                    
    #                 # Apply Non-Maximum Suppression
    #                 if len(boxes) > 0:
    #                     indices = cv2.dnn.NMSBoxes(
    #                         boxes.tolist(), final_scores.tolist(), 
    #                         confidence_threshold, nms_threshold
    #                     )
                        
    #                     if len(indices) > 0:
    #                         indices = indices.flatten()
                            
    #                         # Scale boxes back to original image size
    #                         orig_h, orig_w = original_shape
    #                         input_size = model_config.get('input_size', [640, 640])
                            
    #                         scale_x = orig_w / input_size[1]
    #                         scale_y = orig_h / input_size[0]
                            
    #                         for idx in indices[:max_detections]:
    #                             box = boxes[idx]
    #                             x1, y1, x2, y2 = box
                                
    #                             # Scale to original coordinates
    #                             x1 = x1 * scale_x
    #                             y1 = y1 * scale_y
    #                             x2 = x2 * scale_x
    #                             y2 = y2 * scale_y
                                
    #                             # Clamp to image bounds and normalize (0.0 to 1.0) for frontend
    #                             x1 = max(0.0, min(x1, orig_w - 1)) / orig_w
    #                             y1 = max(0.0, min(y1, orig_h - 1)) / orig_h
    #                             x2 = max(0.0, min(x2, orig_w - 1)) / orig_w
    #                             y2 = max(0.0, min(y2, orig_h - 1)) / orig_h
                                
    #                             class_idx = class_indices[idx]
    #                             if class_idx < len(classes):
    #                                 class_name = classes[class_idx]
    #                                 confidence = float(final_scores[idx])
                                    
    #                                 detection = Detection(
    #                                     class_name=class_name,
    #                                     confidence=confidence,
    #                                     bbox=[x1, y1, x2, y2]
    #                                 )
    #                                 detections.append(detection)
        
    #     return detections
    
    def run_inference(self, frame_data: FrameData) -> List[Detection]:
        """Run inference on a frame using Ultralytics YOLO and return normalized detections."""
        model_name = self.get_model_for_modality(frame_data.modality, frame_data.camera_id)
        
        if not model_name or model_name not in self.models:
            logger.warning(f"No model available for modality {frame_data.modality}")
            return []
        
        model_info = self.models[model_name]
        model = model_info['model']
        model_config = model_info['config']
        
        try:
            # Ultralytics native inference
            # We enforce standard NMS thresholds from our yaml config if present
            postprocessing = model_config.get('postprocessing', {})
            conf_thresh = postprocessing.get('confidence_threshold', 0.25)
            iou_thresh = postprocessing.get('nms_threshold', 0.45)
            
            image = frame_data.image_data
            
            results = model(image, conf=conf_thresh, iou=iou_thresh, verbose=False)
            
            detections = []
            orig_h, orig_w = image.shape[:2]
            
            for r in results:
                for box in r.boxes:
                    class_id = int(box.cls[0])
                    confidence = float(box.conf[0])
                    
                    # Convert pixel boundaries to 0.0-1.0 normalized strings
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    
                    x1_norm = max(0.0, min(x1, orig_w - 1)) / orig_w
                    y1_norm = max(0.0, min(y1, orig_h - 1)) / orig_h
                    x2_norm = max(0.0, min(x2, orig_w - 1)) / orig_w
                    y2_norm = max(0.0, min(y2, orig_h - 1)) / orig_h
                    
                    class_name = model.names[class_id]
                    
                    detection = Detection(
                        class_name=class_name,
                        confidence=confidence,
                        bbox=[x1_norm, y1_norm, x2_norm, y2_norm]
                    )
                    detections.append(detection)
                    
            logger.debug(f"Model {model_name} detected {len(detections)} objects")
            return detections
            
        except Exception as e:
            logger.error(f"Inference failed for model {model_name}: {e}")
            return []

class InferenceEngine:
    """Main inference engine that processes frames from Redis queue."""
    
    def __init__(self):
        self.model_registry = ModelRegistry()
        self.redis_client = self._connect_redis()
        self.running = False
        
        # Performance metrics
        self.stats = {
            'frames_processed': 0,
            'total_detections': 0,
            'avg_inference_time': 0.0,
            'start_time': time.time()
        }
    
    def _connect_redis(self) -> redis.Redis:
        """Connect to Redis for frame queue."""
        try:
            client = redis.Redis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                decode_responses=False  # We need binary data for images
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
            
            # Decode base64 image
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
    
    def _serialize_detections(self, detections: List[Detection], frame_data: FrameData) -> bytes:
        """Serialize detection results for Redis."""
        detection_list = []
        
        for detection in detections:
            detection_dict = {
                'class_name': detection.class_name,
                'confidence': detection.confidence,
                'bbox': detection.bbox,
                'track_id': detection.track_id,
                'features': detection.features
            }
            detection_list.append(detection_dict)
        
        result = {
            'camera_id': frame_data.camera_id,
            'frame_id': frame_data.frame_id,
            'timestamp': frame_data.timestamp.isoformat(),
            'modality': frame_data.modality,
            'detections': detection_list,
            'inference_time': time.time()
        }
        
        return json.dumps(result).encode('utf-8')
    
    def _update_stats(self, inference_time: float, detection_count: int):
        """Update performance statistics."""
        self.stats['frames_processed'] += 1
        self.stats['total_detections'] += detection_count
        
        # Update average inference time
        total_frames = self.stats['frames_processed']
        current_avg = self.stats['avg_inference_time']
        self.stats['avg_inference_time'] = (
            (current_avg * (total_frames - 1) + inference_time) / total_frames
        )
    
    async def process_frames(self):
        """Main processing loop for frames from Redis queue."""
        self.running = True
        logger.info("Inference engine started")
        
        while self.running:
            try:
                # Get frame from queue
                frame_data = self.redis_client.lpop('frame_queue')
                if frame_data is None:
                    await asyncio.sleep(0.01)  # Small delay if no frames
                    continue
                
                # Deserialize frame
                frame = self._deserialize_frame(frame_data)
                
                # Run inference
                start_time = time.time()
                detections = self.model_registry.run_inference(frame)
                inference_time = time.time() - start_time
                
                # Update stats
                self._update_stats(inference_time, len(detections))
                
                # Serialize and publish results
                detection_data = self._serialize_detections(detections, frame)
                
                # Send to detection queue for event processor
                self.redis_client.rpush('detection_queue', detection_data)
                
                # Also publish to WebSocket clients
                self.redis_client.publish('surveillance_detections', detection_data)
                
                logger.debug(f"Processed frame {frame.frame_id} in {inference_time:.3f}s")
                
            except Exception as e:
                import traceback
                logger.error(f"Error processing frame: {e}\\n{traceback.format_exc()}")
                await asyncio.sleep(0.1)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current performance statistics."""
        uptime = time.time() - self.stats['start_time']
        fps = self.stats['frames_processed'] / uptime if uptime > 0 else 0
        
        return {
            'frames_processed': self.stats['frames_processed'],
            'total_detections': self.stats['total_detections'],
            'avg_inference_time': self.stats['avg_inference_time'],
            'fps': fps,
            'uptime_seconds': uptime,
            'models_loaded': len(self.model_registry.models)
        }
    
    async def start(self):
        """Start the inference engine."""
        await self.process_frames()
    
    def stop(self):
        """Stop the inference engine."""
        self.running = False
        logger.info("Inference engine stopped")

if __name__ == "__main__":
    engine = InferenceEngine()
    
    try:
        asyncio.run(engine.start())
    except KeyboardInterrupt:
        engine.stop()
        logger.info("Inference engine stopped by user")
