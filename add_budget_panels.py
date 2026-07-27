"""
Add budget tracking panels to Azure Cost Trends dashboard.
"""
import json

def add_budget_panels():
    """Add budget tracking panels to the dashboard."""
    
    # Read existing dashboard
    with open('config/grafana/dashboards/azure-cost-trends.json', 'r') as f:
        dashboard = json.load(f)
    
    # Budget Status Panel - shows if over/under budget
    budget_status_panel = {
        "datasource": {
            "type": "postgres",
            "uid": "PCC52D03280B7034C"
        },
        "fieldConfig": {
            "defaults": {
                "color": {
                    "mode": "thresholds"
                },
                "mappings": [
                    {
                        "options": {
                            "0": {
                                "color": "red",
                                "index": 0,
                                "text": "Over Budget"
                            },
                            "1": {
                                "color": "green",
                                "index": 1,
                                "text": "Within Budget"
                            }
                        },
                        "type": "value"
                    }
                ],
                "thresholds": {
                    "mode": "absolute",
                    "steps": [
                        {
                            "color": "red",
                            "value": None
                        },
                        {
                            "color": "green",
                            "value": 1
                        }
                    ]
                }
            }
        },
        "gridPos": {
            "h": 6,
            "w": 6,
            "x": 18,
            "y": 0
        },
        "id": 100,
        "options": {
            "colorMode": "background",
            "graphMode": "none",
            "justifyMode": "center",
            "orientation": "auto",
            "reduceOptions": {
                "calcs": ["lastNotNull"],
                "fields": "",
                "values": False
            },
            "textMode": "value"
        },
        "pluginVersion": "9.0.0",
        "targets": [
            {
                "datasource": {
                    "type": "postgres",
                    "uid": "PCC52D03280B7034C"
                },
                "format": "table",
                "group": [],
                "metricColumn": "none",
                "rawQuery": True,
                "rawSql": """
                    WITH current_spend AS (
                        SELECT SUM(cost) as total
                        FROM cost_records
                        WHERE date >= DATE_TRUNC('month', CURRENT_DATE)
                          AND date < DATE_TRUNC('month', CURRENT_DATE + INTERVAL '1 month')
                          AND subscription_id = '$subscription'
                    ),
                    budget AS (
                        SELECT SUM(budget_amount) as total
                        FROM cost_budgets
                        WHERE is_active = true
                          AND time_period = 'monthly'
                    )
                    SELECT 
                        CASE 
                            WHEN c.total <= b.total THEN 1
                            ELSE 0
                        END as "Budget Status"
                    FROM current_spend c, budget b;
                """,
                "refId": "A",
                "select": [[{"params": ["cost"], "type": "column"}]],
                "table": "cost_records",
                "timeColumn": "date",
                "timeColumnType": "timestamp",
                "where": [{"name": "$__timeFilter", "params": [], "type": "macro"}]
            }
        ],
        "title": "💰 Budget Status",
        "type": "stat"
    }
    
    # Budget Overview Panel - shows budget vs actual with gauge
    budget_overview_panel = {
        "datasource": {
            "type": "postgres",
            "uid": "PCC52D03280B7034C"
        },
        "fieldConfig": {
            "defaults": {
                "color": {
                    "mode": "thresholds"
                },
                "mappings": [],
                "max": 100,
                "min": 0,
                "thresholds": {
                    "mode": "percentage",
                    "steps": [
                        {
                            "color": "green",
                            "value": None
                        },
                        {
                            "color": "yellow",
                            "value": 75
                        },
                        {
                            "color": "orange",
                            "value": 90
                        },
                        {
                            "color": "red",
                            "value": 100
                        }
                    ]
                },
                "unit": "percent"
            }
        },
        "gridPos": {
            "h": 8,
            "w": 12,
            "x": 0,
            "y": 6
        },
        "id": 101,
        "options": {
            "orientation": "auto",
            "reduceOptions": {
                "calcs": ["lastNotNull"],
                "fields": "",
                "values": False
            },
            "showThresholdLabels": False,
            "showThresholdMarkers": True,
            "text": {}
        },
        "pluginVersion": "9.0.0",
        "targets": [
            {
                "datasource": {
                    "type": "postgres",
                    "uid": "PCC52D03280B7034C"
                },
                "format": "table",
                "group": [],
                "metricColumn": "none",
                "rawQuery": True,
                "rawSql": """
                    WITH current_spend AS (
                        SELECT SUM(cost) as total
                        FROM cost_records
                        WHERE date >= DATE_TRUNC('month', CURRENT_DATE)
                          AND date < DATE_TRUNC('month', CURRENT_DATE + INTERVAL '1 month')
                          AND subscription_id = '$subscription'
                    ),
                    budget AS (
                        SELECT SUM(budget_amount) as total
                        FROM cost_budgets
                        WHERE is_active = true
                          AND time_period = 'monthly'
                    )
                    SELECT 
                        ROUND((c.total / NULLIF(b.total, 0) * 100)::numeric, 2) as "Budget Used %"
                    FROM current_spend c, budget b;
                """,
                "refId": "A",
                "select": [[{"params": ["cost"], "type": "column"}]],
                "table": "cost_records",
                "timeColumn": "date",
                "timeColumnType": "timestamp",
                "where": [{"name": "$__timeFilter", "params": [], "type": "macro"}]
            }
        ],
        "title": "📊 Budget Utilization (Monthly)",
        "type": "gauge"
    }
    
    # Budget Details Table
    budget_details_panel = {
        "datasource": {
            "type": "postgres",
            "uid": "PCC52D03280B7034C"
        },
        "fieldConfig": {
            "defaults": {
                "color": {
                    "mode": "thresholds"
                },
                "custom": {
                    "align": "auto",
                    "displayMode": "auto"
                },
                "mappings": [],
                "thresholds": {
                    "mode": "absolute",
                    "steps": [
                        {
                            "color": "green",
                            "value": None
                        }
                    ]
                }
            },
            "overrides": [
                {
                    "matcher": {
                        "id": "byName",
                        "options": "Over/Under"
                    },
                    "properties": [
                        {
                            "id": "custom.displayMode",
                            "value": "color-background"
                        },
                        {
                            "id": "thresholds",
                            "value": {
                                "mode": "absolute",
                                "steps": [
                                    {
                                        "color": "green",
                                        "value": None
                                    },
                                    {
                                        "color": "red",
                                        "value": 0
                                    }
                                ]
                            }
                        },
                        {
                            "id": "unit",
                            "value": "currencyUSD"
                        }
                    ]
                },
                {
                    "matcher": {
                        "id": "byName",
                        "options": "Used %"
                    },
                    "properties": [
                        {
                            "id": "custom.displayMode",
                            "value": "gradient-gauge"
                        },
                        {
                            "id": "max",
                            "value": 150
                        },
                        {
                            "id": "min",
                            "value": 0
                        },
                        {
                            "id": "thresholds",
                            "value": {
                                "mode": "absolute",
                                "steps": [
                                    {
                                        "color": "green",
                                        "value": None
                                    },
                                    {
                                        "color": "yellow",
                                        "value": 75
                                    },
                                    {
                                        "color": "orange",
                                        "value": 90
                                    },
                                    {
                                        "color": "red",
                                        "value": 100
                                    }
                                ]
                            }
                        },
                        {
                            "id": "unit",
                            "value": "percent"
                        }
                    ]
                }
            ]
        },
        "gridPos": {
            "h": 8,
            "w": 12,
            "x": 12,
            "y": 6
        },
        "id": 102,
        "options": {
            "footer": {
                "fields": "",
                "reducer": ["sum"],
                "show": False
            },
            "showHeader": True,
            "sortBy": []
        },
        "pluginVersion": "9.0.0",
        "targets": [
            {
                "datasource": {
                    "type": "postgres",
                    "uid": "PCC52D03280B7034C"
                },
                "format": "table",
                "group": [],
                "metricColumn": "none",
                "rawQuery": True,
                "rawSql": """
                    WITH current_spend AS (
                        SELECT SUM(cost) as total
                        FROM cost_records
                        WHERE date >= DATE_TRUNC('month', CURRENT_DATE)
                          AND date < DATE_TRUNC('month', CURRENT_DATE + INTERVAL '1 month')
                          AND subscription_id = '$subscription'
                    ),
                    budgets AS (
                        SELECT 
                            name,
                            budget_amount,
                            time_period
                        FROM cost_budgets
                        WHERE is_active = true
                          AND time_period = 'monthly'
                    )
                    SELECT 
                        b.name as "Budget Name",
                        ROUND(b.budget_amount::numeric, 2) as "Budget Amount",
                        ROUND(c.total::numeric, 2) as "Actual Spend",
                        ROUND((c.total / NULLIF(b.budget_amount, 0) * 100)::numeric, 2) as "Used %",
                        ROUND((c.total - b.budget_amount)::numeric, 2) as "Over/Under",
                        CASE 
                            WHEN c.total > b.budget_amount THEN '🔴 Over Budget'
                            WHEN c.total > b.budget_amount * 0.9 THEN '🟡 Near Limit'
                            ELSE '🟢 On Track'
                        END as "Status"
                    FROM budgets b, current_spend c
                    ORDER BY "Used %" DESC;
                """,
                "refId": "A",
                "select": [[{"params": ["cost"], "type": "column"}]],
                "table": "cost_records",
                "timeColumn": "date",
                "timeColumnType": "timestamp",
                "where": [{"name": "$__timeFilter", "params": [], "type": "macro"}]
            }
        ],
        "title": "💵 Budget Details",
        "type": "table"
    }
    
    # Insert new panels after the first 4 stat panels (y=6)
    # Shift existing panels down
    for panel in dashboard['panels']:
        if panel.get('gridPos', {}).get('y', 0) >= 6:
            panel['gridPos']['y'] += 8  # Make room for budget panels
    
    # Add budget panels
    dashboard['panels'].extend([
        budget_status_panel,
        budget_overview_panel,
        budget_details_panel
    ])
    
    # Save updated dashboard
    with open('config/grafana/dashboards/azure-cost-trends.json', 'w') as f:
        json.dump(dashboard, f, indent=2)
    
    print("✅ Budget panels added successfully!")
    print("📊 Added 3 new panels:")
    print("   1. Budget Status (Over/Under)")
    print("   2. Budget Utilization Gauge")
    print("   3. Budget Details Table")
    print("\n🔄 Restart Grafana to see changes:")
    print("   docker restart azure-cost-grafana")

if __name__ == "__main__":
    add_budget_panels()
