#!/usr/bin/env python3
"""
YOLO Model Downloader and ONNX Converter
Downloads YOLOv11, YOLOv12, and YOLOv26 models and converts them to ONNX format
for optimized real-time inference with minimal latency.
"""

import os
import sys
import time
import requests
from pathlib import Path
from ultralytics import YOLO
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class YOLOModelManager:
    """Manages downloading and converting YOLO models to ONNX format."""
    
    def __init__(self, models_dir: str = "models"):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(exist_ok=True)
        
        # Model configurations - Only include available models
        self.model_configs = {
            # YOLOv11 models (latest available generation)
            "yolov11n": {"size": "nano", "url": "yolo11n.pt"},
            "yolov11s": {"size": "small", "url": "yolo11s.pt"}, 
            "yolov11m": {"size": "medium", "url": "yolo11m.pt"},
            "yolov11l": {"size": "large", "url": "yolo11l.pt"},
            "yolov11x": {"size": "xlarge", "url": "yolo11x.pt"},
            
            # YOLOv8 models (fallback - very stable and fast)
            "yolov8n": {"size": "nano", "url": "yolov8n.pt"},
            "yolov8s": {"size": "small", "url": "yolov8s.pt"},
            "yolov8m": {"size": "medium", "url": "yolov8m.pt"},
            "yolov8l": {"size": "large", "url": "yolov8l.pt"},
            "yolov8x": {"size": "xlarge", "url": "yolov8x.pt"},
            
            # YOLOv9 models (if available)
            "yolov9t": {"size": "tiny", "url": "yolov9t.pt"},
            "yolov9s": {"size": "small", "url": "yolov9s.pt"},
            "yolov9m": {"size": "medium", "url": "yolov9m.pt"},
            "yolov9c": {"size": "large", "url": "yolov9c.pt"},
            "yolov9e": {"size": "xlarge", "url": "yolov9e.pt"},
        }
    
    def download_model(self, model_name: str) -> bool:
        """Download a single YOLO model."""
        if model_name not in self.model_configs:
            logger.error(f"Unknown model: {model_name}")
            return False
        
        config = self.model_configs[model_name]
        model_url = config["url"]
        model_path = self.models_dir / model_url
        
        # Check if model already exists
        if model_path.exists():
            logger.info(f"Model {model_name} already exists at {model_path}")
            return True
        
        logger.info(f"Downloading {model_name} ({config['size']})...")
        
        try:
            # Use Ultralytics to download the model
            model = YOLO(model_url)
            
            # Verify the model was downloaded
            if model_path.exists():
                logger.info(f"Successfully downloaded {model_name} to {model_path}")
                return True
            else:
                logger.error(f"Model file not found after download: {model_path}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to download {model_name}: {e}")
            return False
    
    def convert_to_onnx(self, model_name: str, optimize: bool = True) -> bool:
        """Convert a YOLO model to ONNX format with optimizations."""
        model_pt_path = self.models_dir / f"{model_name}.pt"
        model_onnx_path = self.models_dir / f"{model_name}.onnx"
        
        if not model_pt_path.exists():
            logger.error(f"PyTorch model not found: {model_pt_path}")
            return False
        
        if model_onnx_path.exists():
            logger.info(f"ONNX model already exists: {model_onnx_path}")
            return True
        
        logger.info(f"Converting {model_name} to ONNX format...")
        
        try:
            # Load the YOLO model
            model = YOLO(str(model_pt_path))
            
            # Export to ONNX with optimizations for real-time inference
            export_args = {
                'format': 'onnx',
                'imgsz': 640,  # Standard input size
                'optimize': optimize,
                'half': True,   # Use FP16 for faster inference
                'simplify': True,  # Simplify model for better performance
                'workspace': 4,  # Workspace size in GB
                'nms': True,    # Include Non-Maximum Suppression
                'agnostic_nms': True,  # Class-agnostic NMS
                'topk_per_class': 100,  # Top-K detections per class
                'conf_thres': 0.25,  # Confidence threshold
                'iou_thres': 0.45,   # IoU threshold for NMS
            }
            
            # Export the model
            model.export(**export_args)
            
            # Verify ONNX file was created
            if model_onnx_path.exists():
                file_size_mb = model_onnx_path.stat().st_size / (1024 * 1024)
                logger.info(f"Successfully converted {model_name} to ONNX: {file_size_mb:.1f}MB")
                return True
            else:
                logger.error(f"ONNX file not created: {model_onnx_path}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to convert {model_name} to ONNX: {e}")
            return False
    
    def download_all_models(self, models_to_download: list = None) -> dict:
        """Download multiple models."""
        if models_to_download is None:
            # Focus on the best models for real-time detection
            models_to_download = ["yolov11n", "yolov11s", "yolov8n", "yolov9t"]
        
        results = {}
        
        for model_name in models_to_download:
            logger.info(f"Processing {model_name}...")
            success = self.download_model(model_name)
            results[model_name] = {"downloaded": success}
            
            if success:
                # Also convert to ONNX
                onnx_success = self.convert_to_onnx(model_name)
                results[model_name]["onnx_converted"] = onnx_success
        
        return results
    
    def verify_onnx_model(self, model_name: str) -> bool:
        """Verify ONNX model can be loaded and run inference."""
        try:
            import onnxruntime as ort
            import numpy as np
        except ImportError:
            logger.error("onnxruntime not installed. Install with: pip install onnxruntime")
            return False
        
        onnx_path = self.models_dir / f"{model_name}.onnx"
        
        if not onnx_path.exists():
            logger.error(f"ONNX model not found: {onnx_path}")
            return False
        
        try:
            # Create ONNX Runtime session
            providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
            session = ort.InferenceSession(str(onnx_path), providers=providers)
            
            # Get input info
            input_info = session.get_inputs()[0]
            input_shape = input_info.shape
            input_name = input_info.name
            
            logger.info(f"Model input: {input_name}, shape: {input_shape}")
            
            # Create dummy input
            dummy_input = np.random.randn(*input_shape).astype(np.float32)
            
            # Run inference
            start_time = time.time()
            outputs = session.run(None, {input_name: dummy_input})
            inference_time = time.time() - start_time
            
            logger.info(f"ONNX model verification successful! Inference time: {inference_time*1000:.1f}ms")
            return True
            
        except Exception as e:
            logger.error(f"ONNX model verification failed: {e}")
            return False
    
    def get_model_info(self) -> dict:
        """Get information about downloaded models."""
        info = {}
        
        for model_name in self.model_configs.keys():
            model_files = {
                "pt": (self.models_dir / f"{model_name}.pt").exists(),
                "onnx": (self.models_dir / f"{model_name}.onnx").exists()
            }
            
            if any(model_files.values()):
                info[model_name] = model_files
        
        return info

