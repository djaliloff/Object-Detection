#!/usr/bin/env python3
"""
Platform-wide Latency Monitoring System
Monitors latency across all components of the surveillance platform.
"""

import time
import json
import threading
import redis
import psutil
import torch
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import logging
import numpy as np
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class LatencyMetrics:
    """Latency metrics for a component."""
    component_name: str
    avg_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    fps: float
    total_frames: int
    error_count: int
    last_update: str
    
    @classmethod
    def from_times(cls, component_name: str, times: List[float], fps: float, error_count: int = 0):
        """Create metrics from timing data."""
        if not times:
            return cls(
                component_name=component_name,
                avg_latency_ms=0.0,
                min_latency_ms=0.0,
                max_latency_ms=0.0,
                p95_latency_ms=0.0,
                p99_latency_ms=0.0,
                fps=fps,
                total_frames=0,
                error_count=error_count,
                last_update=datetime.now().isoformat()
            )
        
        times_ms = np.array(times) * 1000
        return cls(
            component_name=component_name,
            avg_latency_ms=np.mean(times_ms),
            min_latency_ms=np.min(times_ms),
            max_latency_ms=np.max(times_ms),
            p95_latency_ms=np.percentile(times_ms, 95),
            p99_latency_ms=np.percentile(times_ms, 99),
            fps=fps,
            total_frames=len(times),
            error_count=error_count,
            last_update=datetime.now().isoformat()
        )

@dataclass
class SystemMetrics:
    """System-wide performance metrics."""
    cpu_percent: float
    memory_percent: float
    memory_used_gb: float
    memory_total_gb: float
    gpu_memory_used_gb: float = 0.0
    gpu_memory_total_gb: float = 0.0
    gpu_utilization_percent: float = 0.0
    active_cameras: int = 0
    total_detections: int = 0
    platform_fps: float = 0.0
    last_update: str = ""

