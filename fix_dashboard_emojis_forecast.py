"""
Fix emoji encoding issues and update forecast to show multi-month trend line.
"""
import json

def fix_dashboard():
    """Fix emojis and update forecast panel."""
    
    # Read dashboard
    with open('config/grafana/dashboards/azure-cost-trends.json', 'r', encoding='utf-8') as f:
        dashboard = json.load(f)
    
    # Fix emoji titles - remove emojis entirely
    title_fixes = {
        "\u00f0\u0178\u2019\u00b0 Total Cost (Current Month)": "Total Cost (Current Month)",
        "\u00f0\u0178\u201c\u02c6 Month-over-Month Change": "Month-over-Month Change",
        "\u00f0\u0178\u201d\u00a7 Active Services": "Active Services",
        "\u00f0\u0178\u201c\u2039 Active Subscriptions": "Active Subscriptions",
        "\u00f0\u0178\u201c\u0160 Cost Breakdown by Service Over Time (Stacked Area Chart)": "Cost Breakdown by Service Over Time (Stacked Area Chart)",
        "\u00f0\u0178\u201c\u0160 Monthly Forecast": "Multi-Month Cost Forecast",
        "\u00f0\u0178\u201c\u0160 Detailed Cost Analysis by TeamGroup, Service & Subscription": "Detailed Cost Analysis by TeamGroup, Service & Subscription",
        "\u00f0\u0178\u201c\u0160 Month-over-Month Change by Service": "Month-over-Month Change by Service"
    }
    
    # Update all panel titles
    for panel in dashboard['panels']:
        if 'title' in panel:
            for old_title, new_title in title_fixes.items():
                if panel['title'] == old_title:
                    panel['title'] = new_title
                    print(f"✓ Fixed: {new_title}")
        
        # Find and update the forecast panel
        if 'Multi-Month Cost Forecast' in panel.get('title', ''):
            print("\n🔄 Updating forecast panel to time series line chart...")
            
            # Change from barchart to timeseries
            panel['type'] = 'timeseries'
            
            # Update options for time series
            panel['options'] = {
                "legend": {
                    "calcs": ["mean", "lastNotNull"],
                    "displayMode": "table",
                    "placement": "bottom",
                    "showLegend": True
                },
                "tooltip": {
                    "mode": "multi",
                    "sort": "none"
                }
            }
            
            # Update field config for line chart
            panel['fieldConfig'] = {
                "defaults": {
                    "color": {
                        "mode": "palette-classic"
                    },
                    "custom": {
                        "axisCenteredZero": False,
                        "axisColorMode": "text",
                        "axisLabel": "",
                        "axisPlacement": "auto",
                        "barAlignment": 0,
                        "drawStyle": "line",
                        "fillOpacity": 20,
                        "gradientMode": "none",
                        "hideFrom": {
                            "tooltip": False,
                            "viz": False,
                            "legend": False
                        },
                        "lineInterpolation": "smooth",
                        "lineWidth": 2,
                        "pointSize": 5,
                        "scaleDistribution": {
                            "type": "linear"
                        },
                        "showPoints": "auto",
                        "spanNulls": False,
                        "stacking": {
                            "group": "A",
                            "mode": "none"
                        },
                        "thresholdsStyle": {
                            "mode": "off"
                        }
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
                    },
                    "unit": "currencyUSD"
                },
                "overrides": [
                    {
                        "matcher": {
                            "id": "byName",
                            "options": "Historical"
                        },
                        "properties": [
                            {
                                "id": "color",
                                "value": {
                                    "fixedColor": "blue",
                                    "mode": "fixed"
                                }
                            }
                        ]
                    },
                    {
                        "matcher": {
                            "id": "byName",
                            "options": "Forecast"
                        },
                        "properties": [
                            {
                                "id": "color",
                                "value": {
                                    "fixedColor": "orange",
                                    "mode": "fixed"
                                }
                            },
                            {
                                "id": "custom.lineStyle",
                                "value": {
                                    "dash": [10, 10],
                                    "fill": "dash"
                                }
                            }
                        ]
                    }
                ]
            }
            
            # Update SQL query for multi-month forecast
            panel['targets'][0]['rawSql'] = """
                -- Historical monthly costs (last 6 months)
                WITH historical_months AS (
                    SELECT 
                        DATE_TRUNC('month', date) as month,
                        SUM(cost) as total_cost
                    FROM cost_records
                    WHERE date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '5 months')
                      AND date < DATE_TRUNC('month', CURRENT_DATE + INTERVAL '1 month')
                      AND subscription_id = '$subscription'
                    GROUP BY DATE_TRUNC('month', date)
                    ORDER BY month
                ),
                -- Calculate trend (simple linear regression slope)
                trend_calc AS (
                    SELECT 
                        AVG(total_cost) as avg_cost,
                        -- Approximate growth rate based on first and last 2 months
                        CASE 
                            WHEN COUNT(*) >= 4 THEN
                                (AVG(CASE WHEN month >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month') THEN total_cost END) - 
                                 AVG(CASE WHEN month < DATE_TRUNC('month', CURRENT_DATE - INTERVAL '3 months') THEN total_cost END)) / 2
                            ELSE 0
                        END as monthly_change
                    FROM historical_months
                ),
                -- Generate forecast for next 3 months
                forecast_months AS (
                    SELECT 
                        DATE_TRUNC('month', CURRENT_DATE + INTERVAL '1 month') + (n || ' months')::interval as month,
                        (SELECT avg_cost + (monthly_change * (n + 1)) FROM trend_calc) as total_cost
                    FROM generate_series(0, 2) as n
                )
                -- Combine historical and forecast
                SELECT month as time, total_cost as "Historical"
                FROM historical_months
                UNION ALL
                SELECT month as time, total_cost as "Forecast"
                FROM forecast_months
                ORDER BY time;
            """
            
            print("✓ Forecast updated to multi-month time series")
    
    # Save updated dashboard
    with open('config/grafana/dashboards/azure-cost-trends.json', 'w', encoding='utf-8') as f:
        json.dump(dashboard, f, indent=2, ensure_ascii=False)
    
    print("\n✅ Dashboard fixed successfully!")
    print("\n📋 Changes made:")
    print("   1. Removed all emoji encoding issues from titles")
    print("   2. Converted forecast from bar chart to line chart")
    print("   3. Added 6 months historical + 3 months forecast")
    print("   4. Historical line (blue solid) + Forecast line (orange dashed)")
    print("\n🔄 Restart Grafana: docker restart azure-cost-grafana")

if __name__ == "__main__":
    fix_dashboard()
