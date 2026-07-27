import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.monitoring.azure_cost_collector import AzureCostCollector
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get database URL
db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/azure_cost_dev')

# Connect to database
engine = create_engine(db_url)

# Collect Azure data
collector = AzureCostCollector()

print('Collecting Azure cost data...')
subs = collector.get_subscriptions()
print(f'Found {len(subs)} subscriptions')

# Limit to first 3 for testing
for sub in subs[:3]:
    sub_id = sub['subscription_id']
    sub_name = sub['display_name']
    
    print(f'Processing: {sub_name}')
    
    try:
        # Get current month costs
        costs = collector.get_current_month_costs_by_service(sub_id)
        
        with Session(engine) as session:
            for cost in costs:
                sql = '''
                INSERT INTO azure_costs (subscription_id, subscription_name, service_name, cost, currency, date, period_type)
                VALUES (:sub_id, :sub_name, :service, :cost, :currency, :date, :period)
                '''
                session.execute(sql, {
                    'sub_id': sub_id,
                    'sub_name': sub_name,
                    'service': cost['service_name'],
                    'cost': cost['current_cost'],
                    'currency': 'USD',
                    'date': datetime.now().replace(day=1),
                    'period': 'current_month'
                })
            session.commit()
            print(f'  Stored {len(costs)} records')
    except Exception as e:
        print(f'  Error: {e}')

print('Done!')
