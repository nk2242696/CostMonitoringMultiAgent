#!/usr/bin/env python3
"""
Generate REAL Azure OpenAI Recommendations - No Dummy Data
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
import requests
import json
from datetime import datetime

# Azure OpenAI Configuration
AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")

# Try common endpoint patterns
POSSIBLE_ENDPOINTS = [
    "https://kuamnuii.openai.azure.com/",
    "https://kuamnuii.openai.azure.com",
]

DEPLOYMENT_NAME = "gpt-4o"
API_VERSION = "2024-02-15-preview"

class RealAzureAIGenerator:
    def __init__(self):
        if not AZURE_OPENAI_KEY:
            raise ValueError("AZURE_OPENAI_KEY environment variable is required")
        self.api_key = AZURE_OPENAI_KEY
        self.endpoint = None
        self.db_config = {
            'host': 'localhost',
            'port': 5432,
            'database': 'azure_cost_dev',
            'user': 'postgres',
            'password': 'AzureCost2025!DbPass'
        }
        
    def test_endpoint(self, endpoint):
        """Test if endpoint is accessible."""
        url = f"{endpoint.rstrip('/')}/openai/deployments/{DEPLOYMENT_NAME}/chat/completions?api-version={API_VERSION}"
        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "messages": [{"role": "user", "content": "test"}],
            "max_tokens": 10
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            if response.status_code in [200, 400]:  # 400 is ok, means auth works
                return True
        except:
            pass
        return False
    
    def find_working_endpoint(self):
        """Find working Azure OpenAI endpoint."""
        print("🔍 Testing Azure OpenAI endpoints...")
        for endpoint in POSSIBLE_ENDPOINTS:
            print(f"   Testing: {endpoint}")
            if self.test_endpoint(endpoint):
                print(f"   ✅ Found working endpoint: {endpoint}")
                self.endpoint = endpoint
                return True
        print("   ❌ No working endpoint found")
        return False
    
    def get_real_cost_data(self):
        """Get REAL cost data from database - NO DUMMY DATA."""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            query = """
                SELECT 
                    service_name,
                    ROUND(SUM(cost)::numeric, 2) as total_cost,
                    COUNT(*) as record_count,
                    ROUND(AVG(cost)::numeric, 2) as avg_cost,
                    COUNT(DISTINCT resource_group) as resource_groups,
                    COUNT(DISTINCT resource_name) as resource_count,
                    COUNT(DISTINCT DATE(date)) as active_days,
                    ROUND(MIN(cost)::numeric, 2) as min_cost,
                    ROUND(MAX(cost)::numeric, 2) as max_cost
                FROM cost_records
                WHERE date >= NOW() - INTERVAL '30 days'
                GROUP BY service_name
                HAVING SUM(cost) > 100
                ORDER BY total_cost DESC
                LIMIT 10;
            """
            
            cursor.execute(query)
            results = cursor.fetchall()
            cursor.close()
            conn.close()
            
            return [dict(row) for row in results]
        except Exception as e:
            print(f"❌ Database error: {e}")
            return []
    
    def call_azure_openai(self, prompt):
        """Call Azure OpenAI API with REAL data."""
        if not self.endpoint:
            raise Exception("No working endpoint found")
        
        url = f"{self.endpoint.rstrip('/')}/openai/deployments/{DEPLOYMENT_NAME}/chat/completions?api-version={API_VERSION}"
        
        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": "You are an Azure cost optimization expert. Analyze the provided REAL cost data and provide specific, actionable recommendations. Return ONLY valid JSON."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.7,
            "max_tokens": 1500,
            "response_format": {"type": "json_object"}
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            raise Exception(f"API error: {response.status_code} - {response.text}")
    
    def generate_real_recommendation(self, service_data):
        """Generate REAL AI recommendation using Azure OpenAI."""
        service_name = service_data['service_name']
        total_cost = float(service_data['total_cost'])
        avg_cost = float(service_data['avg_cost'])
        resource_count = service_data['resource_count']
        active_days = service_data['active_days']
        min_cost = float(service_data['min_cost'])
        max_cost = float(service_data['max_cost'])
        
        prompt = f"""Analyze this REAL Azure cost data and provide a detailed optimization recommendation:

Service: {service_name}
Total Cost (30 days): ${total_cost:,.2f}
Number of Resources: {resource_count}
Active Days: {active_days}
Average Daily Cost: ${avg_cost:,.2f}
Cost Range: ${min_cost:,.2f} - ${max_cost:,.2f}

This is REAL production data from an actual Azure subscription. Provide:

{{
    "title": "Specific recommendation title (max 80 chars)",
    "description": "Detailed explanation based on the actual cost patterns and resource count",
    "action_items": ["Step 1", "Step 2", "Step 3"],
    "potential_savings_percentage": realistic_number_between_10_and_50,
    "confidence_score": number_between_0_and_1,
    "priority": "high|medium|low",
    "implementation_effort": "low|medium|high",
    "category": "rightsizing|reserved-capacity|storage-optimization|cleanup|scheduling|configuration"
}}

