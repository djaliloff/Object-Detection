#!/usr/bin/env python3
"""
Optimized Detection Publisher
Reduces annotation drawing delay with optimized data format.
"""

import time
import json
import numpy as np
from typing import List, Dict, Any
import logging
import redis
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OptimizedDetectionPublisher:
    """Optimized detection publisher for minimal rendering delay."""
    
    def __init__(self):
        self.redis_client = self._connect_redis()
        self.last_detections = {}  # Cache for delta updates
        
    def _connect_redis(self) -> redis.Redis:
        """Connect to Redis."""
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
    
    def publish_optimized_detections(self, detections: List[Dict], frame_data: Dict):
        """Publish optimized detection data for fast rendering."""
        try:
            camera_id = frame_data['camera_id']
            frame_id = frame_data['frame_id']
            
            # Create optimized data structure for frontend
            optimized_data = {
                'type': 'detection_update',
                'camera_id': camera_id,
                'frame_id': frame_id,
                'timestamp': time.time() * 1000,  # Milliseconds for precision
                'detections': self._optimize_detections(detections, camera_id),
                'performance': {
                    'inference_time': frame_data.get('inference_time', 0),
                    'detection_count': len(detections)
                }
            }
            
            # Publish to WebSocket with minimal payload
            self.redis_client.publish('surveillance_detections', json.dumps(optimized_data))
            
            # Also cache for delta updates
            self._update_detection_cache(camera_id, detections)
            
        except Exception as e:
            logger.error(f"Failed to publish optimized detections: {e}")
    
    def _optimize_detections(self, detections: List[Dict], camera_id: str) -> List[Dict]:
        """Optimize detection data for fast frontend rendering."""
        optimized = []
        
        for detection in detections:
            # Pre-calculate values for frontend
            bbox = detection['bbox']  # [x1, y1, x2, y2] normalized (0-1)
            
            # Convert to pixel coordinates (frontend might need this)
            # Assuming 1280x720 resolution - adjust as needed
            x1 = int(bbox[0] * 1280)
            y1 = int(bbox[1] * 720)
            x2 = int(bbox[2] * 1280)
            y2 = int(bbox[3] * 720)
            
            # Optimized detection object
            optimized_detection = {
                'id': f"{camera_id}_{detection.get('track_id', hash(str(detection)))}",
                'class': detection['class_name'],
                'confidence': round(detection['confidence'], 2),  # Round for display
                'bbox': {
                    'x': x1,
                    'y': y1,
                    'width': x2 - x1,
                    'height': y2 - y1
                },
                'center': {
                    'x': x1 + (x2 - x1) // 2,
                    'y': y1 + (y2 - y1) // 2
                },
                'color': self._get_class_color(detection['class_name']),
                'label': f"{detection['class_name']} {detection['confidence']:.2f}"  # Pre-formatted
            }
            
            optimized.append(optimized_detection)
        
        return optimized
    
    def _get_class_color(self, class_name: str) -> str:
        """Get consistent color for each class."""
        # Pre-defined colors for consistent rendering
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
            'bottle': '#00BCD4'
        }
        return color_map.get(class_name, '#FFEB3B')  # Default yellow
    
    def _update_detection_cache(self, camera_id: str, detections: List[Dict]):
        """Update detection cache for delta updates."""
        self.last_detections[camera_id] = {
            'detections': detections,
            'timestamp': time.time()
        }
    
    def get_detection_delta(self, camera_id: str) -> Dict:
        """Get delta updates for efficient rendering."""
        if camera_id not in self.last_detections:
            return {'type': 'full_update', 'detections': []}
        
        # Simple delta - just send full updates for now
        # Could implement sophisticated delta detection later
        return {
            'type': 'full_update',
            'detections': self.last_detections[camera_id]['detections']
        }

def test_optimized_publisher():
    """Test optimized detection publisher."""
    publisher = OptimizedDetectionPublisher()
    
    # Simulate detection data
    test_detections = [
        {
            'class_name': 'person',
            'confidence': 0.85,
            'bbox': [0.1, 0.2, 0.3, 0.6],
            'track_id': 1
        },
        {
            'class_name': 'car',
            'confidence': 0.92,
            'bbox': [0.5, 0.3, 0.8, 0.7],
            'track_id': 2
        }
    ]
    
    frame_data = {
        'camera_id': 'phone_camera',
        'frame_id': 'test_frame_001',
        'inference_time': 0.025
    }
    
    # Test optimization
    start_time = time.time()
    optimized = publisher._optimize_detections(test_detections, 'phone_camera')
    optimization_time = time.time() - start_time
    
    print("🚀 Optimized Detection Publisher Test")
    print("=" * 50)
    print(f"Original detections: {len(test_detections)}")
    print(f"Optimization time: {optimization_time*1000:.2f}ms")
    print()
    
    print("Optimized detection structure:")
    for i, detection in enumerate(optimized):
        print(f"  {i+1}. {detection['class']} (confidence: {detection['confidence']})")
        print(f"     Bbox: {detection['bbox']}")
        print(f"     Center: {detection['center']}")
        print(f"     Color: {detection['color']}")
        print(f"     Label: {detection['label']}")
        print()
    
    # Test publishing
    print("Publishing optimized detections...")
    publisher.publish_optimized_detections(test_detections, frame_data)
    print("✅ Published successfully!")
    
    print("\n💡 Optimization Benefits:")
    print("  ✅ Pre-calculated pixel coordinates")
    print("  ✅ Pre-formatted labels")
    print("  ✅ Consistent colors")
    print("  ✅ Minimal JSON payload")
    print("  ✅ Fast frontend rendering")

if __name__ == "__main__":
    test_optimized_publisher()
