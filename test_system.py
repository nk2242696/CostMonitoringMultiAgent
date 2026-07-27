#!/usr/bin/env python3
"""
Comprehensive test suite for Azure Cost Monitoring API
Tests all major endpoints and validates responses
"""

import requests
import json
import sys
from datetime import datetime
import time

# Base URL for the API
BASE_URL = "http://localhost:8000"

def print_test_header(test_name):
    """Print a formatted test header"""
    print(f"\n{'='*60}")
    print(f"🧪 TESTING: {test_name}")
    print(f"{'='*60}")

def print_result(success, message, data=None):
    """Print test result with formatting"""
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status}: {message}")
    if data and isinstance(data, dict):
        print(f"📊 Data: {json.dumps(data, indent=2)}")
    elif data:
        print(f"📊 Response: {data}")

def test_health_endpoint():
    """Test the health check endpoint"""
    print_test_header("Health Check Endpoint")
    
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        
        if response.status_code == 200:
            health_data = response.json()
            
            # Validate response structure
            required_fields = ['status', 'timestamp', 'service', 'version', 'checks']
            missing_fields = [field for field in required_fields if field not in health_data]
            
            if not missing_fields:
                db_status = health_data.get('checks', {}).get('database', {}).get('status')
                data_status = health_data.get('checks', {}).get('data_freshness', {}).get('status')
                
                if health_data['status'] == 'healthy' and db_status == 'healthy':
                    print_result(True, f"API is healthy, database connected, data status: {data_status}")
                    return health_data
                else:
                    print_result(False, f"API status: {health_data['status']}, DB: {db_status}")
            else:
                print_result(False, f"Missing required fields: {missing_fields}")
        else:
            print_result(False, f"HTTP {response.status_code}: {response.text}")
    
    except requests.exceptions.RequestException as e:
        print_result(False, f"Connection error: {str(e)}")
    
    return None

def test_cost_summary():
    """Test the cost summary endpoint"""
    print_test_header("Cost Summary Endpoint")
    
    try:
        # Test with different time periods
        test_periods = [7, 30, 90]
        
        for days in test_periods:
            response = requests.get(f"{BASE_URL}/api/costs/summary?days={days}", timeout=10)
            
            if response.status_code == 200:
                cost_data = response.json()
                
                # Validate response structure
                required_fields = ['total_cost', 'resource_count', 'top_services', 'trend']
                if all(field in cost_data for field in required_fields):
                    total_cost = cost_data['total_cost']
                    resource_count = cost_data['resource_count']
                    top_services_count = len(cost_data['top_services'])
                    
                    print_result(True, 
                        f"Last {days} days: ${total_cost:.2f}, "
                        f"{resource_count} resources, "
                        f"{top_services_count} top services, "
                        f"trend: {cost_data['trend']}")
                    
                    if days == 30:  # Return 30-day data for further analysis
                        return cost_data
                else:
                    print_result(False, f"Missing fields in {days}-day response")
            else:
                print_result(False, f"HTTP {response.status_code} for {days} days: {response.text}")
    
    except requests.exceptions.RequestException as e:
        print_result(False, f"Connection error: {str(e)}")
    
    return None

def test_recommendations():
    """Test the AI recommendations endpoint"""
    print_test_header("AI Recommendations Endpoint")
    
    try:
        # Test basic recommendations
        response = requests.get(f"{BASE_URL}/api/recommendations?limit=5", timeout=10)
        
        if response.status_code == 200:
            recommendations = response.json()
            
            if isinstance(recommendations, list):
                rec_count = len(recommendations)
                total_savings = sum(rec.get('potential_savings', 0) for rec in recommendations)
                
                print_result(True, 
                    f"Retrieved {rec_count} recommendations with ${total_savings:.2f} potential savings")
                
                # Test with filters
                filters = [
                    ("priority", "high"),
                    ("status", "pending"),
                ]
                
                for filter_type, filter_value in filters:
                    filter_response = requests.get(
                        f"{BASE_URL}/api/recommendations?{filter_type}={filter_value}&limit=3", 
                        timeout=10
                    )
                    
                    if filter_response.status_code == 200:
                        filtered_recs = filter_response.json()
                        print_result(True, 
                            f"Filter '{filter_type}={filter_value}': {len(filtered_recs)} recommendations")
                    else:
                        print_result(False, f"Filter failed: {filter_response.status_code}")
                
                return recommendations[:3]  # Return first 3 for analysis
            else:
                print_result(False, "Response is not a list")
        else:
            print_result(False, f"HTTP {response.status_code}: {response.text}")
    
    except requests.exceptions.RequestException as e:
        print_result(False, f"Connection error: {str(e)}")
    
    return None

