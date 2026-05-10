#!/usr/bin/env python3
"""
Simple Camera Gateway for Testing
Streams frames from IP camera to AI engine.
"""

import cv2
import time
import threading
import queue
import requests
import json
import base64
import numpy as np
from typing import Optional
from datetime import datetime
import logging
import redis
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SimpleIPCameraGateway:
    """Simple IP camera gateway for testing."""
    
    def __init__(self, ip_address: str, port: int = 8080):
        self.ip_address = ip_address
        self.port = port
        self.stream_url = f"http://{ip_address}:{port}/video"
        
        self.cap = None
        self.running = False
        self.redis_client = None
        
        # Performance metrics
        self.frame_count = 0
        self.actual_fps = 0
        self.last_fps_time = time.time()
        
    def start(self):
        """Start camera streaming."""
        try:
            # Connect to Redis
            self.redis_client = redis.Redis(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                decode_responses=False
            )
            self.redis_client.ping()
            logger.info("Connected to Redis")
            
            # Connect to camera
            self.cap = cv2.VideoCapture(self.stream_url)
            if not self.cap.isOpened():
                raise RuntimeError(f"Failed to connect to camera: {self.stream_url}")
            
            # Configure camera
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            
            self.running = True
            self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.capture_thread.start()
            
            logger.info(f"Camera gateway started: {self.stream_url}")
            
        except Exception as e:
            logger.error(f"Failed to start camera gateway: {e}")
            raise
    
    def _capture_loop(self):
        """Main capture loop."""
        consecutive_errors = 0
        max_errors = 10
        
        while self.running:
            try:
                ret, frame = self.cap.read()
                
                if not ret:
                    consecutive_errors += 1
                    if consecutive_errors >= max_errors:
                        logger.error("Too many consecutive errors, stopping")
                        break
                    
                    logger.warning(f"Failed to capture frame (error {consecutive_errors}/{max_errors})")
                    time.sleep(0.1)
                    continue
                
                consecutive_errors = 0
                
                # Update FPS
                self.frame_count += 1
                current_time = time.time()
                if current_time - self.last_fps_time >= 1.0:
                    self.actual_fps = self.frame_count / (current_time - self.last_fps_time)
                    self.frame_count = 0
                    self.last_fps_time = current_time
                
                # Publish frame to Redis
                self._publish_frame(frame)
                
            except Exception as e:
                logger.error(f"Capture loop error: {e}")
                consecutive_errors += 1
                if consecutive_errors >= max_errors:
                    break
                time.sleep(0.1)
    
    def _publish_frame(self, frame: np.ndarray):
        """Publish frame to Redis."""
        try:
            # Encode frame to JPEG
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            frame_bytes = buffer.tobytes()
            
            # Create frame data
            frame_data = {
                'camera_id': 'phone_camera',
                'frame_id': f"phone_camera_{int(time.time() * 1000)}",
                'timestamp': datetime.now().isoformat(),
                'modality': 'rgb',
                'image_data': base64.b64encode(frame_bytes).decode('utf-8'),
                'metadata': {
                    'camera_type': 'ip',
                    'resolution': frame.shape[:2],
                    'fps': self.actual_fps
                }
            }
            
            # Publish to Redis
            self.redis_client.rpush('frame_queue', json.dumps(frame_data))
            
        except Exception as e:
            logger.error(f"Failed to publish frame: {e}")
    
    def stop(self):
        """Stop camera streaming."""
        self.running = False
        if self.capture_thread:
            self.capture_thread.join(timeout=1.0)
        if self.cap:
            self.cap.release()
        logger.info("Camera gateway stopped")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Simple IP Camera Gateway")
    parser.add_argument('--ip', type=str, required=True, help='IP address of phone')
    parser.add_argument('--port', type=int, default=8080, help='Port number')
    
    args = parser.parse_args()
    
    gateway = SimpleIPCameraGateway(args.ip, args.port)
    
    try:
        gateway.start()
        logger.info("Camera gateway running. Press Ctrl+C to stop.")
        
        while True:
            time.sleep(10)
            logger.info(f"Streaming: {gateway.actual_fps:.1f} FPS")
            
    except KeyboardInterrupt:
        logger.info("Stopping camera gateway...")
    finally:
        gateway.stop()

if __name__ == "__main__":
    main()
