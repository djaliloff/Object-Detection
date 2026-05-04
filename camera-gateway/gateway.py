import os
import json
import time
import asyncio
import threading
import base64
import numpy as np
import cv2
import redis
import structlog
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
from abc import ABC, abstractmethod
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables from the root .env file
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

logger = structlog.get_logger()

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
    modality: str = "rgb"  # rgb, thermal, rgb_t
    fps_target: int = 30
    enabled: bool = True
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
    
    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the camera."""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """Disconnect from the camera."""
        pass
    
    @abstractmethod
    async def get_frame(self) -> tuple[np.ndarray, FrameMetadata]:
        """Get a frame from the camera."""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if camera is connected."""
        pass

class RTSPCameraAdapter(CameraAdapter):
    """RTSP camera adapter using OpenCV."""
    
    def __init__(self, config: CameraConfig):
        self.config = config
        self.cap = None
        self.frame_count = 0
        self.last_frame_time = time.time()
        self.connection_attempts = 0
        self.max_connection_attempts = 5
        self.reconnect_delay = 5  # seconds
    
    async def connect(self) -> bool:
        """Connect to RTSP camera."""
        try:
            # Build RTSP URL with credentials if provided
            rtsp_url = self.config.rtsp_url
            if self.config.username and self.config.password:
                # Insert credentials into URL
                if "://" in rtsp_url:
                    protocol, rest = rtsp_url.split("://", 1)
                    rtsp_url = f"{protocol}://{self.config.username}:{self.config.password}@{rest}"
            
            # Bypass GStreamer pipeline entirely for direct HTTP streams (like IP Webcam)
            if rtsp_url.startswith('http'):
                logger.info(f"Opening HTTP/MJPEG stream for camera {self.config.id}: {rtsp_url}")
                self.cap = cv2.VideoCapture(rtsp_url)
                # Set timeout for HTTP streams if supported by OpenCV version
                self.cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
            else:
                try:
                    # Try GStreamer pipeline first for RTSP
                    logger.info(f"Attempting GStreamer for RTSP camera {self.config.id}")
                    pipeline = f"rtspsrc location={rtsp_url} latency=100 ! rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! appsink"
                    self.cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
                    
                    if not self.cap.isOpened():
                        logger.info(f"GStreamer failed, falling back to FFmpeg/Direct for camera {self.config.id}")
                        self.cap = cv2.VideoCapture(rtsp_url)
                except Exception as e:
                    logger.warning(f"GStreamer initialization error: {e}, falling back to standard OpenCV")
                    self.cap = cv2.VideoCapture(rtsp_url)
            
            if not self.cap.isOpened():
                logger.error(f"[ERROR] Failed to open stream for camera {self.config.id}")
                return False
            
            # Test read a frame
            ret, frame = self.cap.read()
            if not ret or frame is None:
                logger.error(f"[ERROR] Connected but failed to read initial frame from camera {self.config.id}")
                self.cap.release()
                self.cap = None
                return False
            
            self.connection_attempts = 0
            logger.info(f"[SUCCESS] Successfully connected and validated camera {self.config.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to RTSP camera {self.config.id}: {e}")
            self.connection_attempts += 1
            return False
    
    async def disconnect(self):
        """Disconnect from RTSP camera."""
        if self.cap:
            self.cap.release()
            self.cap = None
        logger.info(f"Disconnected from RTSP camera {self.config.id}")
    
    async def get_frame(self) -> tuple[Optional[np.ndarray], Optional[FrameMetadata]]:
        """Get a frame from RTSP camera."""
        if not self.cap or not self.cap.isOpened():
            return None, None
        
        try:
            ret, frame = self.cap.read()
            if not ret or frame is None:
                logger.warning(f"Failed to read frame from camera {self.config.id}")
                return None, None
            
            self.frame_count += 1
            current_time = time.time()
            prev_time = getattr(self, 'last_frame_time', current_time - 0.033)
            delta = current_time - prev_time
            if delta <= 0:
                delta = 0.033  # fallback 30fps
            self.last_frame_time = current_time
            
            metadata = FrameMetadata(
                camera_id=self.config.id,
                frame_id=f"{self.config.id}_{int(current_time * 1000)}_{self.frame_count}",
                timestamp=datetime.now(),
                modality=self.config.modality,
                resolution=frame.shape[:2],
                frame_number=self.frame_count,
                metadata={
                    'fps_actual': 1.0 / delta,
                    'connection_attempts': self.connection_attempts
                }
            )
            
            return frame, metadata
            
        except Exception as e:
            logger.error(f"Error getting frame from camera {self.config.id}: {e}")
            return None, None
    
    def is_connected(self) -> bool:
        """Check if RTSP camera is connected."""
        return self.cap is not None and self.cap.isOpened()

