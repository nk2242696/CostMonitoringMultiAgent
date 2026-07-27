#!/usr/bin/env python3
"""
Performance testing for Azure Cost Monitoring API
Tests response times and concurrent request handling
"""

import requests
import time
import threading
import statistics
from concurrent.futures import ThreadPoolExecutor
import json

BASE_URL = "http://localhost:8000"

def time_request(url, description):
    """Time a single request and return metrics"""
    start_time = time.time()
    try:
        response = requests.get(url, timeout=30)
        end_time = time.time()
        
        return {
            'description': description,
            'status_code': response.status_code,
            'response_time': end_time - start_time,
            'success': response.status_code == 200,
            'response_size': len(response.content)
        }
    except Exception as e:
        end_time = time.time()
        return {
            'description': description,
            'status_code': 0,
            'response_time': end_time - start_time,
            'success': False,
            'error': str(e),
            'response_size': 0
        }

def test_endpoint_performance():
    """Test individual endpoint performance"""
    print("⏱️ ENDPOINT PERFORMANCE TESTING")
    print("="*60)
    
    endpoints = [
        (f"{BASE_URL}/health", "Health Check"),
        (f"{BASE_URL}/api/costs/summary?days=7", "Cost Summary (7 days)"),
        (f"{BASE_URL}/api/costs/summary?days=30", "Cost Summary (30 days)"),
        (f"{BASE_URL}/api/recommendations?limit=5", "AI Recommendations"),
        ("http://localhost:8001/metrics", "Prometheus Metrics"),
    ]
    
    results = []
    
    for url, description in endpoints:
        print(f"\n🔍 Testing: {description}")
        
        # Run multiple requests to get average
        times = []
        for i in range(5):
            result = time_request(url, description)
            times.append(result['response_time'])
            
            status = "✅" if result['success'] else "❌"
            print(f"  Request {i+1}: {status} {result['response_time']*1000:.0f}ms "
                  f"({result.get('response_size', 0)} bytes)")
        
        # Calculate statistics
        avg_time = statistics.mean(times)
        min_time = min(times)
        max_time = max(times)
        
        print(f"  📊 Average: {avg_time*1000:.0f}ms, "
              f"Min: {min_time*1000:.0f}ms, "
              f"Max: {max_time*1000:.0f}ms")
        
        results.append({
            'endpoint': description,
            'avg_response_time': avg_time,
            'min_response_time': min_time,
            'max_response_time': max_time
        })
    
    return results

def concurrent_requests(url, num_requests=10):
    """Test concurrent requests to an endpoint"""
    results = []
    
    def make_request():
        return time_request(url, "Concurrent Test")
    
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(make_request) for _ in range(num_requests)]
        results = [future.result() for future in futures]
    
    end_time = time.time()
    
    return results, end_time - start_time

def test_concurrent_load():
    """Test concurrent request handling"""
    print("\n⚡ CONCURRENT LOAD TESTING")
    print("="*60)
    
    test_scenarios = [
        (f"{BASE_URL}/health", "Health Check", 20),
        (f"{BASE_URL}/api/costs/summary?days=30", "Cost Summary", 10),
        (f"{BASE_URL}/api/recommendations?limit=3", "Recommendations", 8),
    ]
    
    for url, description, num_requests in test_scenarios:
        print(f"\n🔥 Testing {description} with {num_requests} concurrent requests")
        
        results, total_time = concurrent_requests(url, num_requests)
        
        # Analyze results
        successful_requests = [r for r in results if r['success']]
        failed_requests = [r for r in results if not r['success']]
        
        if successful_requests:
            response_times = [r['response_time'] for r in successful_requests]
            avg_time = statistics.mean(response_times)
            min_time = min(response_times)
            max_time = max(response_times)
            
            requests_per_second = len(successful_requests) / total_time
            
            print(f"  ✅ Successful: {len(successful_requests)}/{num_requests}")
            print(f"  ⏱️ Average response time: {avg_time*1000:.0f}ms")
            print(f"  🚀 Requests/second: {requests_per_second:.1f}")
            print(f"  📈 Range: {min_time*1000:.0f}ms - {max_time*1000:.0f}ms")
        
        if failed_requests:
            print(f"  ❌ Failed requests: {len(failed_requests)}")

def test_data_volume_handling():
    """Test how well the API handles different data volumes"""
    print("\n📊 DATA VOLUME TESTING")
    print("="*60)
    
    # Test with different day ranges to see how performance scales
    day_ranges = [1, 7, 30, 90, 365]
    
    print("Testing cost summary with different time ranges:")
    
    for days in day_ranges:
        url = f"{BASE_URL}/api/costs/summary?days={days}"
        
        # Time multiple requests
        times = []
        for _ in range(3):
            result = time_request(url, f"Cost Summary ({days} days)")
            if result['success']:
                times.append(result['response_time'])
        
        if times:
            avg_time = statistics.mean(times)
            print(f"  📅 {days:3d} days: {avg_time*1000:6.0f}ms average")
        else:
            print(f"  📅 {days:3d} days: ❌ Failed")

def run_performance_tests():
    """Run all performance tests"""
    print("🚀 PERFORMANCE TEST SUITE")
    print("="*60)
    print(f"Target: Azure Cost Monitoring API")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Individual endpoint performance
    endpoint_results = test_endpoint_performance()
    
    # Concurrent load testing  
    test_concurrent_load()
    
    # Data volume testing
    test_data_volume_handling()
    
    # Summary
    print("\n📋 PERFORMANCE SUMMARY")
    print("="*60)
    
    # Show best and worst performing endpoints
    if endpoint_results:
        fastest = min(endpoint_results, key=lambda x: x['avg_response_time'])
        slowest = max(endpoint_results, key=lambda x: x['avg_response_time'])
        
        print(f"🏆 Fastest endpoint: {fastest['endpoint']} "
              f"({fastest['avg_response_time']*1000:.0f}ms avg)")
        print(f"🐌 Slowest endpoint: {slowest['endpoint']} "
              f"({slowest['avg_response_time']*1000:.0f}ms avg)")
        
        # Performance assessment
        max_acceptable_time = 2.0  # 2 seconds
        slow_endpoints = [r for r in endpoint_results 
                         if r['avg_response_time'] > max_acceptable_time]
        
        if not slow_endpoints:
            print("✅ All endpoints perform within acceptable limits (<2s)")
        else:
            print(f"⚠️ {len(slow_endpoints)} endpoint(s) exceed 2s response time")
    
    print("🎯 Performance testing completed!")

if __name__ == "__main__":
    run_performance_tests()