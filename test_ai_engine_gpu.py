#!/usr/bin/env python3
"""
AI Engine GPU Integration Test
Tests the GPU-accelerated YOLOv8n model integration in the surveillance platform.
"""

import sys
import os
import time
import numpy as np
import cv2
from pathlib import Path
import logging

# Add the ai-engine directory to the path
ai_engine_path = Path(__file__).parent / "ai-engine"
sys.path.insert(0, str(ai_engine_path))

try:
    from inference import ModelRegistry, InferenceEngine, FrameData, Detection
except ImportError:
    print("Error: Could not import from ai-engine.inference")
    print("Make sure the ai-engine directory exists and contains inference.py")
    sys.exit(1)

from datetime import datetime
import json
import base64

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_test_frame(width: int = 640, height: int = 640) -> np.ndarray:
    """Create a test frame with random data."""
    return np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)

def create_frame_data(camera_id: str = "test_camera") -> FrameData:
    """Create test frame data for inference."""
    image = create_test_frame()
    
    return FrameData(
        camera_id=camera_id,
        frame_id=f"frame_{int(time.time())}",
        timestamp=datetime.now(),
        modality="rgb",
        image_data=image,
        metadata={"test": True}
    )

def serialize_frame_for_redis(frame_data: FrameData) -> bytes:
    """Serialize frame data as it would be sent from camera gateway."""
    # Encode image to base64
    _, buffer = cv2.imencode('.jpg', frame_data.image_data)
    image_bytes = buffer.tobytes()
    image_base64 = base64.b64encode(image_bytes).decode('utf-8')
    
    data = {
        'camera_id': frame_data.camera_id,
        'frame_id': frame_data.frame_id,
        'timestamp': frame_data.timestamp.isoformat(),
        'modality': frame_data.modality,
        'image_data': image_base64,
        'metadata': frame_data.metadata
    }
    
    return json.dumps(data).encode('utf-8')

def test_model_registry():
    """Test the model registry with GPU support."""
    logger.info("=== Testing Model Registry ===")
    
    try:
        registry = ModelRegistry()
        
        logger.info(f"Device: {registry.device}")
        logger.info(f"Models loaded: {list(registry.models.keys())}")
        
        # Test model selection
        model_name = registry.get_model_for_modality("rgb", "test_camera")
        logger.info(f"Selected model for RGB: {model_name}")
        
        if model_name in registry.models:
            model_info = registry.models[model_name]
            logger.info(f"Model device: {model_info['device']}")
            logger.info(f"Model config: {model_info['config']['name']}")
        
        return registry
        
    except Exception as e:
        logger.error(f"Model registry test failed: {e}")
        return None

def test_inference_performance(registry: ModelRegistry, num_frames: int = 10):
    """Test inference performance."""
    logger.info(f"=== Testing Inference Performance ({num_frames} frames) ===")
    
    try:
        # Get model
        model_name = registry.get_model_for_modality("rgb", "test_camera")
        
        if model_name not in registry.models:
            logger.error(f"Model {model_name} not found")
            return
        
        # Run inference test
        times = []
        detection_counts = []
        
        for i in range(num_frames):
            frame_data = create_frame_data()
            
            start_time = time.time()
            detections = registry.run_inference(frame_data)
            inference_time = time.time() - start_time
            
            times.append(inference_time)
            detection_counts.append(len(detections))
            
            if i == 0:
                logger.info(f"First frame: {inference_time*1000:.1f}ms, {len(detections)} detections")
        
        avg_time = np.mean(times) * 1000
        min_time = np.min(times) * 1000
        max_time = np.max(times) * 1000
        fps = 1.0 / np.mean(times)
        avg_detections = np.mean(detection_counts)
        
        logger.info(f"Performance Results:")
        logger.info(f"  Average time: {avg_time:.1f}ms")
        logger.info(f"  Min time: {min_time:.1f}ms")
        logger.info(f"  Max time: {max_time:.1f}ms")
        logger.info(f"  FPS: {fps:.1f}")
        logger.info(f"  Average detections: {avg_detections:.1f}")
        
        return {
            'avg_time_ms': avg_time,
            'fps': fps,
            'avg_detections': avg_detections
        }
        
    except Exception as e:
        logger.error(f"Inference performance test failed: {e}")
        return None

def test_ai_engine_integration():
    """Test the full AI engine integration."""
    logger.info("=== Testing AI Engine Integration ===")
    
    try:
        engine = InferenceEngine()
        
        # Get initial stats
        initial_stats = engine.get_stats()
        logger.info(f"Engine stats: {initial_stats}")
        
        # Test with a few frames
        test_frames = 5
        for i in range(test_frames):
            frame_data = create_frame_data(f"test_camera_{i}")
            detections = engine.model_registry.run_inference(frame_data)
            logger.info(f"Frame {i+1}: {len(detections)} detections")
        
        # Final stats
        final_stats = engine.get_stats()
        logger.info(f"Final engine stats: {final_stats}")
        
        return engine
        
    except Exception as e:
        logger.error(f"AI engine integration test failed: {e}")
        return None

def main():
    """Main test function."""
    logger.info("🚀 Starting AI Engine GPU Integration Test")
    logger.info("=" * 60)
    
    # Test 1: Model Registry
    registry = test_model_registry()
    if not registry:
        logger.error("❌ Model registry test failed")
        return
    
    logger.info("✅ Model registry test passed")
    
    # Test 2: Inference Performance
    performance_results = test_inference_performance(registry, num_frames=10)
    if not performance_results:
        logger.error("❌ Inference performance test failed")
        return
    
    logger.info("✅ Inference performance test passed")
    
    # Test 3: AI Engine Integration
    engine = test_ai_engine_integration()
    if not engine:
        logger.error("❌ AI engine integration test failed")
        return
    
    logger.info("✅ AI engine integration test passed")
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("🎉 ALL TESTS PASSED!")
    logger.info("=" * 60)
    logger.info(f"Performance Summary:")
    logger.info(f"  Device: {registry.device}")
    logger.info(f"  Inference Time: {performance_results['avg_time_ms']:.1f}ms")
    logger.info(f"  FPS: {performance_results['fps']:.1f}")
    logger.info(f"  GPU Accelerated: {'✅' if registry.device == 'cuda' else '❌'}")
    
    if registry.device == 'cuda':
        import torch
        gpu_name = torch.cuda.get_device_name(0)
        logger.info(f"  GPU: {gpu_name}")
        logger.info("🚀 GPU acceleration is working!")
    else:
        logger.info("🖥️ Running on CPU (GPU not available)")

if __name__ == "__main__":
    main()