class ThermalCameraAdapter(CameraAdapter):
    """Thermal camera adapter for FLIR and other thermal cameras."""
    
    def __init__(self, config: CameraConfig):
        self.config = config
        self.sdk_client = None
        self.frame_count = 0
        
        # This would be implemented with specific thermal camera SDKs
        # For now, we'll use a placeholder implementation
        
    async def connect(self) -> bool:
        """Connect to thermal camera."""
        # Placeholder for thermal camera SDK connection
        # In real implementation, this would use FLIR Spinnaker SDK, Seek Thermal SDK, etc.
        logger.info(f"Thermal camera adapter for {self.config.id} (placeholder implementation)")
        return True
    
    async def disconnect(self):
        """Disconnect from thermal camera."""
        logger.info(f"Disconnected from thermal camera {self.config.id}")
    
    async def get_frame(self) -> tuple[Optional[np.ndarray], Optional[FrameMetadata]]:
        """Get a frame from thermal camera."""
        # Placeholder implementation
        # In real implementation, this would get frames from thermal SDK
        # For now, create a dummy thermal frame
        dummy_frame = np.random.randint(0, 256, (480, 640), dtype=np.uint8)
        
        self.frame_count += 1
        metadata = FrameMetadata(
            camera_id=self.config.id,
            frame_id=f"{self.config.id}_{int(time.time() * 1000)}_{self.frame_count}",
            timestamp=datetime.now(),
            modality=self.config.modality,
            resolution=dummy_frame.shape,
            frame_number=self.frame_count,
            metadata={'thermal_range': [0, 255]}
        )
        
        return dummy_frame, metadata
    
    def is_connected(self) -> bool:
        """Check if thermal camera is connected."""
        return True  # Placeholder

class VideoFileCameraAdapter(CameraAdapter):
    """Camera adapter for looped video files."""
    
    def __init__(self, config: CameraConfig):
        self.config = config
        self.cap = None
        self.frame_count = 0
        self.last_frame_time = time.time()
    
    async def connect(self) -> bool:
        """Open video file."""
        try:
            video_path = self.config.rtsp_url
            if not os.path.exists(video_path):
                logger.error(f"Video file not found for camera {self.config.id}: {video_path}")
                return False
                
            self.cap = cv2.VideoCapture(video_path)
            if not self.cap.isOpened():
                logger.error(f"Failed to open video file for camera {self.config.id}")
                return False
                
            logger.info(f"Successfully opened video file for camera {self.config.id}")
            return True
        except Exception as e:
            logger.error(f"Error opening video file {self.config.id}: {e}")
            return False
            
    async def disconnect(self):
        """Close video file."""
        if self.cap:
            self.cap.release()
            self.cap = None
            
    async def get_frame(self) -> tuple[Optional[np.ndarray], Optional[FrameMetadata]]:
        """Get a frame from video file with looping."""
        if not self.cap or not self.cap.isOpened():
            return None, None
            
        try:
            ret, frame = self.cap.read()
            
            # Loop the video if we reach the end
            if not ret or frame is None:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
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