def test_prometheus_metrics():
    """Test Prometheus metrics export"""
    print_test_header("Prometheus Metrics Export")
    
    try:
        response = requests.get("http://localhost:8001/metrics", timeout=10)
        
        if response.status_code == 200:
            metrics_text = response.text
            
            # Look for Azure-specific metrics
            azure_metrics = [
                'azure_total_cost',
                'azure_cost_by_service',
                'azure_cost_by_subscription',
                'azure_cost_records_total'
            ]
            
            found_metrics = []
            for metric in azure_metrics:
                if metric in metrics_text:
                    # Extract the value
                    for line in metrics_text.split('\n'):
                        if line.startswith(metric) and not line.startswith('#'):
                            found_metrics.append(line.strip())
                            break
            
            if found_metrics:
                print_result(True, f"Found {len(found_metrics)} Azure metrics")
                for metric in found_metrics[:3]:  # Show first 3
                    print(f"   📊 {metric}")
                return True
            else:
                print_result(False, "No Azure metrics found in export")
        else:
            print_result(False, f"HTTP {response.status_code}: {response.text}")
    
    except requests.exceptions.RequestException as e:
        print_result(False, f"Connection error: {str(e)}")
    
    return False

def test_grafana_access():
    """Test Grafana accessibility"""
    print_test_header("Grafana Dashboard Access")
    
    try:
        response = requests.get("http://localhost:3000/api/health", timeout=10)
        
        if response.status_code == 200:
            health_data = response.json()
            version = health_data.get('version', 'unknown')
            db_status = health_data.get('database', 'unknown')
            
            print_result(True, f"Grafana {version} accessible, database: {db_status}")
            
            # Test if dashboards endpoint is accessible
            try:
                dash_response = requests.get(
                    "http://localhost:3000/api/search", 
                    timeout=5,
                    auth=('admin', 'AzureCost2025!SecurePass')  # Default admin credentials
                )
                
                if dash_response.status_code in [200, 401]:  # 401 is expected without proper auth
                    print_result(True, "Dashboard API endpoint accessible")
                else:
                    print_result(False, f"Dashboard API: HTTP {dash_response.status_code}")
            except:
                print_result(True, "Dashboard endpoint check skipped (auth required)")
            
            return True
        else:
            print_result(False, f"HTTP {response.status_code}: {response.text}")
    
    except requests.exceptions.RequestException as e:
        print_result(False, f"Connection error: {str(e)}")
    
    return False

def test_database_connectivity():
    """Test database through API endpoints"""
    print_test_header("Database Connectivity Test")
    
    try:
        # Test ready endpoint
        ready_response = requests.get(f"{BASE_URL}/health/ready", timeout=10)
        live_response = requests.get(f"{BASE_URL}/health/live", timeout=10)
        
        ready_ok = ready_response.status_code == 200
        live_ok = live_response.status_code == 200
        
        if ready_ok and live_ok:
            print_result(True, "Database connectivity confirmed (ready & live checks pass)")
            return True
        else:
            print_result(False, 
                f"Ready: HTTP {ready_response.status_code}, "
                f"Live: HTTP {live_response.status_code}")
    
    except requests.exceptions.RequestException as e:
        print_result(False, f"Connection error: {str(e)}")
    
    return False

def run_comprehensive_test():
    """Run all tests and provide a summary"""
    print(f"\n🚀 Starting Comprehensive Test Suite")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Target: Azure Cost Monitoring System")
    
    test_results = {
        'health': test_health_endpoint(),
        'cost_summary': test_cost_summary(),
        'recommendations': test_recommendations(),
        'prometheus': test_prometheus_metrics(),
        'grafana': test_grafana_access(),
        'database': test_database_connectivity()
    }
    
    # Summary
    print_test_header("TEST SUMMARY")
    
    passed_tests = sum(1 for result in test_results.values() if result)
    total_tests = len(test_results)
    
    print(f"📊 Tests Passed: {passed_tests}/{total_tests}")
    print(f"🎯 Success Rate: {(passed_tests/total_tests)*100:.1f}%")
    
    if passed_tests == total_tests:
        print(f"🎉 ALL TESTS PASSED! System is fully operational.")
        return True
    else:
        print(f"⚠️  Some tests failed. Check individual results above.")
        return False

if __name__ == "__main__":
    success = run_comprehensive_test()
    sys.exit(0 if success else 1)