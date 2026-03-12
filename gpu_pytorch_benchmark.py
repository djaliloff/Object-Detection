#!/usr/bin/env python3
"""
GPU vs PyTorch Performance Comparison
Compares GPU-accelerated PyTorch models vs CPU models for real-time detection.
"""

import time
import numpy as np
import cv2
from pathlib import Path
from typing import Dict, List, Tuple
import logging
from ultralytics import YOLO
import torch

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GPUPyTorchBenchmark:
    """Benchmark GPU vs CPU performance for PyTorch YOLO models."""
    
    def __init__(self):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        logger.info(f"Using device: {self.device}")
        if torch.cuda.is_available():
            logger.info(f"GPU: {torch.cuda.get_device_name(0)}")
            logger.info(f"GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
    
    def benchmark_model(self, model_path: str, use_gpu: bool = True, num_frames: int = 100) -> Dict:
        """Benchmark a single model on CPU or GPU."""
        device = 'cuda' if use_gpu and torch.cuda.is_available() else 'cpu'
        mode = "GPU" if use_gpu and torch.cuda.is_available() else "CPU"
        
        logger.info(f"Benchmarking {Path(model_path).name} on {mode}...")
        
        try:
            # Load model
            model = YOLO(model_path)
            
            # Move model to GPU if requested
            if use_gpu and torch.cuda.is_available():
                model.to('cuda')
            
            # Create test image
            test_image = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
            
            # Warm up
            for _ in range(5):
                model(test_image, verbose=False, device=device)
            
            # Clear GPU cache before benchmark
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
            
            # Benchmark
            times = []
            for i in range(num_frames):
                if torch.cuda.is_available():
                    torch.cuda.synchronize()
                
                start_time = time.time()
                results = model(test_image, verbose=False, device=device)
                
                if torch.cuda.is_available():
                    torch.cuda.synchronize()
                
                inference_time = time.time() - start_time
                times.append(inference_time)
                
                if (i + 1) % 20 == 0:
                    logger.info(f"  Processed {i + 1}/{num_frames} frames")
            
            avg_time = np.mean(times) * 1000
            fps = 1.0 / np.mean(times)
            
            # Get GPU memory usage if applicable
            memory_usage = None
            if torch.cuda.is_available() and use_gpu:
                memory_usage = torch.cuda.memory_allocated() / 1024**3  # GB
            
            return {
                'avg_time_ms': avg_time,
                'fps': fps,
                'min_time_ms': np.min(times) * 1000,
                'max_time_ms': np.max(times) * 1000,
                'std_time_ms': np.std(times) * 1000,
                'device': mode,
                'memory_usage_gb': memory_usage
            }
            
        except Exception as e:
            logger.error(f"Failed to benchmark {model_path} on {mode}: {e}")
            return None
    
    def compare_all_models(self, models_dir: str = "models", num_frames: int = 100):
        """Compare all available models on CPU vs GPU."""
        models_dir = Path(models_dir)
        pt_models = list(models_dir.glob("*.pt"))
        
        if not pt_models:
            logger.error(f"No PyTorch models found in {models_dir}")
            return
        
        logger.info(f"Found {len(pt_models)} PyTorch models")
        logger.info(f"GPU Available: {torch.cuda.is_available()}")
        
        results = {}
        
        for model_path in pt_models:
            logger.info(f"\n{'='*60}")
            logger.info(f"Benchmarking {model_path.name}")
            logger.info(f"{'='*60}")
            
            model_results = {}
            
            # Benchmark CPU
            cpu_results = self.benchmark_model(str(model_path), use_gpu=False, num_frames=num_frames)
            if cpu_results:
                model_results['cpu'] = cpu_results
                logger.info(f"CPU:  {cpu_results['avg_time_ms']:6.1f}ms ± {cpu_results['std_time_ms']:4.1f}ms | {cpu_results['fps']:5.1f} FPS")
            
            # Benchmark GPU
            if torch.cuda.is_available():
                gpu_results = self.benchmark_model(str(model_path), use_gpu=True, num_frames=num_frames)
                if gpu_results:
                    model_results['gpu'] = gpu_results
                    logger.info(f"GPU:  {gpu_results['avg_time_ms']:6.1f}ms ± {gpu_results['std_time_ms']:4.1f}ms | {gpu_results['fps']:5.1f} FPS")
                    
                    if gpu_results['memory_usage_gb']:
                        logger.info(f"GPU Memory: {gpu_results['memory_usage_gb']:.2f} GB")
                    
                    # Calculate speedup
                    if cpu_results:
                        speedup = cpu_results['avg_time_ms'] / gpu_results['avg_time_ms']
                        model_results['speedup'] = speedup
                        logger.info(f"⚡ Speedup: {speedup:.1f}x faster")
            
            results[model_path.name] = model_results
        
        # Print summary
        self.print_summary(results)
        
        return results
    
    def print_summary(self, results: Dict):
        """Print comprehensive performance summary."""
        logger.info("\n" + "="*80)
        logger.info("GPU vs CPU PERFORMANCE SUMMARY")
        logger.info("="*80)
        
        # Model-by-model comparison
        for model_name, model_results in results.items():
            logger.info(f"\n{model_name.upper().replace('.PT', '')}")
            logger.info("-" * 50)
            
            if 'cpu' in model_results:
                cpu = model_results['cpu']
                logger.info(f"CPU:  {cpu['avg_time_ms']:6.1f}ms ± {cpu['std_time_ms']:4.1f}ms | {cpu['fps']:5.1f} FPS")
            
            if 'gpu' in model_results:
                gpu = model_results['gpu']
                logger.info(f"GPU:  {gpu['avg_time_ms']:6.1f}ms ± {gpu['std_time_ms']:4.1f}ms | {gpu['fps']:5.1f} FPS")
                
                if gpu['memory_usage_gb']:
                    logger.info(f"      Memory: {gpu['memory_usage_gb']:.2f} GB")
            
            if 'speedup' in model_results:
                speedup = model_results['speedup']
                if speedup > 1:
                    logger.info(f"⚡ Speedup: {speedup:.1f}x faster")
                else:
                    logger.info(f"🐌 Speedup: {speedup:.1f}x (slower)")
        
        # Overall ranking
        logger.info("\n" + "="*80)
        logger.info("OVERALL PERFORMANCE RANKING")
        logger.info("="*80)
        
        all_results = []
        for model_name, model_results in results.items():
            if 'cpu' in model_results:
                all_results.append((f"{model_name} (CPU)", model_results['cpu']['avg_time_ms'], model_results['cpu']['fps']))
            if 'gpu' in model_results:
                all_results.append((f"{model_name} (GPU)", model_results['gpu']['avg_time_ms'], model_results['gpu']['fps']))
        
        # Sort by inference time (fastest first)
        all_results.sort(key=lambda x: x[1])
        
        for i, (model_name, avg_time, fps) in enumerate(all_results, 1):
            device = model_name.split()[-1].strip("()")
            logger.info(f"{i:2d}. {model_name:25} | {avg_time:6.1f}ms | {fps:5.1f} FPS")
        
        # GPU speedup summary
        logger.info("\n" + "="*80)
        logger.info("GPU ACCELERATION SUMMARY")
        logger.info("="*80)
        
        gpu_speedups = []
        for model_name, model_results in results.items():
            if 'speedup' in model_results:
                speedup = model_results['speedup']
                gpu_speedups.append((model_name, speedup))
        
        if gpu_speedups:
            gpu_speedups.sort(key=lambda x: x[1], reverse=True)
            
            logger.info(f"{'Model':<15} | {'Speedup':>8} | {'Status':>12}")
            logger.info("-" * 40)
            
            for model_name, speedup in gpu_speedups:
                if speedup > 2.0:
                    status = "🚀 Excellent"
                elif speedup > 1.5:
                    status = "✅ Good"
                elif speedup > 1.0:
                    status = "⚡ Modest"
                else:
                    status = "❌ Poor"
                
                logger.info(f"{model_name:<15} | {speedup:8.1f}x | {status:>12}")
            
            avg_speedup = np.mean([s for _, s in gpu_speedups])
            logger.info("-" * 40)
            logger.info(f"{'Average':<15} | {avg_speedup:8.1f}x | {'Overall':>12}")

def main():
    """Main execution function."""
    benchmark = GPUPyTorchBenchmark()
    
    logger.info("Starting GPU vs CPU PyTorch Performance Benchmark")
    logger.info("This will compare PyTorch models on GPU vs CPU for real-time detection")
    
    # Run comparison
    results = benchmark.compare_all_models(num_frames=100)
    
    # Save results
    import json
    with open('gpu_pytorch_benchmark_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info("\nResults saved to 'gpu_pytorch_benchmark_results.json'")

if __name__ == "__main__":
    main()
