"""
Generate Enhanced Cost Dashboard with:
1. Month-over-month change tracking for each service
2. Stacked area chart (sandwich chart) showing cost breakdown by service per subscription
"""

import psycopg2
import json
from typing import Dict, List

# Database connection
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'azure_cost_dev',
    'user': 'postgres',
    'password': 'AzureCost2025!DbPass'
}


def create_enhanced_cost_dashboard():
    """Create dashboard with MoM changes and stacked area chart"""
    
    panels = []
    panel_id = 1
    y_pos = 0
    
    # Row 1: Summary Stats (4 panels)
    panels.extend([
        # Total Cost (Current Month)
        {
            "datasource": {"type": "postgres", "uid": "PCC52D03280B7034C"},
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "thresholds"},
                    "mappings": [],
                    "thresholds": {
                        "mode": "absolute",
                        "steps": [
                            {"color": "green", "value": None},
                            {"color": "yellow", "value": 50000},
                            {"color": "orange", "value": 100000},
                            {"color": "red", "value": 150000}
                        ]
                    },
                    "unit": "currencyUSD"
                }
            },
            "gridPos": {"h": 6, "w": 6, "x": 0, "y": y_pos},
            "id": panel_id,
            "options": {
                "colorMode": "background",
                "graphMode": "area",
                "justifyMode": "auto",
                "orientation": "auto",
                "reduceOptions": {"values": False, "calcs": ["lastNotNull"], "fields": ""},
                "textMode": "auto"
            },
            "pluginVersion": "11.4.0",
            "targets": [{
                "datasource": {"type": "postgres", "uid": "PCC52D03280B7034C"},
                "format": "table",
                "rawQuery": True,
                "rawSql": """
                    SELECT SUM(cost) as "Total Cost This Month"
                    FROM cost_records
                    WHERE date >= DATE_TRUNC('month', CURRENT_DATE)
                      AND date < DATE_TRUNC('month', CURRENT_DATE + INTERVAL '1 month')
                      AND subscription_id = '$subscription';
                """
            }],
            "title": "💰 Total Cost (Current Month)",
            "type": "stat"
        },
        
        # Month-over-Month Change %
        {
            "datasource": {"type": "postgres", "uid": "PCC52D03280B7034C"},
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "thresholds"},
                    "mappings": [],
                    "thresholds": {
                        "mode": "absolute",
                        "steps": [
                            {"color": "green", "value": None},
                            {"color": "green", "value": -20},
                            {"color": "yellow", "value": -10},
                            {"color": "orange", "value": 0},
                            {"color": "red", "value": 10}
                        ]
                    },
                    "unit": "percent"
                }
            },
            "gridPos": {"h": 6, "w": 6, "x": 6, "y": y_pos},
            "id": panel_id + 1,
            "options": {
                "colorMode": "background",
                "graphMode": "area",
                "justifyMode": "auto",
                "orientation": "auto",
                "reduceOptions": {"values": False, "calcs": ["lastNotNull"], "fields": ""},
                "textMode": "value_and_name"
            },
            "pluginVersion": "11.4.0",
            "targets": [{
                "datasource": {"type": "postgres", "uid": "PCC52D03280B7034C"},
                "format": "table",
                "rawQuery": True,
                "rawSql": """
                    WITH current_month AS (
                        SELECT SUM(cost) as total
                        FROM cost_records
                        WHERE date >= DATE_TRUNC('month', CURRENT_DATE)
                          AND date < DATE_TRUNC('month', CURRENT_DATE + INTERVAL '1 month')
                          AND subscription_id = '$subscription'
                    ),
                    previous_month AS (
                        SELECT SUM(cost) as total
                        FROM cost_records
                        WHERE date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')
                          AND date < DATE_TRUNC('month', CURRENT_DATE')
                          AND subscription_id = '$subscription'
                    )
                    SELECT 
                        CASE 
                            WHEN p.total > 0 THEN ((c.total - p.total) / p.total * 100)
                            ELSE 0
                        END as "MoM Change %"
                    FROM current_month c, previous_month p;
                """
            }],
            "title": "📈 Month-over-Month Change",
            "type": "stat"
        },
        
        # Active Services Count
        {
            "datasource": {"type": "postgres", "uid": "PCC52D03280B7034C"},
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "thresholds"},
                    "mappings": [],
                    "thresholds": {
                        "mode": "absolute",
                        "steps": [
                            {"color": "blue", "value": None},
                            {"color": "purple", "value": 5}
                        ]
                    },
                    "unit": "short"
                }
            },
            "gridPos": {"h": 6, "w": 6, "x": 12, "y": y_pos},
            "id": panel_id + 2,
            "options": {
                "colorMode": "value",
                "graphMode": "area",
                "justifyMode": "auto",
                "orientation": "auto",
                "reduceOptions": {"values": False, "calcs": ["lastNotNull"], "fields": ""},
                "textMode": "auto"
            },
            "pluginVersion": "11.4.0",
            "targets": [{
                "datasource": {"type": "postgres", "uid": "PCC52D03280B7034C"},
                "format": "table",
                "rawQuery": True,
                "rawSql": """
                    SELECT COUNT(DISTINCT service_name) as "Active Services"
                    FROM cost_records
                    WHERE date >= DATE_TRUNC('month', CURRENT_DATE)
                      AND subscription_id = '$subscription';
                """
            }],
            "title": "🔧 Active Services",
            "type": "stat"
        },
        
        # Active Subscriptions
        {
            "datasource": {"type": "postgres", "uid": "PCC52D03280B7034C"},
            "fieldConfig": {
                "defaults": {
                    "color": {"mode": "thresholds"},
                    "mappings": [],
                    "thresholds": {
                        "mode": "absolute",
                        "steps": [{"color": "semi-dark-blue", "value": None}]
                    },
                    "unit": "short"
                }
            },
            "gridPos": {"h": 6, "w": 6, "x": 18, "y": y_pos},
            "id": panel_id + 3,
            "options": {
                "colorMode": "value",
                "graphMode": "none",
                "justifyMode": "auto",
                "orientation": "auto",
                "reduceOptions": {"values": False, "calcs": ["lastNotNull"], "fields": ""},
                "textMode": "auto"
            },
            "pluginVersion": "11.4.0",
            "targets": [{
                "datasource": {"type": "postgres", "uid": "PCC52D03280B7034C"},
                "format": "table",
                "rawQuery": True,
                "rawSql": """
                    SELECT COUNT(DISTINCT subscription_id) as "Active Subscriptions"
                    FROM cost_records
                    WHERE date >= DATE_TRUNC('month', CURRENT_DATE)
                      AND subscription_id = '$subscription';
                """
            }],
            "title": "📋 Active Subscriptions",
            "type": "stat"
        }
    ])
    
    y_pos += 6
    panel_id += 4
    
    # Row 2: Stacked Area Chart - Cost Breakdown by Service (Sandwich Chart)
    panels.append({
        "datasource": {"type": "postgres", "uid": "PCC52D03280B7034C"},
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "palette-classic"},
                "custom": {
                    "axisCenteredZero": False,
                    "axisColorMode": "text",
                    "axisLabel": "Cost (USD)",
                    "axisPlacement": "auto",
                    "barAlignment": 0,
                    "drawStyle": "line",
                    "fillOpacity": 80,
                    "gradientMode": "opacity",
                    "hideFrom": {"tooltip": False, "viz": False, "legend": False},
                    "lineInterpolation": "smooth",
                    "lineWidth": 1,
                    "pointSize": 5,
                    "scaleDistribution": {"type": "linear"},
                    "showPoints": "never",
                    "spanNulls": True,
                    "stacking": {"mode": "normal", "group": "A"},
                    "thresholdsStyle": {"mode": "off"}
                },
                "mappings": [],
                "thresholds": {
                    "mode": "absolute",
                    "steps": [{"color": "green", "value": None}]
                },
                "unit": "currencyUSD"
            },
            "overrides": []
        },
        "gridPos": {"h": 12, "w": 24, "x": 0, "y": y_pos},
        "id": panel_id,
        "options": {
            "legend": {
                "calcs": ["last", "sum"],
                "displayMode": "table",
                "placement": "right",
                "showLegend": True,
                "sortBy": "Sum",
                "sortDesc": True
            },
            "tooltip": {"mode": "multi", "sort": "desc"}
        },
        "pluginVersion": "11.4.0",
        "targets": [{
            "datasource": {"type": "postgres", "uid": "PCC52D03280B7034C"},
            "format": "time_series",
            "rawQuery": True,
            "rawSql": """
                SELECT 
                    DATE_TRUNC('day', date) as time,
                    service_name as metric,
                    SUM(cost) as value
                FROM cost_records
                WHERE date >= NOW() - INTERVAL '90 days'
                  AND subscription_id = '$subscription'
                GROUP BY DATE_TRUNC('day', date), service_name
                ORDER BY time, service_name;
            """
        }],
        "title": "📊 Cost Breakdown by Service Over Time (Stacked Area Chart)",
        "type": "timeseries"
    })
    
    y_pos += 12
    panel_id += 1
    
    # Row 4: Forecast Bar Chart
    panels.append({
        "datasource": {"type": "postgres", "uid": "PCC52D03280B7034C"},
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "palette-classic"},
                "custom": {
                    "axisCenteredZero": False,
                    "axisColorMode": "text",
                    "axisLabel": "Cost (USD)",
                    "axisPlacement": "auto",
                    "fillOpacity": 80,
                    "gradientMode": "none",
                    "hideFrom": {"tooltip": False, "viz": False, "legend": False},
                    "lineWidth": 1,
                    "scaleDistribution": {"type": "linear"},
                    "thresholdsStyle": {"mode": "off"}
                },
                "mappings": [],
                "thresholds": {
                    "mode": "absolute",
                    "steps": [{"color": "green", "value": None}]
                },
                "unit": "currencyUSD"
            },
            "overrides": [
                {
                    "matcher": {"id": "byName", "options": "Total Forecast"},
                    "properties": [
                        {"id": "color", "value": {"fixedColor": "light-blue", "mode": "fixed"}},
                        {"id": "custom.fillOpacity", "value": 50}
                    ]
                }
            ]
        },
        "gridPos": {"h": 8, "w": 6, "x": 18, "y": y_pos - 12},
        "id": panel_id,
        "options": {
            "barRadius": 0,
            "barWidth": 0.8,
            "fullHighlight": False,
            "groupWidth": 0.7,
            "legend": {
                "calcs": ["sum"],
                "displayMode": "list",
                "placement": "bottom",
                "showLegend": True
            },
            "orientation": "horizontal",
            "showValue": "always",
            "stacking": "none",
            "tooltip": {"mode": "single", "sort": "none"},
            "xTickLabelRotation": 0,
            "xTickLabelSpacing": 0
        },
        "pluginVersion": "11.4.0",
        "targets": [{
            "datasource": {"type": "postgres", "uid": "PCC52D03280B7034C"},
            "format": "table",
            "rawQuery": True,
            "rawSql": """
                WITH current_month_data AS (
                    SELECT 
                        DATE(date) as day,
                        SUM(cost) as daily_cost
                    FROM cost_records
                    WHERE date >= DATE_TRUNC('month', CURRENT_DATE)
                      AND date < DATE_TRUNC('month', CURRENT_DATE + INTERVAL '1 month')
                      AND subscription_id = '$subscription'
                    GROUP BY DATE(date)
                ),
                current_total AS (
                    SELECT COALESCE(SUM(daily_cost), 0) as total
                    FROM current_month_data
                ),
                avg_daily AS (
                    SELECT COALESCE(AVG(daily_cost), 0) as avg_cost
                    FROM current_month_data
                ),
                days_remaining AS (
                    SELECT 
                        EXTRACT(day FROM (DATE_TRUNC('month', CURRENT_DATE + INTERVAL '1 month') - CURRENT_DATE))::integer as days
                )
                SELECT 
                    'Total Forecast' as metric,
                    ROUND((c.total + (a.avg_cost * d.days))::numeric, 2) as value
                FROM current_total c, avg_daily a, days_remaining d;
            """
        }],
        "title": "📊 Monthly Forecast",
        "type": "barchart"
    })
    
    panel_id += 1
    
    # Row 5: Detailed Table with TeamGroup, Service, Subscription
    panels.append({
        "datasource": {"type": "postgres", "uid": "PCC52D03280B7034C"},
        "fieldConfig": {
            "defaults": {
                "custom": {
                    "align": "auto",
                    "cellOptions": {"type": "auto"},
                    "inspect": False,
                    "filterable": True
                },
                "mappings": [],
                "thresholds": {
                    "mode": "absolute",
                    "steps": [{"color": "green", "value": None}]
                }
            },
            "overrides": [
                {
                    "matcher": {"id": "byName", "options": "Latest Month"},
                    "properties": [{"id": "unit", "value": "currencyUSD"}]
                },
                {
                    "matcher": {"id": "byName", "options": "Previous Month"},
                    "properties": [{"id": "unit", "value": "currencyUSD"}]
                },
                {
                    "matcher": {"id": "byName", "options": "Change"},
                    "properties": [
                        {"id": "unit", "value": "currencyUSD"},
                        {
                            "id": "custom.cellOptions",
                            "value": {"type": "color-text"}
                        },
                        {
                            "id": "thresholds",
                            "value": {
                                "mode": "absolute",
                                "steps": [
                                    {"color": "green", "value": None},
                                    {"color": "green", "value": -10000},
                                    {"color": "yellow", "value": 0},
                                    {"color": "orange", "value": 5000},
                                    {"color": "red", "value": 10000}
                                ]
                            }
                        }
                    ]
                },
                {
                    "matcher": {"id": "byName", "options": "MoM"},
                    "properties": [
                        {
                            "id": "custom.cellOptions",
                            "value": {"type": "color-background"}
                        },
                        {
                            "id": "thresholds",
                            "value": {
                                "mode": "absolute",
                                "steps": [
                                    {"color": "green", "value": None},
                                    {"color": "green", "value": -20},
                                    {"color": "light-green", "value": -10},
                                    {"color": "yellow", "value": -5},
                                    {"color": "orange", "value": 0},
                                    {"color": "light-red", "value": 5},
                                    {"color": "red", "value": 10}
                                ]
                            }
                        },
                        {
                            "id": "custom.cellOptions",
                            "value": {
                                "type": "gauge",
                                "mode": "gradient"
                            }
                        },
                        {"id": "unit", "value": "percent"},
                        {"id": "decimals", "value": 2}
                    ]
                }
            ]
        },
        "gridPos": {"h": 12, "w": 24, "x": 0, "y": y_pos},
        "id": panel_id,
        "options": {
            "cellHeight": "sm",
            "footer": {
                "countRows": False,
                "enablePagination": True,
                "fields": "",
                "reducer": ["sum"],
                "show": True
            },
            "showHeader": True,
            "sortBy": [{"desc": True, "displayName": "MoM"}]
        },
        "pluginVersion": "11.4.0",
        "targets": [{
            "datasource": {"type": "postgres", "uid": "PCC52D03280B7034C"},
            "format": "table",
            "rawQuery": True,
            "rawSql": """
                WITH current_month AS (
                    SELECT 
                        subscription_id,
                        service_name,
                        resource_group,
                        SUM(cost) as current_cost
                    FROM cost_records
                    WHERE date >= DATE_TRUNC('month', CURRENT_DATE)
                      AND date < DATE_TRUNC('month', CURRENT_DATE + INTERVAL '1 month')
                      AND subscription_id = '$subscription'
                    GROUP BY subscription_id, service_name, resource_group
                ),
                previous_month AS (
                    SELECT 
                        subscription_id,
                        service_name,
                        resource_group,
                        SUM(cost) as previous_cost
                    FROM cost_records
                    WHERE date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')
                      AND date < DATE_TRUNC('month', CURRENT_DATE)
                      AND subscription_id = '$subscription'
                    GROUP BY subscription_id, service_name, resource_group
                )
                SELECT 
                    COALESCE(c.resource_group, p.resource_group, 'Unknown') as "TeamGroup",
                    COALESCE(c.service_name, p.service_name) as "Service",
                    COALESCE(c.subscription_id, p.subscription_id) as "Subscription",
                    ROUND(COALESCE(c.current_cost, 0)::numeric, 2) as "Latest Month",
                    ROUND(COALESCE(p.previous_cost, 0)::numeric, 2) as "Previous Month",
                    ROUND((COALESCE(c.current_cost, 0) - COALESCE(p.previous_cost, 0))::numeric, 2) as "Change",
                    CASE 
                        WHEN COALESCE(p.previous_cost, 0) > 0 
                        THEN ROUND(((COALESCE(c.current_cost, 0) - COALESCE(p.previous_cost, 0)) / p.previous_cost * 100)::numeric, 2)
                        WHEN COALESCE(c.current_cost, 0) > 0
                        THEN 100.00
                        ELSE 0
                    END as "MoM"
                FROM current_month c
                FULL OUTER JOIN previous_month p 
                    ON c.subscription_id = p.subscription_id 
                    AND c.service_name = p.service_name
                    AND COALESCE(c.resource_group, '') = COALESCE(p.resource_group, '')
                WHERE COALESCE(c.current_cost, 0) > 0 OR COALESCE(p.previous_cost, 0) > 0
                ORDER BY ABS(COALESCE(c.current_cost, 0) - COALESCE(p.previous_cost, 0)) DESC;
            """
        }],
        "title": "📊 Detailed Cost Analysis by TeamGroup, Service & Subscription",
        "type": "table"
    })
    
    y_pos += 12
    panel_id += 1
    
    # Row 6: Month-over-Month Change Table by Service (Original)
    panels.append({
        "datasource": {"type": "postgres", "uid": "PCC52D03280B7034C"},
        "fieldConfig": {
            "defaults": {
                "custom": {
                    "align": "auto",
                    "cellOptions": {"type": "auto"},
                    "inspect": False
                },
                "mappings": [],
                "thresholds": {
                    "mode": "absolute",
                    "steps": [{"color": "green", "value": None}]
                }
            },
            "overrides": [
                {
                    "matcher": {"id": "byName", "options": "Current Month"},
                    "properties": [{"id": "unit", "value": "currencyUSD"}]
                },
                {
                    "matcher": {"id": "byName", "options": "Previous Month"},
                    "properties": [{"id": "unit", "value": "currencyUSD"}]
                },
                {
                    "matcher": {"id": "byName", "options": "Difference"},
                    "properties": [
                        {"id": "unit", "value": "currencyUSD"},
                        {
                            "id": "custom.cellOptions",
                            "value": {"type": "color-background"}
                        },
                        {
                            "id": "thresholds",
                            "value": {
                                "mode": "absolute",
                                "steps": [
                                    {"color": "green", "value": None},
                                    {"color": "yellow", "value": 0},
                                    {"color": "orange", "value": 1000},
                                    {"color": "red", "value": 5000}
                                ]
                            }
                        }
                    ]
                },
                {
                    "matcher": {"id": "byName", "options": "Change %"},
                    "properties": [
                        {"id": "unit", "value": "percent"},
                        {
                            "id": "custom.cellOptions",
                            "value": {"type": "color-background"}
                        },
                        {
                            "id": "thresholds",
                            "value": {
                                "mode": "absolute",
                                "steps": [
                                    {"color": "green", "value": None},
                                    {"color": "green", "value": -20},
                                    {"color": "yellow", "value": -10},
                                    {"color": "orange", "value": 0},
                                    {"color": "red", "value": 10}
                                ]
                            }
                        }
                    ]
                }
            ]
        },
        "gridPos": {"h": 10, "w": 24, "x": 0, "y": y_pos},
        "id": panel_id,
        "options": {
            "cellHeight": "sm",
            "footer": {"countRows": False, "fields": "", "reducer": ["sum"], "show": True},
            "showHeader": True,
            "sortBy": [{"desc": True, "displayName": "Change %"}]
        },
        "pluginVersion": "11.4.0",
        "targets": [{
            "datasource": {"type": "postgres", "uid": "PCC52D03280B7034C"},
            "format": "table",
            "rawQuery": True,
            "rawSql": """
                WITH current_month AS (
                    SELECT 
                        service_name,
                        SUM(cost) as current_cost
                    FROM cost_records
                    WHERE date >= DATE_TRUNC('month', CURRENT_DATE)
                      AND date < DATE_TRUNC('month', CURRENT_DATE + INTERVAL '1 month')
                      AND subscription_id = '$subscription'
                    GROUP BY service_name
                ),
                previous_month AS (
                    SELECT 
                        service_name,
                        SUM(cost) as previous_cost
                    FROM cost_records
                    WHERE date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')
                      AND date < DATE_TRUNC('month', CURRENT_DATE)
                      AND subscription_id = '$subscription'
                    GROUP BY service_name
                )
                SELECT 
                    COALESCE(c.service_name, p.service_name) as "Service",
                    ROUND(COALESCE(c.current_cost, 0)::numeric, 2) as "Current Month",
                    ROUND(COALESCE(p.previous_cost, 0)::numeric, 2) as "Previous Month",
                    ROUND((COALESCE(c.current_cost, 0) - COALESCE(p.previous_cost, 0))::numeric, 2) as "Difference",
                    CASE 
                        WHEN COALESCE(p.previous_cost, 0) > 0 
                        THEN ROUND(((COALESCE(c.current_cost, 0) - COALESCE(p.previous_cost, 0)) / p.previous_cost * 100)::numeric, 1)
                        ELSE 0
                    END as "Change %"
                FROM current_month c
                FULL OUTER JOIN previous_month p ON c.service_name = p.service_name
                WHERE COALESCE(c.current_cost, 0) > 0 OR COALESCE(p.previous_cost, 0) > 0
                ORDER BY "Change %" DESC NULLS LAST;
            """
        }],
        "title": "📊 Month-over-Month Change by Service",
        "type": "table"
    })
    
    # Create dashboard
    dashboard = {
        "annotations": {"list": []},
        "editable": True,
        "fiscalYearStartMonth": 0,
        "graphTooltip": 1,
        "id": None,
        "links": [],
        "panels": panels,
        "refresh": "5m",
        "schemaVersion": 39,
        "tags": ["azure", "cost-analysis", "trends"],
        "templating": {
            "list": [
                {
                    "current": {},
                    "datasource": {"type": "postgres", "uid": "PCC52D03280B7034C"},
                    "definition": "SELECT DISTINCT subscription_id FROM cost_records ORDER BY subscription_id",
                    "hide": 0,
                    "includeAll": False,
                    "label": "Subscription",
                    "multi": False,
                    "name": "subscription",
                    "options": [],
                    "query": "SELECT DISTINCT subscription_id FROM cost_records ORDER BY subscription_id",
                    "refresh": 1,
                    "regex": "",
                    "skipUrlSync": False,
                    "sort": 0,
                    "type": "query"
                }
            ]
        },
        "time": {"from": "now-90d", "to": "now"},
        "timepicker": {},
        "timezone": "browser",
        "title": "Azure Cost Trends & Analysis",
        "uid": "azure-cost-trends",
        "version": 0
    }
    
    return dashboard


def main():
    """Generate the enhanced cost dashboard"""
    print("🎨 Generating Enhanced Cost Dashboard...")
    
    dashboard = create_enhanced_cost_dashboard()
    
    # Save dashboard
    output_file = "config/grafana/dashboards/azure-cost-trends.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(dashboard, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Dashboard created: {output_file}")
    print(f"📊 Features:")
    print(f"   • Month-over-Month cost change tracking")
    print(f"   • Stacked area chart (sandwich chart) by service")
    print(f"   • Stacked area chart by subscription & service")
    print(f"   • Detailed MoM change table with color coding")
    print(f"\n🔄 Restart Grafana to see the new dashboard")


if __name__ == "__main__":
    main()
