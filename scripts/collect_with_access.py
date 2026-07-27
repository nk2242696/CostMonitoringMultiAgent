"""
Azure Cost Data Collection - Only subscriptions with access
"""
import os
import sys
from datetime import datetime, timedelta
from azure.identity import DefaultAzureCredential
from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.resource import SubscriptionClient
import psycopg2
from psycopg2.extras import execute_batch

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def connect_db():
    """Connect to PostgreSQL database"""
    return psycopg2.connect(
        host="localhost",
        port=5432,
        database="azure_cost_dev",
        user="postgres",
        password="postgres"
    )

def parse_cost_date(cost_date):
    """Parse date from various formats Azure might return"""
    if isinstance(cost_date, int):
        # Format: 20251031 -> datetime
        date_str = str(cost_date)
        return datetime.strptime(date_str, '%Y%m%d')
    elif isinstance(cost_date, str):
        # Try common formats
        for fmt in ['%Y%m%d', '%Y-%m-%d', '%Y-%m-%dT%H:%M:%S']:
            try:
                return datetime.strptime(cost_date, fmt)
            except ValueError:
                continue
    elif isinstance(cost_date, datetime):
        return cost_date
    
    raise ValueError(f"Unable to parse date: {cost_date} (type: {type(cost_date)})")

def collect_subscription_costs(credential, subscription_id, subscription_name):
    """Collect cost data for a single subscription"""
    print(f"\nProcessing: {subscription_name}")
    
    cost_client = CostManagementClient(credential)
    records = []
    
    try:
        # Define time range (last 30 days)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        # Build query for daily costs
        scope = f"/subscriptions/{subscription_id}"
        
        query = {
            "type": "ActualCost",
            "timeframe": "Custom",
            "time_period": {
                "from": start_date.strftime("%Y-%m-%dT00:00:00Z"),
                "to": end_date.strftime("%Y-%m-%dT23:59:59Z")
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
                    {
                        "type": "Dimension",
                        "name": "ServiceName"
                    },
                    {
                        "type": "Dimension",
                        "name": "ResourceGroupName"
                    }
                ]
            }
        }
        
        print(f"  Querying cost data from {start_date.date()} to {end_date.date()}...")
        result = cost_client.query.usage(scope=scope, parameters=query)
        
        if result.rows:
            print(f"  Found {len(result.rows)} cost records")
            
            # Parse the data
            for row in result.rows:
                try:
                    # Row format: [cost, date, service_name, resource_group, currency]
                    cost = float(row[0]) if row[0] else 0.0
                    cost_date = parse_cost_date(row[1])
                    service_name = row[2] if len(row) > 2 else "Unknown"
                    resource_group = row[3] if len(row) > 3 else "Unknown"
                    currency = row[4] if len(row) > 4 else "USD"
                    
                    # Skip zero-cost entries
                    if cost > 0:
                        records.append({
                            'subscription_id': subscription_id,
                            'subscription_name': subscription_name,
                            'service_name': service_name,
                            'resource_group': resource_group,
                            'cost': cost,
                            'currency': currency,
                            'date': cost_date,
                            'period_type': 'daily'
                        })
                except Exception as e:
                    print(f"  Warning: Error parsing row: {e}")
                    continue
            
            print(f"  Parsed {len(records)} valid cost records (cost > 0)")
        else:
            print(f"  No cost data found")
            
    except Exception as e:
        print(f"  ERROR: {str(e)}")
        return []
    
    return records

def insert_records(conn, records):
    """Insert records into database using batch insert"""
    if not records:
        return 0
    
    cursor = conn.cursor()
    
    # Clear existing data for these subscriptions
    subscription_ids = list(set(r['subscription_id'] for r in records))
    print(f"\nClearing existing data for {len(subscription_ids)} subscription(s)...")
    cursor.execute(
        "DELETE FROM azure_costs WHERE subscription_id = ANY(%s)",
        (subscription_ids,)
    )
    
    # Prepare insert query
    insert_query = """
        INSERT INTO azure_costs 
        (subscription_id, subscription_name, service_name, resource_group, 
         cost, currency, date, period_type, collected_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    
    # Prepare data tuples
    data = [
        (
            r['subscription_id'],
            r['subscription_name'],
            r['service_name'],
            r['resource_group'],
            r['cost'],
            r['currency'],
            r['date'],
            r['period_type'],
            datetime.now()
        )
        for r in records
    ]
    
    # Batch insert
    print(f"Inserting {len(data)} records...")
    execute_batch(cursor, insert_query, data, page_size=100)
    conn.commit()
    
    return len(data)

def main():
    print("=" * 60)
    print("Azure Cost Data Collection (Authorized Subscriptions Only)")
    print("=" * 60)
    
    # List of subscriptions to collect from
    # Add more subscriptions here as you get Cost Management Reader access
    TARGET_SUBSCRIPTIONS = [
        {
            "id": "46651d0c-a45f-4590-a0f7-9089f887ae19",
            "name": "CSC-Eng-Common-NonProd"
        },
        # To add more subscriptions, uncomment and fill in:
        # {
        #     "id": "YOUR_SUBSCRIPTION_ID_HERE",
        #     "name": "YOUR_SUBSCRIPTION_NAME_HERE"
        # },
    ]
    
    # Authenticate
    print("\nAuthenticating to Azure...")
    credential = DefaultAzureCredential()
    
    # Verify access
    try:
        sub_client = SubscriptionClient(credential)
        subs = list(sub_client.subscriptions.list())
        print(f"Found {len(subs)} accessible subscriptions")
        
        # Verify all target subscriptions are accessible
        accessible_ids = {sub.subscription_id for sub in subs}
        for target in TARGET_SUBSCRIPTIONS:
            if target["id"] in accessible_ids:
                print(f"  ✓ {target['name']} - accessible")
            else:
                print(f"  ✗ {target['name']} - NOT accessible")
            
    except Exception as e:
        print(f"ERROR authenticating: {e}")
        return
    
    # Collect data
    print(f"\nCollecting cost data from {len(TARGET_SUBSCRIPTIONS)} subscription(s)...")
    all_records = []
    successful = 0
    
    for target in TARGET_SUBSCRIPTIONS:
        try:
            records = collect_subscription_costs(
                credential,
                target["id"],
                target["name"]
            )
            all_records.extend(records)
            if records:
                successful += 1
        except Exception as e:
            print(f"  ERROR collecting from {target['name']}: {e}")
            continue
    
    # Insert into database
    if all_records:
        print(f"\n" + "=" * 60)
        print(f"Summary: {successful}/{len(TARGET_SUBSCRIPTIONS)} subscription(s) collected successfully")
        print(f"Total records collected: {len(all_records)}")
        print("=" * 60)
        
        conn = connect_db()
        try:
            inserted = insert_records(conn, all_records)
            print(f"\n✓ SUCCESS: Inserted {inserted} records into database")
            print(f"✓ Dashboard updated at: http://localhost:3000/d/azure-costs")
        finally:
            conn.close()
    else:
        print("\n✗ No data collected - check permissions")
    
    print("\nDone!")

if __name__ == "__main__":
    main()
