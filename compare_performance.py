#!/usr/bin/env python3
"""
YOLO vs ONNX Performance Comparison Script
Compares performance between PyTorch YOLO models and ONNX-optimized models
for real-time detection latency analysis.
"""

import time
import numpy as np
import cv2
from pathlib import Path
from typing import Dict, List, Tuple
import logging
from ultralytics import YOLO
from realtime_onnx_detection import ONNXYOLODetector

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ModelPerformanceComparator:
    """Compare performance between PyTorch and ONNX models."""
    
    def __init__(self, models_dir: str = "models"):
        self.models_dir = Path(models_dir)
        self.results = {}
        
    def benchmark_pytorch_model(self, model_path: str, num_frames: int = 100) -> Dict:
        """Benchmark PyTorch YOLO model."""
        logger.info(f"Benchmarking PyTorch model: {model_path}")
        
        try:
            # Load PyTorch model
            model = YOLO(model_path)
            
            # Create test image
            test_image = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
            
            # Warm up
            for _ in range(5):
                model(test_image, verbose=False)
            
            # Benchmark
            times = []
            for i in range(num_frames):
                start_time = time.time()
                results = model(test_image, verbose=False)
                inference_time = time.time() - start_time
                times.append(inference_time)
                
                if (i + 1) % 20 == 0:
                    logger.info(f"  Processed {i + 1}/{num_frames} frames")
            
            avg_time = np.mean(times) * 1000
            fps = 1.0 / np.mean(times)
            
            return {
                'avg_time_ms': avg_time,
                'fps': fps,
                'min_time_ms': np.min(times) * 1000,
                'max_time_ms': np.max(times) * 1000,
                'std_time_ms': np.std(times) * 1000
            }
            
        except Exception as e:
            logger.error(f"Failed to benchmark {model_path}: {e}")
            return None
    
    def benchmark_onnx_model(self, model_path: str, num_frames: int = 100) -> Dict:
        """Benchmark ONNX model."""
        logger.info(f"Benchmarking ONNX model: {model_path}")
        
        try:
            # Load ONNX model
            detector = ONNXYOLODetector(model_path)
            
            # Create test image
            test_image = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
            
            # Warm up
            for _ in range(5):
                detector.detect(test_image)
            
            # Benchmark
            times = []
            for i in range(num_frames):
                _, inference_time = detector.detect(test_image)
                times.append(inference_time)
                
                if (i + 1) % 20 == 0:
                    logger.info(f"  Processed {i + 1}/{num_frames} frames")
            
            avg_time = np.mean(times) * 1000
            fps = 1.0 / np.mean(times)
            
            return {
                'avg_time_ms': avg_time,
                'fps': fps,
                'min_time_ms': np.min(times) * 1000,
                'max_time_ms': np.max(times) * 1000,
                'std_time_ms': np.std(times) * 1000
            }
            
        except Exception as e:
            logger.error(f"Failed to benchmark {model_path}: {e}")
            return None
    
    def compare_models(self, num_frames: int = 100) -> Dict:
        """Compare all available PyTorch and ONNX models."""
        # Find model pairs
        pt_models = list(self.models_dir.glob("*.pt"))
        onnx_models = list(self.models_dir.glob("*.onnx"))
        
        logger.info(f"Found {len(pt_models)} PyTorch models and {len(onnx_models)} ONNX models")
        
        comparison_results = {}
        
        # Group models by base name
        model_groups = {}
        
        for pt_path in pt_models:
            base_name = pt_path.stem
            if base_name not in model_groups:
                model_groups[base_name] = {}
            model_groups[base_name]['pytorch'] = pt_path
        
        for onnx_path in onnx_models:
            base_name = onnx_path.stem
            if base_name not in model_groups:
                model_groups[base_name] = {}
            model_groups[base_name]['onnx'] = onnx_path
        
        # Compare each model group
        for base_name, models in model_groups.items():
            logger.info(f"\n=== Comparing {base_name} ===")
            
            comparison_results[base_name] = {}
            
            # Benchmark PyTorch model
            if 'pytorch' in models:
                pt_results = self.benchmark_pytorch_model(str(models['pytorch']), num_frames)
                if pt_results:
                    comparison_results[base_name]['pytorch'] = pt_results
                    logger.info(f"  PyTorch: {pt_results['avg_time_ms']:.1f}ms avg, {pt_results['fps']:.1f} FPS")
            
            # Benchmark ONNX model
            if 'onnx' in models:
                onnx_results = self.benchmark_onnx_model(str(models['onnx']), num_frames)
                if onnx_results:
                    comparison_results[base_name]['onnx'] = onnx_results
                    logger.info(f"  ONNX: {onnx_results['avg_time_ms']:.1f}ms avg, {onnx_results['fps']:.1f} FPS")
            
            # Calculate improvement
            if 'pytorch' in comparison_results[base_name] and 'onnx' in comparison_results[base_name]:
                pt_time = comparison_results[base_name]['pytorch']['avg_time_ms']
                onnx_time = comparison_results[base_name]['onnx']['avg_time_ms']
                improvement = ((pt_time - onnx_time) / pt_time) * 100
                
                comparison_results[base_name]['improvement_percent'] = improvement
                logger.info(f"  Improvement: {improvement:.1f}% faster")
        
        return comparison_results
    
    def print_comparison_summary(self, results: Dict):
        """Print detailed comparison summary."""
        logger.info("\n" + "="*80)
        logger.info("PERFORMANCE COMPARISON SUMMARY")
        logger.info("="*80)
        
        for model_name, comparison in results.items():
            logger.info(f"\n{model_name.upper()}")
            logger.info("-" * 40)
            
            if 'pytorch' in comparison:
                pt = comparison['pytorch']
                logger.info(f"PyTorch:  {pt['avg_time_ms']:6.1f}ms ± {pt['std_time_ms']:4.1f}ms | {pt['fps']:5.1f} FPS")
            
            if 'onnx' in comparison:
                onnx = comparison['onnx']
                logger.info(f"ONNX:     {onnx['avg_time_ms']:6.1f}ms ± {onnx['std_time_ms']:4.1f}ms | {onnx['fps']:5.1f} FPS")
            
            if 'improvement_percent' in comparison:
                improvement = comparison['improvement_percent']
                if improvement > 0:
                    logger.info(f"Speedup:   {improvement:+.1f}% ⚡")
                else:
                    logger.info(f"Speedup:   {improvement:+.1f}% 🐌")
        
        # Overall summary
        logger.info("\n" + "="*80)
        logger.info("OVERALL PERFORMANCE RANKING")
        logger.info("="*80)
        
        all_models = []
        for model_name, comparison in results.items():
            if 'pytorch' in comparison:
                all_models.append((f"{model_name} (PyTorch)", comparison['pytorch']['avg_time_ms']))
            if 'onnx' in comparison:
                all_models.append((f"{model_name} (ONNX)", comparison['onnx']['avg_time_ms']))
        
        # Sort by inference time (fastest first)
        all_models.sort(key=lambda x: x[1])
        
        for i, (model_name, avg_time) in enumerate(all_models, 1):
            fps = 1000 / avg_time
            logger.info(f"{i:2d}. {model_name:20} | {avg_time:6.1f}ms | {fps:5.1f} FPS")
        
        # Best ONNX vs PyTorch comparison
        logger.info("\n" + "="*80)
        logger.info("ONNX vs PYTORCH DIRECT COMPARISON")
        logger.info("="*80)
        
        onnx_vs_pt = []
        for model_name, comparison in results.items():
            if 'pytorch' in comparison and 'onnx' in comparison:
                pt_time = comparison['pytorch']['avg_time_ms']
                onnx_time = comparison['onnx']['avg_time_ms']
                improvement = comparison['improvement_percent']
                onnx_vs_pt.append((model_name, pt_time, onnx_time, improvement))
        
        onnx_vs_pt.sort(key=lambda x: x[3], reverse=True)  # Sort by improvement
        
        for model_name, pt_time, onnx_time, improvement in onnx_vs_pt:
            logger.info(f"{model_name:15} | PT: {pt_time:6.1f}ms | ONNX: {onnx_time:6.1f}ms | {improvement:+6.1f}%")

def main():
    """Main execution function."""
    comparator = ModelPerformanceComparator()
    
    logger.info("Starting YOLO vs ONNX Performance Comparison")
    logger.info("This will benchmark both PyTorch and ONNX models for latency analysis")
    
    # Run comparison
    results = comparator.compare_models(num_frames=100)
    
    # Print summary
    comparator.print_comparison_summary(results)
    
    # Save results to file
    import json
    with open('performance_comparison_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info("\nResults saved to 'performance_comparison_results.json'")

if __name__ == "__main__":
    main()
