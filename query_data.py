#!/usr/bin/env python3
"""
Direct data querying script for Azure Cost Monitoring
Run with: python query_data.py
"""

from src.common.database import get_session
from src.monitoring.storage.models import CostRecord, AIRecommendation
from sqlalchemy import func, desc
import pandas as pd

def query_cost_summary():
    """Get cost summary with top services."""
    session = next(get_session())
    
    print("🎯 COST SUMMARY")
    print("=" * 50)
    
    # Total cost and record count
    total_cost = session.query(func.sum(CostRecord.cost)).scalar() or 0
    record_count = session.query(CostRecord).count()
    
    print(f"📊 Total Records: {record_count:,}")
    print(f"💰 Total Cost: ${total_cost:.2f}")
    print(f"📅 Average per Record: ${total_cost/record_count:.4f}")
    
    # Top services by cost
    print(f"\n🏆 TOP 5 SERVICES BY COST:")
    print("-" * 30)
    
    top_services = session.query(
        CostRecord.service_name,
        func.sum(CostRecord.cost).label('total_cost'),
        func.count(CostRecord.id).label('record_count')
    ).group_by(
        CostRecord.service_name
    ).order_by(
        desc('total_cost')
    ).limit(5).all()
    
    for i, (service, cost, count) in enumerate(top_services, 1):
        print(f"{i}. {service}: ${cost:.2f} ({count} records)")
    
    session.close()

def query_ai_recommendations():
    """Get AI recommendations summary."""
    session = next(get_session())
    
    print(f"\n🤖 AI RECOMMENDATIONS")
    print("=" * 50)
    
    recommendations = session.query(AIRecommendation).all()
    
    if not recommendations:
        print("❌ No recommendations found")
        session.close()
        return
    
    total_savings = sum(rec.potential_savings for rec in recommendations)
    print(f"📈 Total Recommendations: {len(recommendations)}")
    print(f"💰 Total Potential Savings: ${total_savings:.2f}")
    
    print(f"\n📋 RECOMMENDATIONS BY PRIORITY:")
    print("-" * 40)
    
    # Group by priority
    by_priority = {}
    for rec in recommendations:
        priority = rec.priority
        if priority not in by_priority:
            by_priority[priority] = []
        by_priority[priority].append(rec)
    
    for priority in ['high', 'medium', 'low']:
        if priority in by_priority:
            recs = by_priority[priority]
            print(f"\n🎯 {priority.upper()} PRIORITY ({len(recs)} recommendations):")
            for rec in recs:
                print(f"  • {rec.service_name}: ${rec.potential_savings:.2f} savings")
                print(f"    '{rec.title}'")
    
    session.close()

def query_date_range_analysis():
    """Analyze costs by date range."""
    session = next(get_session())
    
    print(f"\n📅 DATE RANGE ANALYSIS")
    print("=" * 50)
    
    # Date range
    date_range = session.query(
        func.min(CostRecord.date).label('start_date'),
        func.max(CostRecord.date).label('end_date')
    ).first()
    
    print(f"📅 Data Range: {date_range.start_date} to {date_range.end_date}")
    
    # Daily costs
    daily_costs = session.query(
        CostRecord.date,
        func.sum(CostRecord.cost).label('daily_cost')
    ).group_by(
        CostRecord.date
    ).order_by(
        CostRecord.date
    ).limit(7).all()  # Last 7 days
    
    print(f"\n📊 RECENT DAILY COSTS:")
    print("-" * 25)
    for date, cost in daily_costs:
        print(f"{date}: ${cost:.2f}")
    
    session.close()

def export_to_csv():
    """Export data to CSV files."""
    session = next(get_session())
    
    print(f"\n📄 EXPORTING DATA TO CSV")
    print("=" * 50)
    
    try:
        # Export cost records
        cost_query = """
        SELECT 
            date,
            service_name,
            resource_id,
            cost,
            currency,
            region,
            created_at
        FROM cost_records 
        ORDER BY date DESC, cost DESC
        """
        
        cost_df = pd.read_sql(cost_query, session.bind)
        cost_df.to_csv('cost_data.csv', index=False)
        print(f"✅ Exported {len(cost_df)} cost records to 'cost_data.csv'")
        
        # Export AI recommendations
        rec_query = """
        SELECT 
            service_name,
            current_cost,
            potential_savings,
            savings_percentage,
            title,
            priority,
            category,
            source,
            status,
            generated_at
        FROM ai_recommendations 
        ORDER BY potential_savings DESC
        """
        
        rec_df = pd.read_sql(rec_query, session.bind)
        rec_df.to_csv('recommendations.csv', index=False)
        print(f"✅ Exported {len(rec_df)} recommendations to 'recommendations.csv'")
        
    except Exception as e:
        print(f"❌ Export failed: {e}")
    
    session.close()

def custom_query():
    """Run a custom SQL query."""
    print(f"\n🔍 CUSTOM QUERY EXAMPLE")
    print("=" * 50)
    
    session = next(get_session())
    
    # Example: Find services with costs above average
    query = """
    WITH avg_cost AS (
        SELECT AVG(cost) as avg_value FROM cost_records
    )
    SELECT 
        service_name,
        COUNT(*) as records,
        SUM(cost) as total_cost,
        AVG(cost) as avg_cost,
        MAX(cost) as max_cost
    FROM cost_records, avg_cost
    WHERE cost > avg_value
    GROUP BY service_name
    ORDER BY total_cost DESC;
    """
    
    result = session.execute(query).fetchall()
    
    print("🎯 SERVICES WITH ABOVE-AVERAGE COSTS:")
    print("-" * 45)
    print(f"{'Service':<25} {'Records':<8} {'Total':<10} {'Avg':<8} {'Max':<8}")
    print("-" * 45)
    
    for row in result:
        print(f"{row[0]:<25} {row[1]:<8} ${row[2]:<9.2f} ${row[3]:<7.4f} ${row[4]:<7.2f}")
    
    session.close()

if __name__ == "__main__":
    print("🎯 AZURE COST MONITORING - DATA ANALYSIS")
    print("=" * 60)
    
    try:
        query_cost_summary()
        query_ai_recommendations()
        query_date_range_analysis()
        custom_query()
        
        # Uncomment to export data
        # export_to_csv()
        
        print(f"\n✅ Analysis complete!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Make sure your Docker containers are running!")