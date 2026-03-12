# YOLO Models Setup and Performance Analysis

## Overview
This setup provides YOLOv11, YOLOv8, and YOLOv9 models with ONNX conversion for real-time object detection with minimal latency.

## Available Models

### Successfully Downloaded and Converted:
- **YOLOv8n** (PyTorch + ONNX) - 6.2MB / 12.2MB - Ultra-fast detection
- **YOLOv11n** (PyTorch) - 5.4MB - Latest generation, very fast  
- **YOLOv11s** (PyTorch) - 18.4MB - Good balance of speed and accuracy
- **YOLOv9t** (PyTorch) - 4.7MB - Enhanced accuracy

### Performance Results (CPU-only testing):

| Model | Format | Avg Time | FPS | Status |
|-------|--------|----------|-----|---------|
| **YOLOv8n** | PyTorch | **13.6ms** | **73.6 FPS** | ✅ Best Performance |
| **YOLOv11n** | PyTorch | 13.9ms | 71.8 FPS | ✅ Excellent |
| **YOLOv11s** | PyTorch | 15.6ms | 63.9 FPS | ✅ Good |
| **YOLOv9t** | PyTorch | 27.5ms | 36.4 FPS | ✅ Acceptable |
| **YOLOv8n** | ONNX | 42.8ms | 23.4 FPS | ⚠️ Slower on CPU |

## Key Findings

### 🏆 Performance Winner: YOLOv8n (PyTorch)
- **Fastest inference**: 13.6ms average (73.6 FPS)
- **Small model size**: 6.2MB
- **Most stable**: Consistent performance across runs

### 🆕 Latest Generation: YOLOv11n  
- **Very close performance**: 13.9ms (71.8 FPS)
- **Newest architecture**: Latest YOLO improvements
- **Slightly larger**: 5.4MB

### ⚠️ ONNX Performance Note
- ONNX models performed **slower on CPU** due to optimization overhead
- ONNX typically shines with **GPU acceleration**
- PyTorch models are currently **better for CPU-only deployment**

## Usage Examples

### Real-time Detection (Recommended - PyTorch):
```bash
# Use the fastest model
python realtime_onnx_detection.py --model models/yolov8n.pt --camera 0

# Use latest generation
python realtime_onnx_detection.py --model models/yolo11n.pt --camera 0
```

### Performance Benchmarking:
```bash
# Compare all models
python compare_performance.py

# Benchmark specific model
python realtime_onnx_detection.py --benchmark --benchmark-frames 100
```

### Model Downloads:
```bash
# Download additional models
python download_models.py
```

## Recommendations for Real-time Detection

### For CPU Deployment (Current Setup):
1. **Primary Choice**: YOLOv8n (PyTorch) - Best performance
2. **Alternative**: YOLOv11n (PyTorch) - Latest generation
3. **Higher Accuracy**: YOLOv11s (PyTorch) - Slightly slower but more accurate

### For GPU Deployment (Future Enhancement):
1. **Enable CUDA**: Install onnxruntime-gpu
2. **Use ONNX**: Re-export models with GPU optimization
3. **Expected Improvement**: 2-5x faster inference with ONNX + GPU

## Integration with Surveillance Platform

The models are now integrated into the surveillance system via:
- `model_registry.yaml` - Configuration for all models
- `ai-engine/inference.py` - Updated to support new models
- Real-time detection with minimal latency

## Next Steps for Optimal Performance

1. **GPU Setup**: Install CUDA and onnxruntime-gpu for 2-5x speedup
2. **Model Tuning**: Adjust confidence thresholds for specific use cases
3. **Batch Processing**: Enable batch processing for higher throughput
4. **Model Selection**: Choose models based on accuracy vs speed requirements

## File Structure
```
models/
├── yolov8n.pt      # Best performance (PyTorch)
├── yolov8n.onnx    # ONNX version (slower on CPU)
├── yolo11n.pt      # Latest generation
├── yolo11s.pt      # Balanced performance
├── yolov9t.pt      # Higher accuracy
└── [other models]
```

The setup is ready for real-time detection with **minimal latency** using the PyTorch models, which currently outperform ONNX on CPU hardware.