class CameraManager:
    """Manages multiple camera connections and frame capture."""
    
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
    
    def _connect_redis(self) -> redis.Redis:
        """Connect to Redis for publishing frames."""
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
    
    def add_camera(self, config: CameraConfig):
        """Add a camera to the manager."""
        self.camera_configs[config.id] = config
        
        # Create appropriate adapter based on modality
        if config.modality == "thermal":
            adapter = ThermalCameraAdapter(config)
        elif config.modality == "video":
            adapter = VideoFileCameraAdapter(config)
        else:
            adapter = RTSPCameraAdapter(config)
        
        self.cameras[config.id] = adapter
        
        # Initialize stats
        self.stats['frames_per_camera'][config.id] = 0
        self.stats['errors'][config.id] = 0
        self.stats['last_frame_time'][config.id] = None
        
        logger.info(f"Added camera {config.id} ({config.modality})")
    
    def remove_camera(self, camera_id: str):
        """Remove a camera from the manager."""
        if camera_id in self.cameras:
            asyncio.create_task(self.cameras[camera_id].disconnect())
            del self.cameras[camera_id]
            del self.camera_configs[camera_id]
            
            # Clean up stats
            self.stats['frames_per_camera'].pop(camera_id, None)
            self.stats['errors'].pop(camera_id, None)
            self.stats['last_frame_time'].pop(camera_id, None)
            
            logger.info(f"Removed camera {camera_id}")
    
    async def connect_camera(self, camera_id: str) -> bool:
        """Connect a specific camera."""
        if camera_id not in self.cameras:
            logger.error(f"Camera {camera_id} not found")
            return False
        
        adapter = self.cameras[camera_id]
        return await adapter.connect()
    
    async def disconnect_camera(self, camera_id: str):
        """Disconnect a specific camera."""
        if camera_id in self.cameras:
            await self.cameras[camera_id].disconnect()
    
    async def connect_all_cameras(self):
        """Connect all cameras."""
        for camera_id in self.cameras:
            await self.connect_camera(camera_id)
    
    async def disconnect_all_cameras(self):
        """Disconnect all cameras."""
        for camera_id in self.cameras:
            await self.disconnect_camera(camera_id)
    
    def _serialize_frame(self, frame: np.ndarray, metadata: FrameMetadata) -> bytes:
        """Serialize frame for Redis."""
        try:
            # Encode frame as JPEG
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            frame_bytes = buffer.tobytes()
            
            # Encode as base64
            frame_b64 = base64.b64encode(frame_bytes).decode('utf-8')
            
            # Create frame data
            frame_data = {
                'camera_id': metadata.camera_id,
                'frame_id': metadata.frame_id,
                'timestamp': metadata.timestamp.isoformat(),
                'modality': metadata.modality,
                'resolution': list(metadata.resolution),
                'frame_number': metadata.frame_number,
                'metadata': metadata.metadata,
                'image_data': frame_b64
            }
            
            return json.dumps(frame_data).encode('utf-8')
            
        except Exception as e:
            logger.error(f"Error serializing frame: {e}")
            return b""
    
    async def _capture_camera_frames(self, camera_id: str):
        """Capture frames from a specific camera."""
        adapter = self.cameras[camera_id]
        config = self.camera_configs[camera_id]
        
        while self.running and config.enabled:
            try:
                # Check if camera is connected
                if not adapter.is_connected():
                    logger.warning(f"Camera {camera_id} disconnected, attempting reconnect")
                    if not await adapter.connect():
                        await asyncio.sleep(5.0)
                        continue
                
                # Get frame
                frame, metadata = await adapter.get_frame()
                
                if frame is None or metadata is None:
                    self.stats['errors'][camera_id] += 1
                    await asyncio.sleep(0.1)
                    continue
                
                # Update stats
                self.stats['total_frames'] += 1
                self.stats['frames_per_camera'][camera_id] += 1
                self.stats['last_frame_time'][camera_id] = datetime.now()
                
                # Serialize and publish frame
                frame_data = self._serialize_frame(frame, metadata)
                if frame_data:
                    self.redis_client.rpush('frame_queue', frame_data)
                
                # Rate limiting based on target FPS
                frame_time = 1.0 / config.fps_target
                await asyncio.sleep(frame_time)
                
            except Exception as e:
                logger.error(f"Error capturing frames from camera {camera_id}: {e}")
                self.stats['errors'][camera_id] += 1
                await asyncio.sleep(1.0)
    
    async def start_capture(self):
        """Start frame capture from all cameras."""
        self.running = True
        
        # Connect all cameras first
        await self.connect_all_cameras()
        
        # Start capture tasks for each camera
        tasks = []
        for camera_id in self.cameras:
            task = asyncio.create_task(self._capture_camera_frames(camera_id))
            tasks.append(task)
        
        logger.info(f"Started frame capture from {len(self.cameras)} cameras")
        
        # Wait for all tasks to complete (they won't unless stopped)
        await asyncio.gather(*tasks, return_exceptions=True)
    
    def stop_capture(self):
        """Stop frame capture."""
        self.running = False
        logger.info("Stopping frame capture")
    
    def get_stats(self) -> Dict[str, any]:
        """Get camera manager statistics."""
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
        """Discover ONVIF cameras on the network."""
        discovered = []
        
        try:
            from onvif import ONVIFCamera
            
            # Common IP ranges to scan (simplified)
            # In production, you'd want to use proper network discovery
            ip_ranges = ['192.168.1.', '192.168.0.', '10.0.0.']
            
            for prefix in ip_ranges:
                for i in range(1, 255):
                    ip = f"{prefix}{i}"
                    try:
                        # Try to connect to ONVIF service
                        cam = ONVIFCamera(ip, 80, 'admin', 'admin')
                        if cam:
                            # Get device info
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
                        continue  # Camera not found or not accessible
                    
                    # Small delay to avoid overwhelming the network
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
    
    async def start(self):
        """Start the camera gateway service."""
        self.running = True
        logger.info("Camera gateway service started")
        
        # Start camera capture
        await self.camera_manager.start_capture()
    
    def stop(self):
        """Stop the camera gateway service."""
        self.running = False
        self.camera_manager.stop_capture()
        logger.info("Camera gateway service stopped")
    
    def get_stats(self) -> Dict[str, any]:
        """Get gateway statistics."""
        return {
            'camera_manager': self.camera_manager.get_stats(),
            'discovered_cameras': len(self.onvif_discovery.discovered_cameras)
        }

if __name__ == "__main__":
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import uuid
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend-api"))

    # Setup database connection
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/surveillance")
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Example usage
    gateway = CameraGateway()
    
    # Load cameras from database
    db = SessionLocal()
    try:
        from models import Camera
        cameras = db.query(Camera).filter(Camera.status == 'online').all()
        for c in cameras:
            # For MJPEG streams, prioritize the mjpeg parameter if available in the database config block
            rtsp = c.rtsp_url
            if c.config_json and "stream_url" in c.config_json:
                rtsp = c.config_json["stream_url"]

            config = CameraConfig(
                id=str(c.id),
                name=c.name,
                ip=c.ip,
                port=c.port,
                rtsp_url=rtsp,
                username=None,
                password=None,
                modality=c.modality,
                fps_target=c.fps or 15,
                enabled=c.is_active if c.is_active is not None else True,
                mjpeg_url=c.mjpeg_url,
                hls_url=c.hls_url,
                stream_url=c.stream_url
            )
            gateway.camera_manager.add_camera(config)
            logger.info(f"Loaded database camera: {config.name} at {config.rtsp_url}")
    except Exception as e:
        logger.error(f"Failed to load cameras from DB: {e}")
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
