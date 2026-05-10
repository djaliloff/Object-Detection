#!/usr/bin/env python3
"""
Frontend Annotation Optimizer
Fixes annotation display delay with optimized rendering.
"""

import React, { useEffect, useRef, useState, useCallback } from 'react';
import { WebSocket } from 'ws';

// Optimized detection component for minimal rendering delay
const OptimizedDetectionOverlay = ({ cameraId, videoRef }) => {
  const canvasRef = useRef(null);
  const wsRef = useRef(null);
  const [detections, setDetections] = useState([]);
  const [performance, setPerformance] = useState({});
  const animationFrameRef = useRef(null);
  const lastRenderTime = useRef(0);

  // Optimized rendering with requestAnimationFrame
  const renderDetections = useCallback((detectionData) => {
    const canvas = canvasRef.current;
    const video = videoRef.current;
    
    if (!canvas || !video) return;

    const ctx = canvas.getContext('2d');
    const renderStartTime = performance.now();

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Set canvas size to match video
    if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
    }

    // Render detections with optimized drawing
    detectionData.detections.forEach((detection) => {
      const { bbox_pixel, color, label, class_name } = detection;
      const [x1, y1, x2, y2] = bbox_pixel;

      // Draw bounding box
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);

      // Draw label background
      ctx.fillStyle = color;
      const textWidth = ctx.measureText(label).width;
      ctx.fillRect(x1, y1 - 25, textWidth + 8, 25);

      // Draw label text
      ctx.fillStyle = '#FFFFFF';
      ctx.font = '14px Arial';
      ctx.fillText(label, x1 + 4, y1 - 8);
    });

    const renderTime = performance.now() - renderStartTime;
    lastRenderTime.current = renderTime;

    // Update performance metrics
    setPerformance({
      renderTime: renderTime.toFixed(2),
      detectionCount: detectionData.detections.length,
      fps: (1000 / renderTime).toFixed(1)
    });
  }, []);

  // WebSocket connection with optimized message handling
  useEffect(() => {
    const connectWebSocket = () => {
      wsRef.current = new WebSocket('ws://localhost:8000/ws');

      wsRef.current.onopen = () => {
        console.log('WebSocket connected for optimized detections');
      };

      wsRef.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          // Handle both old and new formats
          if (data.type === 'detection_update') {
            // New optimized format
            renderDetections(data);
          } else if (data.camera_id === cameraId) {
            // Legacy format - convert to optimized format
            const optimizedData = convertLegacyFormat(data);
            renderDetections(optimizedData);
          }
        } catch (error) {
          console.error('Error parsing detection data:', error);
        }
      };

      wsRef.current.onclose = () => {
        console.log('WebSocket disconnected, reconnecting...');
        setTimeout(connectWebSocket, 1000);
      };

      wsRef.current.onerror = (error) => {
        console.error('WebSocket error:', error);
      };
    };

    connectWebSocket();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [cameraId, renderDetections]);

  // Convert legacy format to optimized format
  const convertLegacyFormat = (legacyData) => {
    const detections = legacyData.detections.map((detection, index) => {
      const bbox = detection.bbox; // Assuming normalized [x1, y1, x2, y2]
      
      // Convert to pixel coordinates (assuming 1280x720)
      const x1 = Math.round(bbox[0] * 1280);
      const y1 = Math.round(bbox[1] * 720);
      const x2 = Math.round(bbox[2] * 1280);
      const y2 = Math.round(bbox[3] * 720);

      return {
        id: `${legacyData.camera_id}_${index}`,
        class_name: detection.class_name,
        confidence: detection.confidence,
        bbox_norm: bbox,
        bbox_pixel: [x1, y1, x2, y2],
        center: {
          x: x1 + (x2 - x1) // 2,
          y: y1 + (y2 - y1) // 2
        },
        size: {
          width: x2 - x1,
          height: y2 - y1
        },
        color: getClassColor(detection.class_name),
        label: `${detection.class_name} ${detection.confidence.toFixed(2)}`
      };
    });

    return {
      type: 'detection_update',
      camera_id: legacyData.camera_id,
      frame_id: legacyData.frame_id,
      detections: detections,
      frame_info: {
        width: 1280,
        height: 720,
        total_detections: detections.length
      }
    };
  };

  // Get class color (same as backend)
  const getClassColor = (className) => {
    const colorMap = {
      'person': '#FF6B6B',
      'car': '#4CAF50',
      'truck': '#FF9800',
      'bicycle': '#2196F3',
      'motorcycle': '#795548',
      'bus': '#9C27B0',
      'dog': '#F44336',
      'cat': '#E91E63',
      'chair': '#9E9E9E',
      'bottle': '#00BCD4',
      'cell phone': '#9C27B0',
      'laptop': '#607D8B',
      'tv': '#795548'
    };
    return colorMap[className] || '#FFEB3B';
  };

  return (
    <div className="detection-overlay">
      <canvas
        ref={canvasRef}
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          zIndex: 10,
          pointerEvents: 'none'
        }}
      />
      
      {/* Performance overlay */}
      <div
        style={{
          position: 'absolute',
          top: 10,
          right: 10,
          background: 'rgba(0,0,0,0.7)',
          color: 'white',
          padding: '8px',
          borderRadius: '4px',
          fontSize: '12px',
          zIndex: 20
        }}
      >
        <div>Render: {performance.renderTime}ms</div>
        <div>Detections: {performance.detectionCount}</div>
        <div>FPS: {performance.fps}</div>
      </div>
    </div>
  );
};

export default OptimizedDetectionOverlay;

// Usage example in your camera component:
/*
import OptimizedDetectionOverlay from './OptimizedDetectionOverlay';

const CameraView = ({ cameraId }) => {
  const videoRef = useRef(null);

  return (
    <div className="camera-container">
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        style={{ width: '100%', height: 'auto' }}
      />
      <OptimizedDetectionOverlay 
        cameraId={cameraId} 
        videoRef={videoRef} 
      />
    </div>
  );
};
*/
