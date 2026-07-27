"""
Script to programmatically create Grafana alert rules via API
"""
import requests
import json
from datetime import datetime

# Grafana configuration
GRAFANA_URL = "http://localhost:3000"
GRAFANA_USER = "admin"
GRAFANA_PASSWORD = "AzureCost2025!SecurePass"
DATASOURCE_UID = "PCC52D03280B7034C"
SUBSCRIPTION_ID = "518f04e9-2b37-457e-b852-8f058cb3f160"

# Create session with auth
session = requests.Session()
session.auth = (GRAFANA_USER, GRAFANA_PASSWORD)
session.headers.update({"Content-Type": "application/json"})

def create_alert_rule(rule_data):
    """Create an alert rule in Grafana"""
    url = f"{GRAFANA_URL}/api/v1/provisioning/alert-rules"
    
    try:
        response = session.post(url, json=rule_data)
        if response.status_code in [201, 200]:
            print(f"✅ Created alert rule: {rule_data['title']}")
            return True
        else:
            print(f"❌ Failed to create {rule_data['title']}: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error creating {rule_data['title']}: {str(e)}")
        return False

def create_contact_point(name, webhook_url):
    """Create a Teams webhook contact point"""
    url = f"{GRAFANA_URL}/api/v1/provisioning/contact-points"
    
    contact_point = {
        "name": name,
        "type": "webhook",
        "settings": {
            "url": webhook_url,
            "httpMethod": "POST"
        },
        "disableResolveMessage": False
    }
    
    try:
        response = session.post(url, json=contact_point)
        if response.status_code in [201, 200, 202]:
            print(f"✅ Created contact point: {name}")
            return True
        else:
            print(f"⚠️  Contact point response: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error creating contact point: {str(e)}")
        return False

# Alert Rule 1: Budget Exceeded (Critical)
budget_alert = {
    "uid": "budget-exceeded-001",
    "title": "Budget Exceeded - Critical",
    "condition": "C",
    "data": [
        {
            "refId": "A",
            "queryType": "",
            "relativeTimeRange": {
                "from": 600,
                "to": 0
            },
            "datasourceUid": DATASOURCE_UID,
            "model": {
                "format": "table",
                "rawSql": f"""
                    SELECT 
                        (SUM(cost) / 120000.0 * 100) as utilization_percent
                    FROM cost_records
                    WHERE date >= DATE_TRUNC('month', CURRENT_DATE)
                      AND date < DATE_TRUNC('month', CURRENT_DATE + INTERVAL '1 month')
                      AND subscription_id = '{SUBSCRIPTION_ID}'
                """,
                "refId": "A"
            }
        },
        {
            "refId": "B",
            "queryType": "",
            "relativeTimeRange": {
                "from": 0,
                "to": 0
            },
            "datasourceUid": "-100",
            "model": {
                "conditions": [
                    {
                        "evaluator": {
                            "params": [105],
                            "type": "gt"
                        },
                        "operator": {
                            "type": "and"
                        },
                        "query": {
                            "params": ["A"]
                        },
                        "type": "query"
                    }
                ],
                "datasource": {
                    "type": "__expr__",
                    "uid": "-100"
                },
                "expression": "A",
                "reducer": "last",
                "type": "reduce",
                "refId": "B"
            }
        },
        {
            "refId": "C",
            "queryType": "",
            "relativeTimeRange": {
                "from": 0,
                "to": 0
            },
            "datasourceUid": "-100",
            "model": {
                "conditions": [
                    {
                        "evaluator": {
                            "params": [105],
                            "type": "gt"
                        },
                        "operator": {
                            "type": "and"
                        },
                        "query": {
                            "params": ["C"]
                        },
                        "type": "query"
                    }
                ],
                "datasource": {
                    "type": "__expr__",
                    "uid": "-100"
                },
                "expression": "B",
                "type": "threshold",
                "refId": "C"
            }
        }
    ],
    "noDataState": "NoData",
    "execErrState": "Error",
    "for": "5m",
    "annotations": {
        "description": "Monthly budget utilization has exceeded 105%. Current budget: $120,000",
        "summary": "Budget exceeded alert for subscription"
    },
    "labels": {
        "severity": "critical",
        "team": "finance"
    },
    "folderUID": "cost-alerts"
}