class LatencyMonitor:
    """Platform-wide latency monitoring system."""
    
    def __init__(self, redis_client: redis.Redis, monitoring_interval: int = 10):
        """
        Initialize latency monitor.
        
        Args:
            redis_client: Redis client for data collection
            monitoring_interval: Monitoring interval in seconds
        """
        self.redis_client = redis_client
        self.monitoring_interval = monitoring_interval
        self.running = False
        self.monitor_thread = None
        
        # Component metrics storage
        self.component_metrics: Dict[str, LatencyMetrics] = {}
        self.system_metrics: List[SystemMetrics] = []
        
        # Performance history
        self.max_history_size = 1000
        
        logger.info("Latency monitor initialized")
    
    def start(self):
        """Start latency monitoring."""
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("Latency monitoring started")
    
    def stop(self):
        """Stop latency monitoring."""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5.0)
        logger.info("Latency monitoring stopped")
    
    def _monitoring_loop(self):
        """Main monitoring loop."""
        while self.running:
            try:
                # Collect system metrics
                system_metrics = self._collect_system_metrics()
                self.system_metrics.append(system_metrics)
                
                # Keep only recent history
                if len(self.system_metrics) > self.max_history_size:
                    self.system_metrics.pop(0)
                
                # Collect component metrics from Redis
                self._collect_component_metrics()
                
                # Store aggregated metrics in Redis
                self._store_metrics()
                
                # Check for performance alerts
                self._check_alerts()
                
                time.sleep(self.monitoring_interval)
                
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                time.sleep(self.monitoring_interval)
    
    def _collect_system_metrics(self) -> SystemMetrics:
        """Collect system-wide performance metrics."""
        # CPU and Memory
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        
        # GPU metrics (if available)
        gpu_memory_used = 0.0
        gpu_memory_total = 0.0
        gpu_utilization = 0.0
        
        if torch.cuda.is_available():
            gpu_memory_used = torch.cuda.memory_allocated() / 1024**3
            gpu_memory_total = torch.cuda.get_device_properties(0).total_memory / 1024**3
            gpu_utilization = (gpu_memory_used / gpu_memory_total) * 100
        
        # Platform metrics from Redis
        active_cameras = 0
        total_detections = 0
        platform_fps = 0.0
        
        try:
            # Get camera stats
            camera_stats = self.redis_client.get('camera_stats')
            if camera_stats:
                stats = json.loads(camera_stats.decode('utf-8'))
                active_cameras = stats.get('active_cameras', 0)
            
            # Get detection stats
            detection_stats = self.redis_client.get('detection_stats')
            if detection_stats:
                stats = json.loads(detection_stats.decode('utf-8'))
                total_detections = stats.get('total_detections', 0)
                platform_fps = stats.get('fps', 0.0)
                
        except Exception as e:
            logger.debug(f"Could not collect platform metrics: {e}")
        
        return SystemMetrics(
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            memory_used_gb=memory.used / 1024**3,
            memory_total_gb=memory.total / 1024**3,
            gpu_memory_used_gb=gpu_memory_used,
            gpu_memory_total_gb=gpu_memory_total,
            gpu_utilization_percent=gpu_utilization,
            active_cameras=active_cameras,
            total_detections=total_detections,
            platform_fps=platform_fps,
            last_update=datetime.now().isoformat()
        )
    
    def _collect_component_metrics(self):
        """Collect metrics from individual components."""
        try:
            # Get AI engine metrics
            ai_stats = self.redis_client.get('ai_engine_stats')
            if ai_stats:
                stats = json.loads(ai_stats.decode('utf-8'))
                
                # Create latency metrics for AI engine
                avg_time = stats.get('avg_inference_time_ms', 0)
                fps = stats.get('fps', 0)
                total_frames = stats.get('frames_processed', 0)
                
                self.component_metrics['ai_engine'] = LatencyMetrics(
                    component_name='ai_engine',
                    avg_latency_ms=avg_time,
                    min_latency_ms=avg_time * 0.8,  # Estimate
                    max_latency_ms=avg_time * 1.5,  # Estimate
                    p95_latency_ms=avg_time * 1.2,  # Estimate
                    p99_latency_ms=avg_time * 1.8,  # Estimate
                    fps=fps,
                    total_frames=total_frames,
                    error_count=0,
                    last_update=datetime.now().isoformat()
                )
            
            # Get camera gateway metrics
            camera_stats = self.redis_client.get('camera_gateway_stats')
            if camera_stats:
                stats = json.loads(camera_stats.decode('utf-8'))
                
                for camera_id, camera_data in stats.get('cameras', {}).items():
                    fps = camera_data.get('actual_fps', 0)
                    
                    self.component_metrics[f'camera_{camera_id}'] = LatencyMetrics(
                        component_name=f'camera_{camera_id}',
                        avg_latency_ms=1000 / fps if fps > 0 else 0,  # Estimate from FPS
                        min_latency_ms=0,
                        max_latency_ms=0,
                        p95_latency_ms=0,
                        p99_latency_ms=0,
                        fps=fps,
                        total_frames=0,
                        error_count=camera_data.get('connection_errors', 0),
                        last_update=datetime.now().isoformat()
                    )
            
        except Exception as e:
            logger.error(f"Error collecting component metrics: {e}")
    
    def _store_metrics(self):
        """Store metrics in Redis for dashboard and analysis."""
        try:
            # Store component metrics
            component_data = {name: asdict(metrics) for name, metrics in self.component_metrics.items()}
            self.redis_client.set('latency_component_metrics', json.dumps(component_data))
            
            # Store latest system metrics
            if self.system_metrics:
                latest_system = self.system_metrics[-1]
                self.redis_client.set('latency_system_metrics', json.dumps(asdict(latest_system)))
            
            # Store historical system metrics (keep last 100)
            if len(self.system_metrics) > 100:
                recent_metrics = self.system_metrics[-100:]
            else:
                recent_metrics = self.system_metrics
            
            system_history = [asdict(metrics) for metrics in recent_metrics]
            self.redis_client.set('latency_system_history', json.dumps(system_history))
            
        except Exception as e:
            logger.error(f"Error storing metrics: {e}")
    
    def _check_alerts(self):
        """Check for performance alerts."""
        alerts = []
        
        # Check AI engine latency
        if 'ai_engine' in self.component_metrics:
            ai_metrics = self.component_metrics['ai_engine']
            if ai_metrics.avg_latency_ms > 50:  # Alert if >50ms
                alerts.append({
                    'type': 'high_latency',
                    'component': 'ai_engine',
                    'value': ai_metrics.avg_latency_ms,
                    'threshold': 50,
                    'message': f"AI engine latency too high: {ai_metrics.avg_latency_ms:.1f}ms"
                })
            
            if ai_metrics.fps < 20:  # Alert if <20 FPS
                alerts.append({
                    'type': 'low_fps',
                    'component': 'ai_engine',
                    'value': ai_metrics.fps,
                    'threshold': 20,
                    'message': f"AI engine FPS too low: {ai_metrics.fps:.1f}"
                })
        
        # Check system resources
        if self.system_metrics:
            latest = self.system_metrics[-1]
            
            if latest.cpu_percent > 80:
                alerts.append({
                    'type': 'high_cpu',
                    'component': 'system',
                    'value': latest.cpu_percent,
                    'threshold': 80,
                    'message': f"High CPU usage: {latest.cpu_percent:.1f}%"
                })
            
            if latest.memory_percent > 85:
                alerts.append({
                    'type': 'high_memory',
                    'component': 'system',
                    'value': latest.memory_percent,
                    'threshold': 85,
                    'message': f"High memory usage: {latest.memory_percent:.1f}%"
                })
            
            if latest.gpu_utilization_percent > 90:
                alerts.append({
                    'type': 'high_gpu',
                    'component': 'system',
                    'value': latest.gpu_utilization_percent,
                    'threshold': 90,
                    'message': f"High GPU usage: {latest.gpu_utilization_percent:.1f}%"
                })
        
        # Store alerts
        if alerts:
            self.redis_client.set('latency_alerts', json.dumps(alerts))
            
            # Log alerts
            for alert in alerts:
                logger.warning(f"ALERT: {alert['message']}")
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary."""
        summary = {
            'timestamp': datetime.now().isoformat(),
            'components': {},
            'system': {},
            'alerts': []
        }
        
        # Component metrics
        for name, metrics in self.component_metrics.items():
            summary['components'][name] = {
                'avg_latency_ms': metrics.avg_latency_ms,
                'fps': metrics.fps,
                'total_frames': metrics.total_frames,
                'error_count': metrics.error_count,
                'status': 'healthy' if metrics.avg_latency_ms < 50 and metrics.fps > 20 else 'warning'
            }
        
        # Latest system metrics
        if self.system_metrics:
            latest = self.system_metrics[-1]
            summary['system'] = {
                'cpu_percent': latest.cpu_percent,
                'memory_percent': latest.memory_percent,
                'gpu_utilization_percent': latest.gpu_utilization_percent,
                'active_cameras': latest.active_cameras,
                'platform_fps': latest.platform_fps,
                'status': 'healthy' if latest.cpu_percent < 80 and latest.memory_percent < 85 else 'warning'
            }
        
        # Current alerts
        try:
            alerts_data = self.redis_client.get('latency_alerts')
            if alerts_data:
                summary['alerts'] = json.loads(alerts_data.decode('utf-8'))
        except Exception:
            pass
        
        return summary
    
    def generate_report(self, duration_minutes: int = 60) -> Dict[str, Any]:
        """Generate performance report for the last N minutes."""
        cutoff_time = datetime.now() - timedelta(minutes=duration_minutes)
        
        # Filter system metrics
        recent_system = []
        for metrics in self.system_metrics:
            try:
                metrics_time = datetime.fromisoformat(metrics.last_update)
                if metrics_time >= cutoff_time:
                    recent_system.append(metrics)
            except:
                continue
        
        if not recent_system:
            return {'error': 'No data available for the specified duration'}
        
        # Calculate aggregates
        cpu_values = [m.cpu_percent for m in recent_system]
        memory_values = [m.memory_percent for m in recent_system]
        gpu_values = [m.gpu_utilization_percent for m in recent_system]
        
        report = {
            'duration_minutes': duration_minutes,
            'period': {
                'start': cutoff_time.isoformat(),
                'end': datetime.now().isoformat(),
                'data_points': len(recent_system)
            },
            'system_performance': {
                'cpu': {
                    'avg': np.mean(cpu_values),
                    'min': np.min(cpu_values),
                    'max': np.max(cpu_values),
                    'p95': np.percentile(cpu_values, 95)
                },
                'memory': {
                    'avg': np.mean(memory_values),
                    'min': np.min(memory_values),
                    'max': np.max(memory_values),
                    'p95': np.percentile(memory_values, 95)
                },
                'gpu': {
                    'avg': np.mean(gpu_values),
                    'min': np.min(gpu_values),
                    'max': np.max(gpu_values),
                    'p95': np.percentile(gpu_values, 95)
                }
            },
            'components': {},
            'alerts_count': 0
        }
        
        # Component performance
        for name, metrics in self.component_metrics.items():
            try:
                metrics_time = datetime.fromisoformat(metrics.last_update)
                if metrics_time >= cutoff_time:
                    report['components'][name] = {
                        'avg_latency_ms': metrics.avg_latency_ms,
                        'fps': metrics.fps,
                        'total_frames': metrics.total_frames,
                        'error_count': metrics.error_count
                    }
            except:
                continue
        
        # Count alerts
        try:
            alerts_data = self.redis_client.get('latency_alerts')
            if alerts_data:
                alerts = json.loads(alerts_data.decode('utf-8'))
                report['alerts_count'] = len(alerts)
        except:
            pass
        
        return report

def main():
    """Main function for latency monitor."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Platform Latency Monitor")
    parser.add_argument('--interval', type=int, default=10,
                        help='Monitoring interval in seconds')
    parser.add_argument('--report', type=int,
                        help='Generate report for last N minutes')
    parser.add_argument('--summary', action='store_true',
                        help='Show current metrics summary')
    
    args = parser.parse_args()
    
    # Connect to Redis
    try:
        redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            decode_responses=False
        )
        redis_client.ping()
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        return
    
    monitor = LatencyMonitor(redis_client, args.interval)
    
    if args.summary:
        # Show current summary
        monitor._collect_component_metrics()
        monitor._collect_system_metrics()
        summary = monitor.get_metrics_summary()
        
        print("\n=== Platform Latency Summary ===")
        print(f"Timestamp: {summary['timestamp']}")
        
        print("\nSystem Performance:")
        system = summary['system']
        print(f"  CPU: {system.get('cpu_percent', 0):.1f}%")
        print(f"  Memory: {system.get('memory_percent', 0):.1f}%")
        print(f"  GPU: {system.get('gpu_utilization_percent', 0):.1f}%")
        print(f"  Active Cameras: {system.get('active_cameras', 0)}")
        print(f"  Platform FPS: {system.get('platform_fps', 0):.1f}")
        print(f"  Status: {system.get('status', 'unknown')}")
        
        print("\nComponent Performance:")
        for name, comp in summary['components'].items():
            print(f"  {name}:")
            print(f"    Latency: {comp['avg_latency_ms']:.1f}ms")
            print(f"    FPS: {comp['fps']:.1f}")
            print(f"    Status: {comp['status']}")
        
        if summary['alerts']:
            print(f"\nAlerts: {len(summary['alerts'])}")
            for alert in summary['alerts']:
                print(f"  - {alert['message']}")
        
        return
    
    if args.report:
        # Generate report
        monitor._collect_component_metrics()
        monitor._collect_system_metrics()
        report = monitor.generate_report(args.report)
        
        if 'error' in report:
            print(f"Error: {report['error']}")
            return
        
        print(f"\n=== Performance Report (Last {args.report} minutes) ===")
        print(f"Period: {report['period']['start']} to {report['period']['end']}")
        print(f"Data Points: {report['period']['data_points']}")
        
        print("\nSystem Performance:")
        sys_perf = report['system_performance']
        
        for component in ['cpu', 'memory', 'gpu']:
            if component in sys_perf:
                perf = sys_perf[component]
                print(f"  {component.upper()}:")
                print(f"    Average: {perf['avg']:.1f}%")
                print(f"    Min: {perf['min']:.1f}%")
                print(f"    Max: {perf['max']:.1f}%")
                print(f"    P95: {perf['p95']:.1f}%")
        
        print(f"\nAlerts: {report['alerts_count']}")
        
        return
    
    # Start monitoring
    try:
        monitor.start()
        logger.info("Latency monitor running. Press Ctrl+C to stop.")
        
        while True:
            time.sleep(30)
            summary = monitor.get_metrics_summary()
            
            # Print brief status
            system = summary.get('system', {})
            print(f"Status: CPU {system.get('cpu_percent', 0):.1f}%, "
                  f"Memory {system.get('memory_percent', 0):.1f}%, "
                  f"GPU {system.get('gpu_utilization_percent', 0):.1f}%, "
                  f"Cameras {system.get('active_cameras', 0)}, "
                  f"Alerts {len(summary.get('alerts', []))}")
            
    except KeyboardInterrupt:
        logger.info("Stopping latency monitor...")
    finally:
        monitor.stop()

if __name__ == "__main__":
    main()
