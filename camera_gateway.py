#!/usr/bin/env python3
"""
Camera Gateway with IP Camera Support
Handles both USB cameras and IP cameras for the surveillance platform.
"""

import cv2
import time
import threading
import queue
import numpy as np
import requests
import json
import base64
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import logging
import redis
from pathlib import Path
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class CameraConfig:
    """Camera configuration."""
    camera_id: str
    camera_type: str  # "usb" or "ip"
    source: str  # device index for USB, URL for IP
    ip_address: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    resolution: tuple = (1280, 720)
    fps: int = 30
    buffer_size: int = 1

class CameraCapture:
    """Unified camera capture for USB and IP cameras."""
    
    def __init__(self, config: CameraConfig, redis_client: redis.Redis):
        """
        Initialize camera capture.
        
        Args:
            config: Camera configuration
            redis_client: Redis client for publishing frames
        """
        self.config = config
        self.redis_client = redis_client
        
        self.cap = None
        self.running = False
        self.capture_thread = None
        self.frame_count = 0
        self.last_fps_time = time.time()
        self.actual_fps = 0
        self.connection_errors = 0
        
        # Build stream URL for IP cameras
        self.stream_url = self._build_stream_url() if config.camera_type == "ip" else None
    
    def _build_stream_url(self) -> str:
        """Build the stream URL for IP camera."""
        if self.config.username and self.config.password:
            auth = f"{self.config.username}:{self.config.password}@"
        else:
            auth = ""
        
        return f"http://{auth}{self.config.ip_address}:{self.config.port}/video"
    
    def start(self):
        """Start camera capture in separate thread."""
        try:
            if self.config.camera_type == "usb":
                self._start_usb_camera()
            elif self.config.camera_type == "ip":
                self._start_ip_camera()
            else:
                raise ValueError(f"Unsupported camera type: {self.config.camera_type}")
            
            self.running = True
            self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.capture_thread.start()
            
            logger.info(f"Camera capture started: {self.config.camera_id} ({self.config.camera_type})")
            
        except Exception as e:
            logger.error(f"Failed to start camera {self.config.camera_id}: {e}")
            raise
    
    def _start_usb_camera(self):
        """Start USB camera capture."""
        self.cap = cv2.VideoCapture(int(self.config.source))
        
        if not self.cap.isOpened():
            raise RuntimeError(f"Failed to open USB camera {self.config.source}")
        
        # Configure USB camera
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.resolution[0])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.resolution[1])
        self.cap.set(cv2.CAP_PROP_FPS, self.config.fps)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, self.config.buffer_size)
        self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)
        self.cap.set(cv2.CAP_PROP_AUTO_WB, 1)
        
        logger.info(f"USB camera configured: {self.config.resolution} @ {self.config.fps} FPS")
    
    def _start_ip_camera(self):
        """Start IP camera capture."""
        try:
            # Test connection first
            self._test_connection()
            
            self.cap = cv2.VideoCapture(self.stream_url)
            
            if not self.cap.isOpened():
                raise RuntimeError(f"Failed to open IP camera stream: {self.stream_url}")
            
            # Configure IP camera
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, self.config.buffer_size)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.resolution[0])
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.resolution[1])
            self.cap.set(cv2.CAP_PROP_FPS, self.config.fps)
            
            logger.info(f"IP camera configured: {self.config.resolution} @ {self.config.fps} FPS")
            
        except Exception as e:
            logger.error(f"Failed to start IP camera: {e}")
            raise
    
    def _test_connection(self):
        """Test connection to IP camera."""
        try:
            test_url = f"http://{self.config.ip_address}:{self.config.port}/status.json"
            response = requests.get(test_url, timeout=5)
            if response.status_code == 200:
                logger.info(f"Successfully connected to IP camera at {self.config.ip_address}:{self.config.port}")
            else:
                logger.warning(f"IP camera returned status {response.status_code}")
        except Exception as e:
            logger.warning(f"Could not test IP camera connection: {e}")
    
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
                
                # Publish frame to Redis
                self._publish_frame(frame)
                
            except Exception as e:
                logger.error(f"Capture loop error: {e}")
                consecutive_errors += 1
                if consecutive_errors >= max_errors:
                    break
                time.sleep(0.1)
    
    def _publish_frame(self, frame: np.ndarray):
        """Publish frame to Redis for AI engine."""
        try:
            # Encode frame to JPEG
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            frame_bytes = buffer.tobytes()
            
            # Create frame data
            frame_data = {
                'camera_id': self.config.camera_id,
                'frame_id': f"{self.config.camera_id}_{int(time.time() * 1000)}",
                'timestamp': datetime.now().isoformat(),
                'modality': 'rgb',
                'image_data': base64.b64encode(frame_bytes).decode('utf-8'),
                'metadata': {
                    'camera_type': self.config.camera_type,
                    'resolution': self.config.resolution,
                    'fps': self.actual_fps,
                    'source': self.config.source
                }
            }
            
            # Publish to Redis frame queue
            self.redis_client.rpush('frame_queue', json.dumps(frame_data))
            
        except Exception as e:
            logger.error(f"Failed to publish frame: {e}")
    
    def stop(self):
        """Stop camera capture."""
        self.running = False
        if self.capture_thread:
            self.capture_thread.join(timeout=1.0)
        if self.cap:
            self.cap.release()
        logger.info(f"Camera capture stopped: {self.config.camera_id}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get camera statistics."""
        return {
            'camera_id': self.config.camera_id,
            'camera_type': self.config.camera_type,
            'actual_fps': self.actual_fps,
            'running': self.running,
            'connection_errors': self.connection_errors
        }

class CameraGateway:
    """Main camera gateway managing multiple cameras."""
    
    def __init__(self, config_file: str = "camera_config.json"):
        """
        Initialize camera gateway.
        
        Args:
            config_file: Path to camera configuration file
        """
        self.config_file = config_file
        self.cameras = {}
        self.redis_client = self._connect_redis()
        self.running = False
        
        # Load camera configurations
        self.camera_configs = self._load_camera_configs()
        
        logger.info(f"Camera gateway initialized with {len(self.camera_configs)} camera configurations")
    
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
    
    def _load_camera_configs(self) -> Dict[str, CameraConfig]:
        """Load camera configurations from file."""
        try:
            if not Path(self.config_file).exists():
                # Create default configuration
                default_configs = {
                    "camera_001": CameraConfig(
                        camera_id="camera_001",
                        camera_type="usb",
                        source="0",
                        resolution=(1280, 720),
                        fps=30
                    )
                }
                self._save_camera_configs(default_configs)
                return default_configs
            
            with open(self.config_file, 'r') as f:
                data = json.load(f)
            
            configs = {}
            for camera_id, config_data in data.items():
                configs[camera_id] = CameraConfig(**config_data)
            
            logger.info(f"Loaded {len(configs)} camera configurations")
            return configs
            
        except Exception as e:
            logger.error(f"Failed to load camera configs: {e}")
            return {}
    
    def _save_camera_configs(self, configs: Dict[str, CameraConfig]):
        """Save camera configurations to file."""
        try:
            data = {camera_id: asdict(config) for camera_id, config in configs.items()}
            with open(self.config_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved {len(configs)} camera configurations")
        except Exception as e:
            logger.error(f"Failed to save camera configs: {e}")
    
    def add_camera(self, config: CameraConfig):
        """Add a new camera configuration."""
        self.camera_configs[config.camera_id] = config
        self._save_camera_configs(self.camera_configs)
        logger.info(f"Added camera configuration: {config.camera_id}")
    
    def start(self):
        """Start all configured cameras."""
        self.running = True
        
        for camera_id, config in self.camera_configs.items():
            try:
                camera = CameraCapture(config, self.redis_client)
                camera.start()
                self.cameras[camera_id] = camera
                logger.info(f"Started camera: {camera_id}")
            except Exception as e:
                logger.error(f"Failed to start camera {camera_id}: {e}")
        
        logger.info(f"Camera gateway started with {len(self.cameras)} active cameras")
    
    def stop(self):
        """Stop all cameras."""
        self.running = False
        
        for camera_id, camera in self.cameras.items():
            try:
                camera.stop()
            except Exception as e:
                logger.error(f"Error stopping camera {camera_id}: {e}")
        
        self.cameras.clear()
        logger.info("Camera gateway stopped")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics for all cameras."""
        stats = {
            'gateway_running': self.running,
            'total_cameras': len(self.camera_configs),
            'active_cameras': len(self.cameras),
            'cameras': {}
        }
        
        for camera_id, camera in self.cameras.items():
            stats['cameras'][camera_id] = camera.get_stats()
        
        return stats

def main():
    """Main function for camera gateway."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Camera Gateway for Surveillance Platform")
    parser.add_argument('--config', type=str, default='camera_config.json',
                        help='Camera configuration file')
    parser.add_argument('--add-ip-camera', action='store_true',
                        help='Add an IP camera interactively')
    parser.add_argument('--camera-id', type=str,
                        help='Camera ID for new camera')
    parser.add_argument('--ip-address', type=str,
                        help='IP address for IP camera')
    parser.add_argument('--port', type=int, default=8080,
                        help='Port for IP camera')
    parser.add_argument('--username', type=str,
                        help='Username for IP camera')
    parser.add_argument('--password', type=str,
                        help='Password for IP camera')
    
    args = parser.parse_args()
    
    gateway = CameraGateway(args.config)
    
    if args.add_ip_camera:
        # Add IP camera interactively
        if not args.camera_id or not args.ip_address:
            logger.error("Camera ID and IP address are required for adding IP camera")
            return
        
        config = CameraConfig(
            camera_id=args.camera_id,
            camera_type="ip",
            source=f"http://{args.ip_address}:{args.port}/video",
            ip_address=args.ip_address,
            port=args.port,
            username=args.username,
            password=args.password
        )
        
        gateway.add_camera(config)
        logger.info(f"Added IP camera: {args.camera_id} -> {args.ip_address}:{args.port}")
        return
    
    # Start camera gateway
    try:
        gateway.start()
        
        # Keep running
        logger.info("Camera gateway running. Press Ctrl+C to stop.")
        while True:
            time.sleep(10)
            
            # Print stats periodically
            stats = gateway.get_stats()
            logger.info(f"Status: {stats['active_cameras']}/{stats['total_cameras']} cameras active")
            
            for camera_id, camera_stats in stats['cameras'].items():
                logger.info(f"  {camera_id}: {camera_stats['actual_fps']:.1f} FPS")
            
    except KeyboardInterrupt:
        logger.info("Stopping camera gateway...")
    finally:
        gateway.stop()

if __name__ == "__main__":
    main()
