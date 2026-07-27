"""
Azure Cost Data Collection Script
Collects real cost data from Azure subscriptions and stores in database
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from typing import List, Dict
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.monitoring.azure_cost_collector import AzureCostCollector
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, text
from sqlalchemy.orm import declarative_base, sessionmaker

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

Base = declarative_base()


class AzureCost(Base):
    """Azure cost data model"""
    __tablename__ = 'azure_costs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    subscription_id = Column(String(100), nullable=False, index=True)
    subscription_name = Column(String(255))
    service_name = Column(String(255), nullable=False, index=True)
    resource_group = Column(String(255))
    resource_id = Column(String(500))
    cost = Column(Float, nullable=False)
    currency = Column(String(10), default='USD')
    date = Column(DateTime, nullable=False, index=True)
    period_type = Column(String(50))  # daily, monthly, current_month
    collected_at = Column(DateTime, default=datetime.utcnow)


def init_database():
    """Initialize database tables"""
    database_url = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/azure_cost_dev')
    engine = create_engine(database_url)
    
    logger.info("Creating database tables if they don't exist...")
    Base.metadata.create_all(engine)
    
    return engine


def collect_subscription_costs(
    collector: AzureCostCollector,
    subscription: Dict,
    session
) -> int:
    """
    Collect and store costs for a single subscription
    
    Returns:
        Number of records inserted
    """
    sub_id = subscription['subscription_id']
    sub_name = subscription['display_name']
    
    logger.info(f"\n{'='*70}")
    logger.info(f"Processing: {sub_name}")
    logger.info(f"Subscription ID: {sub_id}")
    logger.info(f"{'='*70}")
    
    records_inserted = 0
    
    try:
        # 1. Get current month costs by service
        logger.info("📊 Fetching current month costs by service...")
        service_costs = collector.get_current_month_costs_by_service(sub_id)
        
        for service in service_costs:
            cost_record = AzureCost(
                subscription_id=sub_id,
                subscription_name=sub_name,
                service_name=service['service_name'],
                cost=service['current_cost'],
                currency=service['currency'],
                date=datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0),
                period_type='current_month'
            )
            session.add(cost_record)
            records_inserted += 1
        
        logger.info(f"✅ Stored {len(service_costs)} service cost records")
        
        # 2. Get daily costs for the last 7 days
        logger.info("📊 Fetching last 7 days daily costs...")
        start_date = datetime.now() - timedelta(days=7)
        daily_costs = collector.get_cost_data(
            subscription_id=sub_id,
            start_date=start_date,
            granularity="Daily"
        )
        
        for daily in daily_costs:
            # Parse date if it's a string or integer
            cost_date = daily['date']
            if isinstance(cost_date, int):
                # Convert from format like 20251031 to datetime
                try:
                    date_str = str(cost_date)
                    cost_date = datetime.strptime(date_str, '%Y%m%d')
                except:
                    cost_date = datetime.now()
            elif isinstance(cost_date, str):
                try:
                    cost_date = datetime.strptime(cost_date.split('T')[0], '%Y-%m-%d')
                except:
                    cost_date = datetime.now()
            elif not isinstance(cost_date, datetime):
                cost_date = datetime.now()
            
            cost_record = AzureCost(
                subscription_id=sub_id,
                subscription_name=sub_name,
                service_name=daily['service_name'],
                resource_group=daily.get('resource_group'),
                cost=daily['cost'],
                currency=daily['currency'],
                date=cost_date,
                period_type='daily'
            )
            session.add(cost_record)
            records_inserted += 1
        
        logger.info(f"✅ Stored {len(daily_costs)} daily cost records")
        
        # 3. Get top resource costs
        logger.info("📊 Fetching resource-level costs...")
        resource_costs = collector.get_resource_costs(sub_id)
        
        # Store top 50 resources to avoid too much data
        for resource in resource_costs[:50]:
            cost_record = AzureCost(
                subscription_id=sub_id,
                subscription_name=sub_name,
                service_name=resource['service_name'],
                resource_group=resource['resource_group'],
                resource_id=resource['resource_id'],
                cost=resource['cost'],
                currency=resource['currency'],
                date=datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0),
                period_type='resource_monthly'
            )
            session.add(cost_record)
            records_inserted += 1
        
        logger.info(f"✅ Stored {min(50, len(resource_costs))} resource cost records")
        
        # Commit all records for this subscription
        session.commit()
        
        # Print summary
        total_current_month_cost = sum(s['current_cost'] for s in service_costs)
        logger.info(f"\n💰 Summary for {sub_name}:")
        logger.info(f"   - Current month total: ${total_current_month_cost:,.2f}")
        logger.info(f"   - Services tracked: {len(service_costs)}")
        logger.info(f"   - Resources tracked: {min(50, len(resource_costs))}")
        logger.info(f"   - Total records inserted: {records_inserted}")
        
    except Exception as e:
        logger.error(f"❌ Error processing subscription {sub_name}: {e}")
        session.rollback()
        raise
    
    return records_inserted


def main():
    """Main data collection function"""
    print("\n" + "="*70)
    print("Azure Cost Data Collection")
    print("="*70 + "\n")
    
    try:
        # Initialize database
        engine = init_database()
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Initialize Azure collector
        logger.info("🔐 Initializing Azure Cost Collector...")
        collector = AzureCostCollector()
        
        # Get target subscriptions
        target_sub_ids = os.getenv('AZURE_SUBSCRIPTION_IDS')
        if target_sub_ids:
            target_sub_ids = [s.strip() for s in target_sub_ids.split(',')]
            logger.info(f"📝 Target subscriptions specified: {len(target_sub_ids)}")
        
        # Get all accessible subscriptions
        logger.info("📋 Fetching accessible subscriptions...")
        all_subscriptions = collector.get_subscriptions()
        logger.info(f"✅ Found {len(all_subscriptions)} accessible subscriptions")
        
        # Filter if specific subscriptions are specified
        if target_sub_ids:
            subscriptions = [s for s in all_subscriptions if s['subscription_id'] in target_sub_ids]
            logger.info(f"📌 Processing {len(subscriptions)} target subscriptions")
        else:
            subscriptions = all_subscriptions
            logger.info(f"📌 Processing all {len(subscriptions)} subscriptions")
        
        if not subscriptions:
            logger.warning("⚠️  No subscriptions to process!")
            return
        
        # Display subscriptions to be processed
        print("\n📊 Subscriptions to process:")
        for i, sub in enumerate(subscriptions, 1):
            print(f"   {i}. {sub['display_name']} ({sub['subscription_id']})")
        
        # Collect data for each subscription
        total_records = 0
        successful_subs = 0
        failed_subs = []
        
        for sub in subscriptions:
            try:
                records = collect_subscription_costs(collector, sub, session)
                total_records += records
                successful_subs += 1
            except Exception as e:
                logger.error(f"Failed to process {sub['display_name']}: {e}")
                failed_subs.append(sub['display_name'])
        
        # Final summary
        print("\n" + "="*70)
        print("📈 COLLECTION SUMMARY")
        print("="*70)
        print(f"✅ Successful: {successful_subs}/{len(subscriptions)} subscriptions")
        print(f"📊 Total records inserted: {total_records:,}")
        
        if failed_subs:
            print(f"❌ Failed subscriptions: {', '.join(failed_subs)}")
        
        # Show sample data
        print("\n📋 Sample data from database:")
        result = session.execute(text("""
            SELECT 
                subscription_name,
                service_name,
                SUM(cost) as total_cost,
                COUNT(*) as record_count
            FROM azure_costs
            GROUP BY subscription_name, service_name
            ORDER BY total_cost DESC
            LIMIT 10
        """))
        
        print(f"\n{'Subscription':<30} {'Service':<30} {'Cost':>15} {'Records':>10}")
        print("-" * 90)
        for row in result:
            print(f"{row[0]:<30} {row[1]:<30} ${row[2]:>14,.2f} {row[3]:>10}")
        
        print("\n" + "="*70)
        print("✅ Collection completed successfully!")
        print("="*70 + "\n")
        
        session.close()
        
    except Exception as e:
        logger.error(f"❌ Collection failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

