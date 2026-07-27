#!/usr/bin/env python3
"""
Database testing script for Azure Cost Monitoring
Direct database queries to validate data integrity
"""

import subprocess
import json

def run_db_query(query, description):
    """Execute a database query via Docker"""
    print(f"\n🔍 {description}")
    print("-" * 60)
    
    cmd = [
        "docker", "exec", "azure-cost-db", 
        "psql", "-U", "postgres", "-d", "azure_cost_dev", 
        "-c", query
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print(result.stdout)
            return True
        else:
            print(f"❌ Error: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return False

def test_database():
    """Run comprehensive database tests"""
    print("🗄️ DATABASE TESTING SUITE")
    print("="*60)
    
    # Test queries
    tests = [
        # Data overview
        ("""SELECT 
            COUNT(*) as total_records,
            ROUND(SUM(cost)::numeric, 2) as total_cost,
            MIN(date) as earliest_date,
            MAX(date) as latest_date,
            COUNT(DISTINCT subscription_id) as subscriptions,
            COUNT(DISTINCT service_name) as services
        FROM cost_records;""", 
         "📊 Cost Records Overview"),
        
        # Service breakdown
        ("""SELECT 
            service_name,
            COUNT(*) as record_count,
            ROUND(SUM(cost)::numeric, 2) as total_cost,
            ROUND(AVG(cost)::numeric, 2) as avg_cost
        FROM cost_records 
        GROUP BY service_name 
        ORDER BY total_cost DESC 
        LIMIT 10;""", 
         "🏷️ Top 10 Services by Cost"),
        
        # Monthly trends
        ("""SELECT 
            DATE_TRUNC('month', date) as month,
            COUNT(*) as records,
            ROUND(SUM(cost)::numeric, 2) as total_cost
        FROM cost_records 
        GROUP BY DATE_TRUNC('month', date) 
        ORDER BY month;""", 
         "📈 Monthly Cost Trends"),
        
        # AI recommendations data
        ("""SELECT 
            COUNT(*) as total_recommendations,
            ROUND(SUM(potential_savings)::numeric, 2) as total_potential_savings,
            COUNT(*) FILTER (WHERE priority = 'high') as high_priority,
            COUNT(*) FILTER (WHERE status = 'pending') as pending_status
        FROM ai_recommendations;""", 
         "🤖 AI Recommendations Summary"),
        
        # Recent data freshness
        ("""SELECT 
            'cost_records' as table_name,
            COUNT(*) as records_last_7_days
        FROM cost_records 
        WHERE created_at >= NOW() - INTERVAL '7 days'
        UNION ALL
        SELECT 
            'ai_recommendations' as table_name,
            COUNT(*) as records_last_7_days
        FROM ai_recommendations 
        WHERE generated_at >= NOW() - INTERVAL '7 days';""", 
         "🕐 Data Freshness Check"),
        
        # Table sizes
        ("""SELECT 
            schemaname,
            tablename,
            attname as column_name,
            n_distinct,
            null_frac
        FROM pg_stats 
        WHERE schemaname = 'public' 
        AND tablename IN ('cost_records', 'ai_recommendations')
        ORDER BY tablename, attname;""", 
         "📋 Table Statistics")
    ]
    
    success_count = 0
    total_tests = len(tests)
    
    for query, description in tests:
        if run_db_query(query, description):
            success_count += 1
        
    print(f"\n{'='*60}")
    print(f"📊 DATABASE TEST SUMMARY")
    print(f"{'='*60}")
    print(f"✅ Passed: {success_count}/{total_tests}")
    print(f"🎯 Success Rate: {(success_count/total_tests)*100:.1f}%")
    
    if success_count == total_tests:
        print("🎉 All database tests passed!")
        return True
    else:
        print("⚠️ Some database tests failed.")
        return False

if __name__ == "__main__":
    test_database()