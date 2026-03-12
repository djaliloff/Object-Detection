#!/usr/bin/env python3
"""
Camera Stream Optimizer
Optimizes camera capture and display for smooth streaming with minimal lag.
"""

import cv2
import time
import threading
import queue
import numpy as np
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class OptimizedCameraCapture:
    """Optimized camera capture for smooth streaming."""
    
    def __init__(self, camera_id: int = 0, target_fps: int = 60, buffer_size: int = 1):
        """
        Initialize optimized camera capture.
        
        Args:
            camera_id: Camera device ID
            target_fps: Target FPS for capture
            buffer_size: Frame buffer size (1 = minimal latency)
        """
        self.camera_id = camera_id
        self.target_fps = target_fps
        self.buffer_size = buffer_size
        
        self.cap = None
        self.running = False
        self.capture_thread = None
        self.frame_queue = queue.Queue(maxsize=buffer_size)
        
        # Performance metrics
        self.actual_fps = 0
        self.frame_count = 0
        self.last_fps_time = time.time()
        
    def start(self):
        """Start camera capture in separate thread."""
        self.cap = cv2.VideoCapture(self.camera_id)
        
        if not self.cap.isOpened():
            raise RuntimeError(f"Failed to open camera {self.camera_id}")
        
        # Optimize camera settings for low latency
        self._configure_camera()
        
        self.running = True
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()
        
        logger.info(f"Camera capture started: {self.camera_id} @ {self.target_fps} FPS")
    
    def _configure_camera(self):
        """Configure camera for optimal performance."""
        # Set resolution
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        
        # Set FPS
        self.cap.set(cv2.CAP_PROP_FPS, self.target_fps)
        
        # Minimize latency settings
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, self.buffer_size)
        self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)
        self.cap.set(cv2.CAP_PROP_AUTO_WB, 1)
        
        # Disable automatic exposure adjustments that cause lag
        self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)  # Manual exposure mode
        
        # Set optimal backend
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        
        logger.info("Camera optimized for low latency")
    
    def _capture_loop(self):
        """Main capture loop running in separate thread."""
        while self.running:
            ret, frame = self.cap.read()
            
            if not ret:
                logger.warning("Failed to capture frame")
                continue
            
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
    
    def get_frame(self) -> Optional[np.ndarray]:
        """Get latest frame (non-blocking)."""
        try:
            return self.frame_queue.get_nowait()
        except queue.Empty:
            return None
    
    def stop(self):
        """Stop camera capture."""
        self.running = False
        if self.capture_thread:
            self.capture_thread.join(timeout=1.0)
        if self.cap:
            self.cap.release()
        logger.info("Camera capture stopped")

class SmoothDisplay:
    """Optimized display for smooth streaming."""
    
    def __init__(self, window_name: str = "Smooth Stream", target_fps: int = 60):
        """
        Initialize smooth display.
        
        Args:
            window_name: Window name
            target_fps: Target display FPS
        """
        self.window_name = window_name
        self.target_fps = target_fps
        self.frame_time = 1.0 / target_fps
        
        # Performance tracking
        self.last_frame_time = 0
        self.actual_fps = 0
        self.frame_count = 0
        self.last_fps_time = time.time()
        
        # Create window
        cv2.namedWindow(self.window_name, cv2.WINDOW_AUTOSIZE)
        
    def show_frame(self, frame: np.ndarray) -> bool:
        """
        Show frame with FPS control.
        
        Args:
            frame: Frame to display
            
        Returns:
            True if should continue, False if quit requested
        """
        current_time = time.time()
        
        # FPS limiting for smooth display
        if self.last_frame_time > 0:
            elapsed = current_time - self.last_frame_time
            if elapsed < self.frame_time:
                time.sleep(self.frame_time - elapsed)
        
        # Show frame
        cv2.imshow(self.window_name, frame)
        
        # Handle input
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:  # q or ESC
            return False
        
        # Update FPS counter
        self.frame_count += 1
        if current_time - self.last_fps_time >= 1.0:
            self.actual_fps = self.frame_count / (current_time - self.last_fps_time)
            self.frame_count = 0
            self.last_fps_time = current_time
        
        self.last_frame_time = time.time()
        return True
    
    def get_fps(self) -> float:
        """Get actual display FPS."""
        return self.actual_fps
    
    def destroy(self):
        """Destroy display window."""
        cv2.destroyWindow(self.window_name)

class AdaptiveFrameSkipper:
    """Adaptive frame skipping based on performance."""
    
    def __init__(self, initial_skip: int = 0, max_skip: int = 3):
        """
        Initialize adaptive frame skipper.
        
        Args:
            initial_skip: Initial frame skip value
            max_skip: Maximum frame skip value
        """
        self.skip_count = initial_skip
        self.max_skip = max_skip
        self.current_frame = 0
        
        # Performance tracking
        self.processing_times = []
        self.target_processing_time = 1.0 / 60  # 60 FPS target
        
    def should_process(self) -> bool:
        """
        Check if current frame should be processed.
        
        Returns:
            True if frame should be processed, False if should skip
        """
        self.current_frame += 1
        return self.current_frame % (self.skip_count + 1) == 0
    
    def update_performance(self, processing_time: float):
        """
        Update performance metrics and adjust skip count.
        
        Args:
            processing_time: Time taken to process last frame
        """
        self.processing_times.append(processing_time)
        
        # Keep only recent times
        if len(self.processing_times) > 10:
            self.processing_times.pop(0)
        
        # Adjust skip count based on performance
        if len(self.processing_times) >= 5:
            avg_time = np.mean(self.processing_times)
            
            if avg_time > self.target_processing_time * 1.5:
                # Too slow, increase skip
                self.skip_count = min(self.skip_count + 1, self.max_skip)
                logger.info(f"Increasing frame skip to {self.skip_count}")
            elif avg_time < self.target_processing_time * 0.8:
                # Fast enough, decrease skip
                self.skip_count = max(self.skip_count - 1, 0)
                logger.info(f"Decreasing frame skip to {self.skip_count}")
    
    def get_skip_count(self) -> int:
        """Get current skip count."""
        return self.skip_count

def test_optimized_capture():
    """Test optimized camera capture."""
    logger.info("Testing optimized camera capture...")
    
    try:
        # Initialize components
        camera = OptimizedCameraCapture(camera_id=0, target_fps=60, buffer_size=1)
        display = SmoothDisplay("Optimized Capture Test", target_fps=60)
        
        # Start camera
        camera.start()
        
        # Test loop
        start_time = time.time()
        frame_count = 0
        
        while True:
            frame = camera.get_frame()
            if frame is None:
                continue
            
            # Add FPS overlay
            fps_text = f"Camera: {camera.actual_fps:.1f} FPS | Display: {display.get_fps():.1f} FPS"
            cv2.putText(frame, fps_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            
            # Show frame
            if not display.show_frame(frame):
                break
            
            frame_count += 1
            
            # Print stats every 5 seconds
            if frame_count % 300 == 0:
                elapsed = time.time() - start_time
                logger.info(f"Stats: Camera={camera.actual_fps:.1f} FPS, Display={display.get_fps():1f} FPS, "
                          f"Frames={frame_count}, Time={elapsed:.1f}s")
        
        # Cleanup
        camera.stop()
        display.destroy()
        
    except Exception as e:
        logger.error(f"Test failed: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_optimized_capture()
