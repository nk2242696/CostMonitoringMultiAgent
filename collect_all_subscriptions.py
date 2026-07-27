"""
Collect cost data from all accessible Azure subscriptions
"""
import subprocess
import json
import psycopg2
from datetime import datetime, timedelta
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'azure_cost_dev',
    'user': 'postgres',
    'password': 'AzureCost2025!DbPass'
}


def get_all_subscriptions():
    """Get list of all accessible subscriptions"""
    logger.info("Fetching all accessible subscriptions...")
    result = subprocess.run(
        ['az', 'account', 'list', '--output', 'json'],
        capture_output=True,
        text=True,
        check=True,
        shell=True
    )
    subscriptions = json.loads(result.stdout)
    logger.info(f"Found {len(subscriptions)} accessible subscriptions")
    return subscriptions


def get_cost_data_for_subscription(subscription_id, subscription_name, days=90):
    """Get cost data for a specific subscription"""
    logger.info(f"Fetching cost data for: {subscription_name} ({subscription_id})")
    
    # Set the subscription
    subprocess.run(
        ['az', 'account', 'set', '--subscription', subscription_id],
        check=True,
        capture_output=True,
        shell=True
    )
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Query cost data using Azure Cost Management API
    query = {
        "type": "Usage",
        "timeframe": "Custom",
        "timePeriod": {
            "from": start_date.strftime("%Y-%m-%d"),
            "to": end_date.strftime("%Y-%m-%d")
        },
        "dataset": {
            "granularity": "Daily",
            "aggregation": {
                "totalCost": {
                    "name": "Cost",
                    "function": "Sum"
                }
            },
            "grouping": [
                {"type": "Dimension", "name": "ServiceName"},
                {"type": "Dimension", "name": "ResourceGroup"}
            ]
        }
    }
    
    try:
        result = subprocess.run(
            ['az', 'costmanagement', 'query',
             '--type', 'Usage',
             '--dataset-aggregation', 'totalCost=Sum',
             '--dataset-grouping', 'name=ServiceName', 'type=Dimension',
             '--dataset-grouping', 'name=ResourceGroup', 'type=Dimension',
             '--timeframe', 'Custom',
             '--time-period', f'from={start_date.strftime("%Y-%m-%d")}',
             f'to={end_date.strftime("%Y-%m-%d")}',
             '--query', 'rows',
             '--output', 'json'],
            capture_output=True,
            text=True,
            timeout=60,
            shell=True
        )
        
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            logger.info(f"Retrieved {len(data) if data else 0} cost records for {subscription_name}")
            return data
        else:
            logger.warning(f"No cost data available for {subscription_name}: {result.stderr}")
            return []
            
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout while fetching data for {subscription_name}")
        return []
    except Exception as e:
        logger.error(f"Error fetching cost data for {subscription_name}: {e}")
        return []


def insert_cost_data(conn, subscription_id, subscription_name, cost_data):
    """Insert cost data into database"""
    if not cost_data:
        return 0
    
    cursor = conn.cursor()
    inserted = 0
    
    for row in cost_data:
        try:
            # Row format: [cost, date, service_name, resource_group, currency]
            cost = float(row[0]) if row[0] else 0.0
            date = datetime.strptime(row[1], "%Y%m%d").date()
            service_name = row[2] if len(row) > 2 else 'Unknown'
            resource_group = row[3] if len(row) > 3 else 'Unknown'
            currency = row[4] if len(row) > 4 else 'USD'
            
            # Skip zero cost entries
            if cost == 0:
                continue
            
            cursor.execute("""
                INSERT INTO cost_records 
                (subscription_id, subscription_name, service_name, resource_group, 
                 cost, currency, date, region)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (subscription_id, service_name, date) 
                DO UPDATE SET 
                    cost = EXCLUDED.cost,
                    resource_group = EXCLUDED.resource_group,
                    currency = EXCLUDED.currency,
                    subscription_name = EXCLUDED.subscription_name
            """, (
                subscription_id,
                subscription_name,
                service_name,
                resource_group,
                cost,
                currency,
                date,
                'unknown'  # region not available in this query
            ))
            inserted += 1
            
        except Exception as e:
            logger.error(f"Error inserting record: {e}, row: {row}")
            continue
    
    conn.commit()
    cursor.close()
    return inserted


def main():
    """Main function to collect costs from all subscriptions"""
    logger.info("=" * 80)
    logger.info("Starting multi-subscription cost collection")
    logger.info("=" * 80)
    
    # Get all subscriptions
    subscriptions = get_all_subscriptions()
    
    # Connect to database
    conn = psycopg2.connect(**DB_CONFIG)
    
    total_inserted = 0
    successful = 0
    failed = 0
    
    for sub in subscriptions:
        sub_id = sub['id']
        sub_name = sub['name']
        
        try:
            # Get cost data
            cost_data = get_cost_data_for_subscription(sub_id, sub_name)
            
            # Insert into database
            if cost_data:
                inserted = insert_cost_data(conn, sub_id, sub_name, cost_data)
                total_inserted += inserted
                successful += 1
                logger.info(f"✓ {sub_name}: {inserted} records inserted")
            else:
                logger.info(f"○ {sub_name}: No cost data available")
                successful += 1
                
        except Exception as e:
            logger.error(f"✗ {sub_name}: Failed - {e}")
            failed += 1
            continue
    
    conn.close()
    
    logger.info("=" * 80)
    logger.info("Collection Summary:")
    logger.info(f"  Total Subscriptions: {len(subscriptions)}")
    logger.info(f"  Successful: {successful}")
    logger.info(f"  Failed: {failed}")
    logger.info(f"  Total Records Inserted: {total_inserted}")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
