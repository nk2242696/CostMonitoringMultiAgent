#!/usr/bin/env python3
"""
Generate Real AI-Powered Recommendations using Azure OpenAI
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from openai import AzureOpenAI
import json

# Azure OpenAI configuration
AZURE_OPENAI_KEY = os.environ.get('AZURE_OPENAI_KEY')
AZURE_OPENAI_ENDPOINT = os.environ.get('AZURE_OPENAI_ENDPOINT', 'https://openai-opvc0011.openai.azure.com/')
AZURE_OPENAI_DEPLOYMENT = os.environ.get('AZURE_OPENAI_DEPLOYMENT', 'gpt-4o')

class RealAIRecommendationGenerator:
    """Generate real AI-powered recommendations using Azure OpenAI."""
    
    def __init__(self):
        """Initialize the AI recommendation generator."""
        if not AZURE_OPENAI_KEY:
            raise ValueError('AZURE_OPENAI_KEY environment variable is required')
        self.client = AzureOpenAI(
            api_key=AZURE_OPENAI_KEY,
            api_version="2024-02-15-preview",
            azure_endpoint=AZURE_OPENAI_ENDPOINT
        )
        self.db_config = {
            'host': 'localhost',
            'port': 5432,
            'database': 'azure_cost_dev',
            'user': 'postgres',
            'password': 'AzureCost2025!DbPass'
        }
    
    def get_cost_data(self):
        """Get cost data from database."""
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
                    COUNT(DISTINCT DATE(date)) as active_days
                FROM cost_records
                WHERE date >= NOW() - INTERVAL '30 days'
                GROUP BY service_name
                HAVING SUM(cost) > 10
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
    
    def generate_ai_recommendation(self, service_data):
        """Generate intelligent AI recommendation using advanced rule-based system."""
        service_name = service_data['service_name']
        total_cost = float(service_data['total_cost'])
        avg_cost = float(service_data['avg_cost'])
        active_days = service_data['active_days']
        resource_groups = service_data['resource_groups']
        
        # Use advanced rule-based AI system
        return self._generate_smart_recommendation(service_data)
    
    def _generate_smart_recommendation(self, service_data):
        """Generate smart recommendations using advanced analysis."""
        service_name = service_data['service_name']
        total_cost = float(service_data['total_cost'])
        avg_cost = float(service_data['avg_cost'])
        active_days = service_data['active_days']
        resource_groups = service_data['resource_groups']
        
        # Cost intensity analysis
        daily_cost = total_cost / max(active_days, 1)
        cost_tier = 'high' if total_cost > 20000 else 'medium' if total_cost > 10000 else 'low'
        
        prompt = f"""BACKUP: As an Azure cost optimization expert, analyze this service and provide specific, actionable recommendations:

Service: {service_name}
Total Cost (30 days): ${total_cost:,.2f}
Average Daily Cost: ${avg_cost:,.2f}
Active Days: {active_days}
Resource Groups: {resource_groups}

Provide a detailed JSON response with:
1. "title": A concise recommendation title (max 60 chars)
2. "description": Detailed explanation of the issue and why this recommendation matters (2-3 sentences)
3. "action_items": Array of 3-4 specific, actionable steps to implement
4. "potential_savings_percentage": Realistic percentage of cost that can be saved (10-50%)
5. "confidence_score": Your confidence in this recommendation (0.0-1.0)
6. "priority": "high", "medium", or "low" based on cost and impact
7. "implementation_effort": "low", "medium", or "high"
8. "category": One of: "rightsizing", "reserved-capacity", "storage-optimization", "cleanup", "scheduling", "configuration"

Focus on Azure-specific best practices. Be realistic about savings. Consider the actual cost when prioritizing.

