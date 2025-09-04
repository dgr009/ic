#!/usr/bin/env python3
"""
Performance benchmarking runner for GCP services integration.

This script runs comprehensive performance benchmarks and generates
detailed performance reports.
"""

import time
import json
import psutil
import statistics
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Callable
from concurrent.futures import ThreadPoolExecutor
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.performance.test_gcp_performance import run_performance_tests
from tests.test_config import TEST_CONFIG


class PerformanceBenchmark:
    """Performance benchmarking utility."""
    
    def __init__(self):
        """Initialize benchmark runner."""
        self.results = {}
        self.system_info = self._get_system_info()
        self.start_time = None
        self.end_time = None
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get system information for benchmark context."""
        return {
            'cpu_count': psutil.cpu_count(),
            'cpu_count_logical': psutil.cpu_count(logical=True),
            'memory_total_gb': psutil.virtual_memory().total / (1024**3),
            'python_version': sys.version,
            'platform': sys.platform
        }
    
    def benchmark_function(self, func: Callable, name: str, iterations: int = 10, 
                          warmup: int = 2) -> Dict[str, Any]:
        """Benchmark a function with multiple iterations."""
        print(f"🔥 Benchmarking {name} ({iterations} iterations, {warmup} warmup)...")
        
        # Warmup runs
        for _ in range(warmup):
            try:
                func()
            except Exception as e:
                print(f"Warning: Warmup failed for {name}: {e}")
        
        # Benchmark runs
        times = []
        memory_usage = []
        
        for i in range(iterations):
            # Measure memory before
            process = psutil.Process()
            memory_before = process.memory_info().rss / 1024 / 1024  # MB
            
            # Time the function
            start_time = time.perf_counter()
            try:
                result = func()
                success = True
                error = None
            except Exception as e:
                success = False
                error = str(e)
                result = None
            end_time = time.perf_counter()
            
            # Measure memory after
            memory_after = process.memory_info().rss / 1024 / 1024  # MB
            
            duration = end_time - start_time
            memory_delta = memory_after - memory_before
            
            times.append(duration)
            memory_usage.append(memory_delta)
            
            if not success:
                print(f"  Iteration {i+1} failed: {error}")
        
        # Calculate statistics
        successful_times = [t for t in times if t > 0]
        
        if successful_times:
            stats = {
                'name': name,
                'iterations': iterations,
                'successful_runs': len(successful_times),
                'mean_time': statistics.mean(successful_times),
                'median_time': statistics.median(successful_times),
                'min_time': min(successful_times),
                'max_time': max(successful_times),
                'std_dev': statistics.stdev(successful_times) if len(successful_times) > 1 else 0,
                'mean_memory_delta': statistics.mean(memory_usage),
                'max_memory_delta': max(memory_usage),
                'times': successful_times,
                'memory_deltas': memory_usage
            }
        else:
            stats = {
                'name': name,
                'iterations': iterations,
                'successful_runs': 0,
                'error': 'All iterations failed'
            }
        
        return stats
    
    def benchmark_concurrency(self, func: Callable, name: str, 
                            thread_counts: List[int] = None) -> Dict[str, Any]:
        """Benchmark function with different concurrency levels."""
        if thread_counts is None:
            thread_counts = [1, 2, 4, 8, 16]
        
        print(f"🔀 Benchmarking {name} concurrency...")
        
        results = {}
        
        for thread_count in thread_counts:
            print(f"  Testing with {thread_count} threads...")
            
            def run_concurrent():
                with ThreadPoolExecutor(max_workers=thread_count) as executor:
                    futures = [executor.submit(func) for _ in range(thread_count)]
                    return [f.result() for f in futures]
            
            stats = self.benchmark_function(
                run_concurrent, 
                f"{name}_threads_{thread_count}", 
                iterations=5
            )
            
            results[thread_count] = stats
        
        return results
    
    def benchmark_scalability(self, func_factory: Callable, name: str,
                            data_sizes: List[int] = None) -> Dict[str, Any]:
        """Benchmark function scalability with different data sizes."""
        if data_sizes is None:
            data_sizes = [10, 50, 100, 500, 1000]
        
        print(f"📈 Benchmarking {name} scalability...")
        
        results = {}
        
        for size in data_sizes:
            print(f"  Testing with data size {size}...")
            
            func = func_factory(size)
            stats = self.benchmark_function(
                func,
                f"{name}_size_{size}",
                iterations=5
            )
            
            results[size] = stats
        
        return results
    
    def run_comprehensive_benchmark(self) -> Dict[str, Any]:
        """Run comprehensive performance benchmark."""
        print("🚀 Starting Comprehensive GCP Services Performance Benchmark")
        print("=" * 80)
        
        self.start_time = datetime.now()
        
        # Import test functions
        from tests.test_gcp_mock_data import GCPMockDataGenerator
        from gcp.compute.info import format_output
        
        generator = GCPMockDataGenerator()
        
        # 1. Authentication Benchmarks
        print("\n1. Authentication Performance")
        print("-" * 40)
        
        def mock_auth():
            from common.gcp_utils import GCPAuthManager
            with unittest.mock.patch('common.gcp_utils.service_account.Credentials.from_service_account_info'):
                auth_manager = GCPAuthManager()
                return auth_manager.get_credentials()
        
        self.results['authentication'] = self.benchmark_function(
            mock_auth, 'authentication', iterations=20
        )
        
        # 2. Data Generation Benchmarks
        print("\n2. Data Generation Performance")
        print("-" * 40)
        
        def generate_compute_data():
            return generator.generate_compute_instance()
        
        self.results['data_generation'] = self.benchmark_function(
            generate_compute_data, 'data_generation', iterations=100
        )
        
        # 3. Data Processing Benchmarks
        print("\n3. Data Processing Performance")
        print("-" * 40)
        
        def data_processing_factory(size):
            def process_data():
                data = [generator.generate_compute_instance(f"instance-{i}") for i in range(size)]
                filtered = [item for item in data if item['status'] == 'RUNNING']
                sorted_data = sorted(filtered, key=lambda x: x['name'])
                return len(sorted_data)
            return process_data
        
        self.results['data_processing'] = self.benchmark_scalability(
            data_processing_factory, 'data_processing'
        )
        
        # 4. Output Formatting Benchmarks
        print("\n4. Output Formatting Performance")
        print("-" * 40)
        
        def formatting_factory(size):
            def format_data():
                data = [generator.generate_compute_instance(f"instance-{i}") for i in range(size)]
                return format_output(data, 'json')
            return format_data
        
        self.results['output_formatting'] = self.benchmark_scalability(
            formatting_factory, 'output_formatting', [10, 50, 100, 200]
        )
        
        # 5. Concurrency Benchmarks
        print("\n5. Concurrency Performance")
        print("-" * 40)
        
        def concurrent_task():
            data = [generator.generate_compute_instance(f"instance-{i}") for i in range(10)]
            return len([item for item in data if item['status'] == 'RUNNING'])
        
        self.results['concurrency'] = self.benchmark_concurrency(
            concurrent_task, 'concurrent_processing'
        )
        
        # 6. Memory Usage Benchmarks
        print("\n6. Memory Usage Performance")
        print("-" * 40)
        
        def memory_intensive_factory(size):
            def memory_task():
                # Create large dataset
                data = [generator.generate_compute_instance(f"instance-{i}") for i in range(size)]
                # Duplicate data to test memory usage
                duplicated = data * 2
                # Process data
                result = [item for item in duplicated if 'instance' in item['name']]
                return len(result)
            return memory_task
        
        self.results['memory_usage'] = self.benchmark_scalability(
            memory_intensive_factory, 'memory_intensive', [50, 100, 200, 500]
        )
        
        self.end_time = datetime.now()
        
        return self.results
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive benchmark report."""
        if not self.results:
            raise ValueError("No benchmark results available. Run benchmark first.")
        
        report = {
            'metadata': {
                'timestamp': self.start_time.isoformat() if self.start_time else None,
                'duration_seconds': (self.end_time - self.start_time).total_seconds() if self.start_time and self.end_time else None,
                'system_info': self.system_info,
                'test_config': TEST_CONFIG
            },
            'results': self.results,
            'summary': self._generate_summary(),
            'recommendations': self._generate_recommendations()
        }
        
        return report
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate performance summary."""
        summary = {}
        
        # Authentication performance
        if 'authentication' in self.results:
            auth_stats = self.results['authentication']
            summary['authentication'] = {
                'mean_time_ms': auth_stats.get('mean_time', 0) * 1000,
                'success_rate': auth_stats.get('successful_runs', 0) / auth_stats.get('iterations', 1)
            }
        
        # Data processing scalability
        if 'data_processing' in self.results:
            processing_results = self.results['data_processing']
            scalability_factor = self._calculate_scalability_factor(processing_results)
            summary['data_processing_scalability'] = scalability_factor
        
        # Concurrency efficiency
        if 'concurrency' in self.results:
            concurrency_results = self.results['concurrency']
            efficiency = self._calculate_concurrency_efficiency(concurrency_results)
            summary['concurrency_efficiency'] = efficiency
        
        # Memory efficiency
        if 'memory_usage' in self.results:
            memory_results = self.results['memory_usage']
            memory_efficiency = self._calculate_memory_efficiency(memory_results)
            summary['memory_efficiency'] = memory_efficiency
        
        return summary
    
    def _calculate_scalability_factor(self, results: Dict[str, Any]) -> float:
        """Calculate scalability factor (lower is better)."""
        sizes = sorted([int(k) for k in results.keys() if isinstance(k, (int, str)) and str(k).isdigit()])
        
        if len(sizes) < 2:
            return 1.0
        
        # Calculate time per item for different sizes
        time_per_item = []
        for size in sizes:
            stats = results[size]
            if stats.get('successful_runs', 0) > 0:
                time_per_item.append(stats['mean_time'] / size)
        
        if len(time_per_item) < 2:
            return 1.0
        
        # Scalability factor: ratio of time per item at largest vs smallest size
        return time_per_item[-1] / time_per_item[0]
    
    def _calculate_concurrency_efficiency(self, results: Dict[str, Any]) -> float:
        """Calculate concurrency efficiency."""
        thread_counts = sorted([int(k) for k in results.keys() if isinstance(k, (int, str)) and str(k).isdigit()])
        
        if len(thread_counts) < 2:
            return 1.0
        
        # Get baseline (single thread) performance
        baseline_time = results[1].get('mean_time', 1.0) if 1 in results else 1.0
        
        # Calculate efficiency for highest thread count
        max_threads = max(thread_counts)
        max_thread_time = results[max_threads].get('mean_time', baseline_time)
        
        # Efficiency = (baseline_time / max_thread_time) / max_threads
        # Perfect efficiency would be 1.0
        return (baseline_time / max_thread_time) / max_threads
    
    def _calculate_memory_efficiency(self, results: Dict[str, Any]) -> float:
        """Calculate memory efficiency (MB per 1000 items)."""
        sizes = sorted([int(k) for k in results.keys() if isinstance(k, (int, str)) and str(k).isdigit()])
        
        if not sizes:
            return 0.0
        
        # Calculate average memory usage per item
        memory_per_item = []
        for size in sizes:
            stats = results[size]
            if stats.get('successful_runs', 0) > 0:
                memory_per_item.append(stats.get('mean_memory_delta', 0) / size)
        
        if not memory_per_item:
            return 0.0
        
        # Return memory usage per 1000 items
        return statistics.mean(memory_per_item) * 1000
    
    def _generate_recommendations(self) -> List[str]:
        """Generate performance recommendations."""
        recommendations = []
        summary = self._generate_summary()
        
        # Authentication recommendations
        if 'authentication' in summary:
            auth_time = summary['authentication'].get('mean_time_ms', 0)
            if auth_time > 1000:  # > 1 second
                recommendations.append(
                    "Consider implementing credential caching to improve authentication performance"
                )
        
        # Scalability recommendations
        if 'data_processing_scalability' in summary:
            scalability = summary['data_processing_scalability']
            if scalability > 2.0:
                recommendations.append(
                    "Data processing shows poor scalability. Consider implementing streaming or chunked processing"
                )
        
        # Concurrency recommendations
        if 'concurrency_efficiency' in summary:
            efficiency = summary['concurrency_efficiency']
            if efficiency < 0.3:
                recommendations.append(
                    "Low concurrency efficiency detected. Consider optimizing for CPU-bound vs I/O-bound operations"
                )
        
        # Memory recommendations
        if 'memory_efficiency' in summary:
            memory_per_1k = summary['memory_efficiency']
            if memory_per_1k > 100:  # > 100MB per 1000 items
                recommendations.append(
                    "High memory usage detected. Consider implementing data streaming or garbage collection optimization"
                )
        
        if not recommendations:
            recommendations.append("Performance looks good! No specific recommendations at this time.")
        
        return recommendations
    
    def print_report(self, report: Dict[str, Any]):
        """Print formatted benchmark report."""
        print("\n" + "=" * 80)
        print("GCP SERVICES PERFORMANCE BENCHMARK REPORT")
        print("=" * 80)
        
        # Metadata
        metadata = report['metadata']
        print(f"Timestamp: {metadata['timestamp']}")
        print(f"Duration: {metadata['duration_seconds']:.2f} seconds")
        print(f"System: {metadata['system_info']['cpu_count']} CPU cores, "
              f"{metadata['system_info']['memory_total_gb']:.1f}GB RAM")
        
        # Summary
        print("\n" + "-" * 40)
        print("PERFORMANCE SUMMARY")
        print("-" * 40)
        
        summary = report['summary']
        for metric, value in summary.items():
            if isinstance(value, dict):
                print(f"{metric}:")
                for k, v in value.items():
                    if isinstance(v, float):
                        print(f"  {k}: {v:.3f}")
                    else:
                        print(f"  {k}: {v}")
            else:
                if isinstance(value, float):
                    print(f"{metric}: {value:.3f}")
                else:
                    print(f"{metric}: {value}")
        
        # Recommendations
        print("\n" + "-" * 40)
        print("RECOMMENDATIONS")
        print("-" * 40)
        
        for i, rec in enumerate(report['recommendations'], 1):
            print(f"{i}. {rec}")
        
        # Detailed results
        print("\n" + "-" * 40)
        print("DETAILED RESULTS")
        print("-" * 40)
        
        for test_name, result in report['results'].items():
            print(f"\n{test_name.upper()}:")
            
            if isinstance(result, dict) and 'mean_time' in result:
                # Single benchmark result
                print(f"  Mean time: {result['mean_time']*1000:.2f}ms")
                print(f"  Success rate: {result['successful_runs']}/{result['iterations']}")
                if 'mean_memory_delta' in result:
                    print(f"  Memory delta: {result['mean_memory_delta']:.2f}MB")
            
            elif isinstance(result, dict):
                # Multiple results (scalability or concurrency)
                for key, stats in result.items():
                    if isinstance(stats, dict) and 'mean_time' in stats:
                        print(f"  {key}: {stats['mean_time']*1000:.2f}ms "
                              f"({stats['successful_runs']}/{stats['iterations']} success)")
    
    def save_report(self, report: Dict[str, Any], filename: str = None):
        """Save benchmark report to file."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"gcp_performance_benchmark_{timestamp}.json"
        
        report_file = Path(__file__).parent / filename
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"\n📊 Benchmark report saved to: {report_file}")


def main():
    """Main benchmark runner."""
    import argparse
    import unittest.mock
    
    parser = argparse.ArgumentParser(description='GCP Services Performance Benchmark')
    parser.add_argument('--output', '-o', help='Output file for benchmark report')
    parser.add_argument('--quick', action='store_true', help='Run quick benchmark (fewer iterations)')
    
    args = parser.parse_args()
    
    try:
        benchmark = PerformanceBenchmark()
        
        # Run comprehensive benchmark
        print("Starting performance benchmark...")
        results = benchmark.run_comprehensive_benchmark()
        
        # Generate and display report
        report = benchmark.generate_report()
        benchmark.print_report(report)
        
        # Save report
        benchmark.save_report(report, args.output)
        
        print("\n✅ Benchmark completed successfully!")
        
    except KeyboardInterrupt:
        print("\n⚠️  Benchmark interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Benchmark failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()