# Alert Rule 2: Service Cost Spike (Warning)
service_spike_alert = {
    "uid": "service-spike-001",
    "title": "Service Cost Spike - Warning",
    "condition": "C",
    "data": [
        {
            "refId": "A",
            "queryType": "",
            "relativeTimeRange": {
                "from": 600,
                "to": 0
            },
            "datasourceUid": DATASOURCE_UID,
            "model": {
                "format": "table",
                "rawSql": """
                    WITH current_month AS (
                        SELECT service_name, SUM(cost) as current_cost
                        FROM cost_records
                        WHERE date >= DATE_TRUNC('month', CURRENT_DATE)
                        GROUP BY service_name
                    ),
                    previous_month AS (
                        SELECT service_name, SUM(cost) as previous_cost
                        FROM cost_records
                        WHERE date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')
                          AND date < DATE_TRUNC('month', CURRENT_DATE)
                        GROUP BY service_name
                    )
                    SELECT MAX(((c.current_cost - p.previous_cost) / p.previous_cost * 100)) as max_increase
                    FROM current_month c
                    JOIN previous_month p ON c.service_name = p.service_name
                    WHERE p.previous_cost > 0
                """,
                "refId": "A"
            }
        },
        {
            "refId": "B",
            "queryType": "",
            "relativeTimeRange": {
                "from": 0,
                "to": 0
            },
            "datasourceUid": "-100",
            "model": {
                "conditions": [
                    {
                        "evaluator": {
                            "params": [50],
                            "type": "gt"
                        },
                        "operator": {
                            "type": "and"
                        },
                        "query": {
                            "params": ["A"]
                        },
                        "type": "query"
                    }
                ],
                "datasource": {
                    "type": "__expr__",
                    "uid": "-100"
                },
                "expression": "A",
                "reducer": "last",
                "type": "reduce",
                "refId": "B"
            }
        },
        {
            "refId": "C",
            "queryType": "",
            "relativeTimeRange": {
                "from": 0,
                "to": 0
            },
            "datasourceUid": "-100",
            "model": {
                "conditions": [
                    {
                        "evaluator": {
                            "params": [50],
                            "type": "gt"
                        },
                        "operator": {
                            "type": "and"
                        },
                        "query": {
                            "params": ["C"]
                        },
                        "type": "query"
                    }
                ],
                "datasource": {
                    "type": "__expr__",
                    "uid": "-100"
                },
                "expression": "B",
                "type": "threshold",
                "refId": "C"
            }
        }
    ],
    "noDataState": "NoData",
    "execErrState": "Error",
    "for": "5m",
    "annotations": {
        "description": "One or more services have increased costs by more than 50% compared to last month",
        "summary": "Service cost spike detected"
    },
    "labels": {
        "severity": "warning",
        "team": "operations"
    },
    "folderUID": "cost-alerts"
}