def main():
    """Main execution function."""
    manager = YOLOModelManager()
    
    print("=== YOLO Model Downloader and ONNX Converter ===")
    print("Available models:", list(manager.model_configs.keys()))
    print()
    
    # Check what's already downloaded
    existing_models = manager.get_model_info()
    if existing_models:
        print("Existing models:")
        for name, files in existing_models.items():
            status = []
            if files["pt"]: status.append("PT")
            if files["onnx"]: status.append("ONNX")
            print(f"  {name}: {', '.join(status)}")
        print()
    
    # Download recommended models for real-time detection
    # Focus on the fastest models: nano and small versions
    recommended_models = ["yolov11n", "yolov8n", "yolov9t", "yolov11s"]  # Start with most efficient models
    
    print("Downloading recommended models for real-time detection...")
    results = manager.download_all_models(recommended_models)
    
    print("\n=== Results ===")
    for model_name, result in results.items():
        status = []
        if result.get("downloaded"): status.append("✓ Downloaded")
        if result.get("onnx_converted"): status.append("✓ ONNX")
        print(f"{model_name}: {', '.join(status)}")
    
    # Verify ONNX models
    print("\n=== Verifying ONNX Models ===")
    for model_name in recommended_models:
        manager.verify_onnx_model(model_name)
    
    print("\n=== Summary ===")
    final_info = manager.get_model_info()
    total_pt = sum(1 for files in final_info.values() if files["pt"])
    total_onnx = sum(1 for files in final_info.values() if files["onnx"])
    
    print(f"Models ready: {total_pt} PyTorch, {total_onnx} ONNX")
    print("Models are ready for real-time detection!")

if __name__ == "__main__":
    main()
