"""
Quick test script for Architecture Review API integration
"""
import requests
import json
from datetime import datetime


def test_architecture_review():
    """Test the architecture review API endpoint"""
    
    API_BASE = "http://localhost:8000"
    
    problem_statement = """
We need to enhance our existing Azure cost monitoring system.

CURRENT SETUP:
- Python backend (FastAPI) running in Docker
- PostgreSQL database storing cost data
- Grafana for visualization
- Collecting costs from 5-10 Azure subscriptions
- Multi-agent chat system using Azure OpenAI (gpt-4o)
- Redis for caching
- Celery for background tasks

NEW REQUIREMENTS:
- Scale to 50+ Azure subscriptions (currently 5-10)
- Add predictive cost forecasting (ML-based)
- Implement automated budget alerts with Slack/Teams integration
- Add compliance scanning (unused resources, untagged resources)
- Improve query performance (currently slow on 6+ months of data)
- Add multi-tenancy support (different teams/business units)
- Deploy to production on Azure (currently local Docker only)
- Support 100+ concurrent users (currently ~10)

CONSTRAINTS:
- Budget: $2000-3000/month for Azure infrastructure
- Team: 2 engineers, limited DevOps experience
- Timeline: 3 months to production
- Must maintain current functionality during migration
- Security: SOC 2 compliance required
- Data retention: 2 years of cost history

TECHNICAL DEBT:
- No automated testing
- Manual deployments
- No proper CI/CD
- Database not optimized (full table scans)
- No monitoring/alerting for the monitoring system itself

GOALS:
1. Migrate to Azure with proper architecture
2. Improve performance 10x
3. Reduce operational overhead
4. Keep costs under control
"""
    
    print("="*80)
    print("🚀 Testing Architecture Review API")
    print("="*80)
    print()
    
    # Test 1: Health check
    print("1. Testing health endpoint...")
    try:
        response = requests.get(f"{API_BASE}/health")
        print(f"   ✅ Health check: {response.status_code}")
        print(f"   Status: {response.json()['status']}")
    except Exception as e:
        print(f"   ❌ Health check failed: {str(e)}")
        return
    
    print()
    
    # Test 2: Run architecture review
    print("2. Running architecture review...")
    print("   (This will take 2-3 minutes...)")
    
    try:
        response = requests.post(
            f"{API_BASE}/architecture/review",
            json={"problem_statement": problem_statement},
            timeout=300  # 5 minute timeout
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Review completed!")
            print(f"   Review ID: {data['review_id']}")
            print(f"   Generated at: {data['generated_at']}")
            print()
            print("   📄 Files created:")
            for file_type, file_path in data['files'].items():
                print(f"      - {file_type}: {file_path}")
            
            # Show preview of decision
            print()
            print("   📋 Decision Preview:")
            print("   " + "-"*76)
            decision_lines = data['decision'].split('\n')[:10]
            for line in decision_lines:
                print(f"   {line}")
            print("   " + "-"*76)
            
            return data['review_id']
        else:
            print(f"   ❌ Review failed: {response.status_code}")
            print(f"   Error: {response.text}")
            return None
            
    except Exception as e:
        print(f"   ❌ Review failed: {str(e)}")
        return None
    
    print()


def test_list_reviews(api_base="http://localhost:8000"):
    """Test listing architecture reviews"""
    print("3. Listing recent reviews...")
    
    try:
        response = requests.get(f"{api_base}/architecture/reviews")
        data = response.json()
        
        print(f"   ✅ Found {data['count']} reviews")
        
        if data['count'] > 0:
            print()
            print("   Recent reviews:")
            for review in data['reviews'][:5]:
                print(f"      - {review['review_id']} (created: {review['created_at']})")
        
    except Exception as e:
        print(f"   ❌ Failed to list reviews: {str(e)}")
    
    print()


def test_get_review(review_id, api_base="http://localhost:8000"):
    """Test getting a specific review"""
    print(f"4. Getting review {review_id}...")
    
    try:
        response = requests.get(f"{api_base}/architecture/review/{review_id}")
        data = response.json()
        
        print(f"   ✅ Retrieved review")
        print(f"   Files available: {', '.join(data['files'].keys())}")
        
    except Exception as e:
        print(f"   ❌ Failed to get review: {str(e)}")
    
    print()


def print_next_steps():
    """Print next steps for user"""
    print()
    print("="*80)
    print("✅ Integration Complete!")
    print("="*80)
    print()
    print("📍 Next Steps:")
    print()
    print("1. Start the API server:")
    print("   python -m uvicorn src.monitoring.api.main:app --reload --port 8000")
    print()
    print("2. Open the Architecture Review UI:")
    print("   http://localhost:8000/static/architecture_review.html")
    print()
    print("3. Use the API endpoints:")
    print("   POST   /architecture/review          - Run new review")
    print("   GET    /architecture/reviews         - List all reviews")
    print("   GET    /architecture/review/{id}     - Get specific review")
    print("   GET    /architecture/review/{id}/download/{type} - Download file")
    print()
    print("4. Integrate with Grafana:")
    print("   - Add iframe panel with URL: http://localhost:8000/static/architecture_review.html")
    print("   - Or use Text panel with Markdown linking to review results")
    print()
    print("5. Integrate with existing chat system:")
    print("   - Add 'architecture review' command to chat bot")
    print("   - Trigger reviews based on cost anomalies or budget alerts")
    print()


if __name__ == "__main__":
    print()
    print("🤖 Architecture Review API Integration Test")
    print()
    print("This script tests the integration of the three-agent architecture")
    print("review system with your existing cost monitoring platform.")
    print()
    
    input("Press Enter to start the test (make sure API is running on port 8000)...")
    print()
    
    review_id = test_architecture_review()
    test_list_reviews()
    
    if review_id:
        test_get_review(review_id)
    
    print_next_steps()