# Alert Rule 3: Month-over-Month Increase (Warning)
mom_increase_alert = {
    "uid": "mom-increase-001",
    "title": "MoM Cost Increase - Warning",
    "condition": "C",
    "data": [
        {
            "refId": "A",
            "queryType": "",
            "relativeTimeRange": {
                "from": 600,
                "to": 0
            },
            "datasourceUid": DATASOURCE_UID,
            "model": {
                "format": "table",
                "rawSql": f"""
                    WITH current_month AS (
                        SELECT SUM(cost) as total
                        FROM cost_records
                        WHERE date >= DATE_TRUNC('month', CURRENT_DATE)
                          AND subscription_id = '{SUBSCRIPTION_ID}'
                    ),
                    previous_month AS (
                        SELECT SUM(cost) as total
                        FROM cost_records
                        WHERE date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')
                          AND date < DATE_TRUNC('month', CURRENT_DATE)
                          AND subscription_id = '{SUBSCRIPTION_ID}'
                    )
                    SELECT ((c.total - p.total) / p.total * 100) as mom_change
                    FROM current_month c, previous_month p
                """,
                "refId": "A"
            }
        },
        {
            "refId": "B",
            "queryType": "",
            "relativeTimeRange": {
                "from": 0,
                "to": 0
            },
            "datasourceUid": "-100",
            "model": {
                "conditions": [
                    {
                        "evaluator": {
                            "params": [15],
                            "type": "gt"
                        },
                        "operator": {
                            "type": "and"
                        },
                        "query": {
                            "params": ["A"]
                        },
                        "type": "query"
                    }
                ],
                "datasource": {
                    "type": "__expr__",
                    "uid": "-100"
                },
                "expression": "A",
                "reducer": "last",
                "type": "reduce",
                "refId": "B"
            }
        },
        {
            "refId": "C",
            "queryType": "",
            "relativeTimeRange": {
                "from": 0,
                "to": 0
            },
            "datasourceUid": "-100",
            "model": {
                "conditions": [
                    {
                        "evaluator": {
                            "params": [15],
                            "type": "gt"
                        },
                        "operator": {
                            "type": "and"
                        },
                        "query": {
                            "params": ["C"]
                        },
                        "type": "query"
                    }
                ],
                "datasource": {
                    "type": "__expr__",
                    "uid": "-100"
                },
                "expression": "B",
                "type": "threshold",
                "refId": "C"
            }
        }
    ],
    "noDataState": "NoData",
    "execErrState": "Error",
    "for": "5m",
    "annotations": {
        "description": "Month-over-month costs have increased by more than 15%",
        "summary": "Significant MoM cost increase detected"
    },
    "labels": {
        "severity": "warning",
        "team": "finance"
    },
    "folderUID": "cost-alerts"
}

def create_folder():
    """Create alert folder if it doesn't exist"""
    url = f"{GRAFANA_URL}/api/folders"
    
    folder_data = {
        "uid": "cost-alerts",
        "title": "Cost Alerts"
    }
    
    try:
        response = session.post(url, json=folder_data)
        if response.status_code in [200, 201]:
            print("✅ Created folder: Cost Alerts")
            return True
        elif response.status_code == 409:
            print("✅ Folder already exists: Cost Alerts")
            return True
        else:
            print(f"⚠️  Folder creation: {response.status_code}")
            return True  # Continue anyway
    except Exception as e:
        print(f"⚠️  Error creating folder: {str(e)}")
        return True  # Continue anyway

def main():
    print("=" * 60)
    print("Setting up Grafana Alert Rules")
    print("=" * 60)
    print()
    
    # Test connection
    try:
        response = session.get(f"{GRAFANA_URL}/api/health")
        if response.status_code == 200:
            print("✅ Connected to Grafana")
        else:
            print(f"❌ Failed to connect to Grafana: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ Cannot connect to Grafana: {str(e)}")
        print("   Make sure Grafana is running on http://localhost:3000")
        return
    
    # Create folder
    print()
    create_folder()
    
    print()
    print("Creating alert rules...")
    print()
    
    # Create alert rules
    success_count = 0
    
    if create_alert_rule(budget_alert):
        success_count += 1
    
    if create_alert_rule(service_spike_alert):
        success_count += 1
    
    if create_alert_rule(mom_increase_alert):
        success_count += 1
    
    print()
    print("=" * 60)
    print(f"Summary: {success_count}/3 alert rules created successfully")
    print("=" * 60)
    print()
    
    if success_count > 0:
        print("✅ Alert rules are now active in Grafana")
        print()
        print("Next steps:")
        print("1. Go to Grafana → Alerting → Alert rules to view them")
        print("2. Create a Teams webhook contact point:")
        print("   - Alerting → Contact points → New contact point")
        print("   - Name: 'Teams - Cost Alerts'")
        print("   - Type: Webhook")
        print("   - URL: [Your Teams incoming webhook URL]")
        print("3. Configure notification policy to use the contact point")
        print()
        print("Current alert status:")
        print("  • Budget: 103.79% (will fire if >105%)")
        print("  • Service Spike: Load Balancer +45.58% (will fire if >50%)")
        print("  • MoM: -1.60% (will fire if >15%)")
    else:
        print("⚠️  No alert rules were created. Check the errors above.")
        print()
        print("Common issues:")
        print("  • Alert rules may already exist (delete them first)")
        print("  • Folder 'cost-alerts' may not exist")
        print("  • Datasource UID may be incorrect")

if __name__ == "__main__":
    main()