Base your savings estimate on the actual cost data. Be specific about what to optimize based on the resource count and cost patterns."""
        
        try:
            response_text = self.call_azure_openai(prompt)
            recommendation = json.loads(response_text)
            
            # Calculate real savings
            savings_pct = recommendation.get('potential_savings_percentage', 20) / 100
            potential_savings = round(total_cost * savings_pct, 2)
            
            return {
                'service_name': service_name,
                'current_cost': total_cost,
                'potential_savings': potential_savings,
                'savings_percentage': round(savings_pct * 100, 2),
                'title': recommendation['title'],
                'description': recommendation['description'],
                'recommendation_text': json.dumps(recommendation['action_items']),
                'priority': recommendation['priority'],
                'confidence_score': recommendation['confidence_score'],
                'implementation_effort': recommendation['implementation_effort'],
                'category': recommendation['category'],
                'status': 'pending',
                'source': 'azure_openai_real'
            }
        except Exception as e:
            print(f"❌ Azure OpenAI error: {e}")
            return None
    
    def save_recommendation(self, rec):
        """Save REAL recommendation to database."""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            query = """
                INSERT INTO ai_recommendations (
                    resource_id, recommendation_type, title, description,
                    potential_savings, confidence_score, priority,
                    service_name, current_cost, savings_percentage,
                    recommendation_text, implementation_effort, category, status, source
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """
            
            values = (
                f"/subscriptions/518f04e9-2b37-457e-b852-8f058cb3f160/services/{rec['service_name']}",
                rec['category'],
                rec['title'],
                rec['description'],
                rec['potential_savings'],
                rec['confidence_score'],
                rec['priority'],
                rec['service_name'],
                rec['current_cost'],
                rec['savings_percentage'],
                rec['recommendation_text'],
                rec['implementation_effort'],
                rec['category'],
                rec['status'],
                rec['source']
            )
            
            cursor.execute(query, values)
            conn.commit()
            cursor.close()
            conn.close()
            return True
        except Exception as e:
            print(f"❌ Database save error: {e}")
            return False
    
    def run(self):
        """Run REAL Azure OpenAI recommendation generation."""
        print("🤖 REAL AZURE OPENAI RECOMMENDATION GENERATOR")
        print("=" * 60)
        print("📌 NO DUMMY DATA - ALL REAL PRODUCTION DATA\n")
        
        # Find working endpoint
        if not self.find_working_endpoint():
            print("\n❌ Cannot connect to Azure OpenAI. Check:")
            print("   1. API key is correct")
            print("   2. Endpoint URL is accessible")
            print("   3. Deployment name 'gpt-4o' exists")
            return
        
        # Clear old recommendations
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM ai_recommendations WHERE source = 'azure_openai_real' OR source IS NULL;")
            deleted = cursor.rowcount
            conn.commit()
            cursor.close()
            conn.close()
            print(f"🗑️  Cleared {deleted} old recommendations\n")
        except Exception as e:
            print(f"⚠️  Warning: {e}\n")
        
        # Get REAL cost data
        print("📊 Fetching REAL cost data from database...")
        services = self.get_real_cost_data()
        
        if not services:
            print("❌ No cost data found in database")
            return
        
        print(f"✅ Found {len(services)} services with real cost data:\n")
        total_cost = sum(float(s['total_cost']) for s in services)
        for s in services:
            print(f"   • {s['service_name']}: ${float(s['total_cost']):,.2f}")
        print(f"\n💰 Total Cost: ${total_cost:,.2f}")
        print("=" * 60)
        
        # Generate REAL AI recommendations
        successful = 0
        total_savings = 0
        
        for i, service in enumerate(services, 1):
            print(f"\n🧠 Generating REAL AI recommendation {i}/{len(services)} for {service['service_name']}...")
            
            rec = self.generate_real_recommendation(service)
            
            if rec and self.save_recommendation(rec):
                print(f"✅ Generated: {rec['title']}")
                print(f"   💰 Savings: ${rec['potential_savings']:,.2f} ({rec['savings_percentage']}%)")
                print(f"   🎯 Priority: {rec['priority']} | Effort: {rec['implementation_effort']}")
                successful += 1
                total_savings += rec['potential_savings']
            else:
                print(f"❌ Failed to generate recommendation")
        
        print("\n" + "=" * 60)
        print(f"🎉 REAL AI GENERATION COMPLETE!")
        print(f"✅ Successfully generated {successful}/{len(services)} recommendations")
        print(f"💰 Total potential savings: ${total_savings:,.2f}")
        print(f"\n🌐 View in Grafana: http://localhost:3000")
        print("📌 All recommendations are based on REAL Azure OpenAI analysis")

if __name__ == "__main__":
    generator = RealAzureAIGenerator()
    generator.run()
