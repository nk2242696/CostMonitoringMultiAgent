"""
Prometheus exporter for Azure Cost Monitoring metrics.
Exposes custom metrics about costs, services, and budgets.
"""

import os
from prometheus_client import start_http_server, Gauge
from sqlalchemy import text, create_engine
from sqlalchemy.orm import sessionmaker
import time
import traceback

# Prometheus metrics
TOTAL_COST = Gauge('azure_total_cost', 'Total Azure cost')
COST_BY_SERVICE = Gauge('azure_cost_by_service', 'Cost by Azure service', ['service_name'])
COST_BY_SUBSCRIPTION = Gauge('azure_cost_by_subscription', 'Cost by subscription', ['subscription_id'])
COST_RECORDS_COUNT = Gauge('azure_cost_records_total', 'Total number of cost records')

# Database setup - use synchronous engine for simplicity
DATABASE_URL = os.environ.get(
    "DATABASE_URL", 
    "postgresql://postgres:AzureCost2025!DbPass@localhost:5432/azure_cost_dev"
)
# Convert to synchronous URL if needed
if "postgresql+asyncpg" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg", "postgresql")

engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def collect_metrics():
    """Collect metrics from database and update Prometheus gauges."""
    with SessionLocal() as session:
        try:
            # Total cost (last 30 days)
            result = session.execute(text("""
                SELECT COALESCE(SUM(cost), 0) as total_cost
                FROM cost_records
                WHERE date >= CURRENT_DATE - INTERVAL '30 days'
            """))
            total = result.fetchone()
            if total:
                TOTAL_COST.set(float(total[0]))
            
            # Cost by service (last 30 days)
            result = session.execute(text("""
                SELECT service_name, SUM(cost) as service_cost
                FROM cost_records
                WHERE date >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY service_name
            """))
            for row in result.fetchall():
                COST_BY_SERVICE.labels(service_name=row[0]).set(float(row[1]))
            
            # Cost by subscription (last 30 days)
            result = session.execute(text("""
                SELECT subscription_id, SUM(cost) as subscription_cost
                FROM cost_records
                WHERE date >= CURRENT_DATE - INTERVAL '30 days'
                GROUP BY subscription_id
            """))
            for row in result.fetchall():
                COST_BY_SUBSCRIPTION.labels(subscription_id=row[0]).set(float(row[1]))
            
            # Total record count
            result = session.execute(text("SELECT COUNT(*) FROM cost_records"))
            count = result.fetchone()
            if count:
                COST_RECORDS_COUNT.set(float(count[0]))
            
            print(f"✅ Metrics collected at {time.strftime('%Y-%m-%d %H:%M:%S')}")
            
        except Exception as e:
            print(f"❌ Error collecting metrics: {e}")
            traceback.print_exc()


def metrics_loop():
    """Continuously collect metrics every 30 seconds."""
    while True:
        collect_metrics()
        time.sleep(30)


def main():
    """Start the Prometheus exporter."""
    port = int(os.environ.get("EXPORTER_PORT", 8001))
    
    print("=" * 70)
    print("🔥 Prometheus Exporter for Azure Cost Monitoring")
    print("=" * 70)
    print(f"📊 Metrics endpoint: http://localhost:{port}/metrics")
    print(f"💾 Database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'configured'}")
    print(f"🔄 Collection interval: 30 seconds")
    print("=" * 70)
    
    # Start Prometheus HTTP server
    start_http_server(port)
    print(f"\n✅ Exporter started on port {port}")
    print("🔄 Starting metrics collection...")
    
    # Run metrics collection loop
    try:
        metrics_loop()
    except KeyboardInterrupt:
        print("\n⛔ Exporter stopped")


if __name__ == "__main__":
    main()