Return ONLY valid JSON, no other text."""

        try:
            response = self.client.chat.completions.create(
                model=AZURE_OPENAI_DEPLOYMENT,
                messages=[
                    {"role": "system", "content": "You are an Azure cost optimization expert. Provide recommendations in valid JSON format only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            content = response.choices[0].message.content.strip()
            
            # Remove markdown code blocks if present
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            recommendation = json.loads(content)
            
            # Calculate savings
            savings_pct = recommendation.get('potential_savings_percentage', 20) / 100
            potential_savings = round(total_cost * savings_pct, 2)
            
            return {
                'service_name': service_name,
                'current_cost': total_cost,
                'potential_savings': potential_savings,
                'savings_percentage': round(savings_pct * 100, 2),
                'title': recommendation.get('title', 'Optimize Resource'),
                'description': recommendation.get('description', 'Cost optimization opportunity identified'),
                'recommendation_text': json.dumps(recommendation.get('action_items', [])),
                'priority': recommendation.get('priority', 'medium'),
                'confidence_score': recommendation.get('confidence_score', 0.85),
                'implementation_effort': recommendation.get('implementation_effort', 'medium'),
                'category': recommendation.get('category', 'optimization'),
                'status': 'pending',
                'source': 'openai-gpt4'
            }
            
        except json.JSONDecodeError as e:
            print(f"⚠️  JSON parse error for {service_name}: {e}")
            print(f"Response: {content[:200]}")
            return None
        except Exception as e:
            print(f"❌ OpenAI error for {service_name}: {e}")
            return None
    
    def save_recommendation(self, rec):
        """Save recommendation to database."""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            query = """
                INSERT INTO ai_recommendations (
                    resource_id, recommendation_type, title, description,
                    potential_savings, confidence_score, priority,
                    service_name, current_cost, savings_percentage,
                    recommendation_text, implementation_effort, category,
                    status, source
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """
            
            resource_id = f"/subscriptions/518f04e9-2b37-457e-b852-8f058cb3f160/services/{rec['service_name']}"
            
            cursor.execute(query, (
                resource_id,
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
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            return True
            
        except Exception as e:
            print(f"❌ Save error: {e}")
            return False
    
    def generate_all_recommendations(self):
        """Generate recommendations for all services."""
        print("🤖 REAL AI RECOMMENDATION GENERATOR (OpenAI GPT-4)")
        print("=" * 60)
        
        # Clear old recommendations
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM ai_recommendations WHERE source = 'openai-gpt4' OR source IS NULL")
            deleted = cursor.rowcount
            conn.commit()
            cursor.close()
            conn.close()
            print(f"🗑️  Cleared {deleted} old recommendations\n")
        except Exception as e:
            print(f"⚠️  Clear error: {e}\n")
        
        # Get cost data
        print("📊 Fetching cost data from last 30 days...")
        services = self.get_cost_data()
        
        if not services:
            print("❌ No cost data found")
            return
        
        print(f"🎯 Found {len(services)} services for AI analysis:\n")
        for svc in services:
            print(f"   • {svc['service_name']}: ${svc['total_cost']}")
        
        print("\n" + "=" * 60)
        
        # Generate recommendations using OpenAI
        total_savings = 0
        successful = 0
        
        for i, service in enumerate(services, 1):
            print(f"\n🧠 Generating AI recommendation {i}/{len(services)} for {service['service_name']}...")
            
            recommendation = self.generate_ai_recommendation(service)
            
            if recommendation:
                if self.save_recommendation(recommendation):
                    print(f"✅ Saved: {recommendation['title']}")
                    print(f"   💰 Potential Savings: ${recommendation['potential_savings']:,.2f} ({recommendation['savings_percentage']:.1f}%)")
                    print(f"   🎯 Priority: {recommendation['priority']} | Effort: {recommendation['implementation_effort']}")
                    total_savings += recommendation['potential_savings']
                    successful += 1
                else:
                    print(f"❌ Failed to save recommendation")
            else:
                print(f"❌ Failed to generate recommendation")
        
        print("\n" + "=" * 60)
        print(f"🎉 AI GENERATION COMPLETE!")
        print(f"📈 Successfully generated {successful}/{len(services)} recommendations")
        print(f"💰 Total potential savings: ${total_savings:,.2f}")
        print(f"\n✅ Real AI-powered recommendations are now active!")
        print(f"🌐 View in Grafana: http://localhost:3000")


if __name__ == "__main__":
    generator = RealAIRecommendationGenerator()
    generator.generate_all_recommendations()
