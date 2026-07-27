"""
Generate dashboard matching AI Cost Optimization Recommendations look/feel
- Same column sequence and styling
- Real Azure OpenAI data from database
- Pagination (5 recommendations per page)
"""

import psycopg2
import json

# Database connection
conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="azure_cost_dev",
    user="postgres",
    password="AzureCost2025!DbPass"
)

cursor = conn.cursor()

# Fetch all recommendations
cursor.execute("""
    SELECT 
        id, service_name, title, description, recommendation_text,
        potential_savings, current_cost, savings_percentage,
        priority, implementation_effort, category
    FROM ai_recommendations 
    WHERE status = 'pending'
    ORDER BY potential_savings DESC;
""")

recommendations = cursor.fetchall()
total_recommendations = len(recommendations)

conn.close()

def parse_steps_to_numbered_list(text):
    """Parse JSON array or text into numbered markdown list"""
    if not text:
        return ""
    
    # Try to parse as JSON array
    try:
        steps = json.loads(text)
        if isinstance(steps, list):
            return "\n\n".join([f"{i+1}. {step}" for i, step in enumerate(steps)])
    except:
        pass
    
    # Return as-is if already formatted
    return text

def generate_detail_panel(rec, rank, y_position, panel_id):
    """Generate detail panel matching the original template style"""
    rec_id, service_name, title, description, recommendation_text, \
    potential_savings, current_cost, savings_percentage, \
    priority, implementation_effort, category = rec
    
    priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(priority.lower() if priority else "medium", "🟡")
    
    # Parse steps
    impl_steps = parse_steps_to_numbered_list(recommendation_text)
    
    # Build markdown content in original template style
    content = f"""# {priority_emoji} {rank}. {title}

**💰 Potential Monthly Savings:** ${potential_savings:,.2f} ({savings_percentage:.1f}% reduction)

**🎯 Priority:** {priority.upper() if priority else 'MEDIUM'} | **⏱️ Effort:** {implementation_effort or 'medium'} | **⚠️ Risk:** LOW

**📊 Service:** {service_name} | **💵 Current Cost:** ${current_cost:,.2f}/month

---

## 📋 Current Issue

{description}

---

## 💡 Recommendation

{title}

---

## 📋 Implementation Steps

{impl_steps}


---

## ✅ Best Practices

- Review the implementation steps carefully before making changes
- Test changes in a non-production environment first
- Monitor performance metrics after implementation
- Document configuration changes for audit trail
- Validate cost savings after 7 days
- Set up alerts for cost anomalies
- Schedule regular reviews of optimization effectiveness

---

## 📚 Helpful Resources

- [Azure Cost Management Best Practices](https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/cost-mgt-best-practices)
- [Azure Well-Architected Framework - Cost Optimization](https://learn.microsoft.com/en-us/azure/well-architected/cost/)
- [Azure Advisor Cost Recommendations](https://learn.microsoft.com/en-us/azure/advisor/advisor-cost-recommendations)
- [Azure Pricing Calculator](https://azure.microsoft.com/en-us/pricing/calculator/)
"""
    
    return {
        "datasource": {
            "type": "postgres",
            "uid": "PCC52D03280B7034C"
        },
        "gridPos": {
            "h": 20,
            "w": 24,
            "x": 0,
            "y": y_position
        },
        "id": panel_id,
        "options": {
            "code": {
                "language": "plaintext",
                "showLineNumbers": False,
                "showMiniMap": False
            },
            "content": content,
            "mode": "markdown"
        },
        "pluginVersion": "11.4.0",
        "title": f"{priority_emoji} {service_name} - {title}",
        "type": "text"
    }

# Create dashboard panels
panels = []

# Panel 1-4: Stats (same as original)
panels.extend([
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
                        {"color": "#6bcf7f", "value": 50},
                        {"color": "#4ecdc4", "value": 100}
                    ]
                },
                "unit": "currencyUSD"
            }
        },
        "gridPos": {"h": 6, "w": 6, "x": 0, "y": 0},
        "id": 1,
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
            "rawSql": "SELECT SUM(potential_savings) as \"Potential Monthly Savings\" FROM ai_recommendations WHERE status = 'pending';"
        }],
        "title": "💰 Total Potential Savings",
        "type": "stat"
    },
    {
        "datasource": {"type": "postgres", "uid": "PCC52D03280B7034C"},
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "thresholds"},
                "mappings": [],
                "thresholds": {
                    "mode": "absolute",
                    "steps": [
                        {"color": "#a8dadc", "value": None},
                        {"color": "#457b9d", "value": 3},
                        {"color": "#1d3557", "value": 5}
                    ]
                }
            }
        },
        "gridPos": {"h": 6, "w": 6, "x": 6, "y": 0},
        "id": 2,
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
            "rawSql": "SELECT COUNT(*) as \"Active Recommendations\" FROM ai_recommendations WHERE status = 'pending';"
        }],
        "title": "📋 Active Recommendations",
        "type": "stat"
    },
    {
        "datasource": {"type": "postgres", "uid": "PCC52D03280B7034C"},
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "thresholds"},
                "mappings": [
                    {
                        "options": {
                            "high": {"color": "red", "index": 0, "text": "High Priority"},
                            "medium": {"color": "yellow", "index": 1, "text": "Medium Priority"},
                            "low": {"color": "green", "index": 2, "text": "Low Priority"}
                        },
                        "type": "value"
                    }
                ],
                "thresholds": {
                    "mode": "absolute",
                    "steps": [{"color": "green", "value": None}]
                }
            }
        },
        "gridPos": {"h": 6, "w": 6, "x": 12, "y": 0},
        "id": 3,
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
            "rawSql": "SELECT COUNT(*) as value, priority as metric FROM ai_recommendations WHERE status = 'pending' GROUP BY priority ORDER BY CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END LIMIT 1;"
        }],
        "title": "🎯 Highest Priority",
        "type": "stat"
    },
    {
        "datasource": {"type": "postgres", "uid": "PCC52D03280B7034C"},
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "thresholds"},
                "mappings": [],
                "thresholds": {
                    "mode": "absolute",
                    "steps": [
                        {"color": "#ffd93d", "value": None},
                        {"color": "#f77f00", "value": 20},
                        {"color": "#e63946", "value": 30}
                    ]
                },
                "unit": "percent"
            }
        },
        "gridPos": {"h": 6, "w": 6, "x": 18, "y": 0},
        "id": 4,
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
            "rawSql": "SELECT (SUM(potential_savings) / SUM(current_cost) * 100) as \"Avg Savings Potential\" FROM ai_recommendations WHERE status = 'pending';"
        }],
        "title": "📈 Average Savings %",
        "type": "stat"
    }
])

# Panel 5: Overview header
panels.append({
    "datasource": {"type": "postgres", "uid": "PCC52D03280B7034C"},
    "gridPos": {"h": 7, "w": 24, "x": 0, "y": 6},
    "id": 5,
    "options": {
        "code": {"language": "plaintext", "showLineNumbers": False, "showMiniMap": False},
        "content": """<div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 10px; color: white; text-align: center;">

<div style="background: rgba(255,255,255,0.1); padding: 15px; border-radius: 8px; margin-top: 15px;">

💡 **Smart Insights from Real Azure OpenAI GPT-4**

Discover detailed, actionable recommendations to optimize your cloud costs. Each recommendation includes:

🔍 **Current Issue Analysis** • 📋 **Step-by-Step Implementation** • ✅ **Best Practices** • 🔗 **Azure Documentation Links**

</div>

</div>""",
        "mode": "markdown"
    },
    "pluginVersion": "11.4.0",
    "title": "Overview",
    "type": "text"
})

# Panel 6: Summary table with exact same column sequence
panels.append({
    "datasource": {"type": "postgres", "uid": "PCC52D03280B7034C"},
    "fieldConfig": {
        "defaults": {
            "custom": {"align": "auto", "cellOptions": {"type": "auto"}, "inspect": False},
            "mappings": [],
            "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": None}]}
        },
        "overrides": [
            {
                "matcher": {"id": "byName", "options": "Priority"},
                "properties": [
                    {"id": "custom.cellOptions", "value": {"type": "color-background"}},
                    {
                        "id": "mappings",
                        "value": [{
                            "options": {
                                "high": {"color": "red", "index": 0, "text": "🔴 HIGH"},
                                "medium": {"color": "yellow", "index": 1, "text": "🟡 MEDIUM"},
                                "low": {"color": "green", "index": 2, "text": "🟢 LOW"}
                            },
                            "type": "value"
                        }]
                    }
                ]
            },
            {
                "matcher": {"id": "byName", "options": "Potential Savings"},
                "properties": [
                    {"id": "unit", "value": "currencyUSD"},
                    {"id": "custom.cellOptions", "value": {"type": "color-background", "mode": "gradient"}},
                    {"id": "color", "value": {"mode": "continuous-GrYlRd"}}
                ]
            },
            {
                "matcher": {"id": "byName", "options": "Current Cost"},
                "properties": [{"id": "unit", "value": "currencyUSD"}]
            },
            {
                "matcher": {"id": "byName", "options": "Savings %"},
                "properties": [{"id": "unit", "value": "percent"}]
            }
        ]
    },
    "gridPos": {"h": 8, "w": 24, "x": 0, "y": 13},
    "id": 6,
    "options": {
        "cellHeight": "sm",
        "footer": {"countRows": False, "fields": "", "reducer": ["sum"], "show": False},
        "showHeader": True,
        "sortBy": [{"desc": True, "displayName": "Potential Savings"}]
    },
    "pluginVersion": "11.4.0",
    "targets": [{
        "datasource": {"type": "postgres", "uid": "PCC52D03280B7034C"},
        "format": "table",
        "rawQuery": True,
        "rawSql": """SELECT 
  priority as "Priority",
  service_name as "Service",
  title as "Recommendation",
  ROUND(current_cost::numeric, 2) as "Current Cost",
  ROUND(potential_savings::numeric, 2) as "Potential Savings",
  savings_percentage as "Savings %",
  implementation_effort as "Effort",
  category as "Category"
FROM ai_recommendations 
WHERE status = 'pending'
ORDER BY potential_savings DESC;"""
    }],
    "title": "💡 Recommendations Summary",
    "type": "table"
})

# Generate detail panels with pagination (5 per page)
current_y = 21
panel_id = 11
ITEMS_PER_PAGE = 5
total_pages = (total_recommendations + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE

for page in range(total_pages):
    start_idx = page * ITEMS_PER_PAGE
    end_idx = min(start_idx + ITEMS_PER_PAGE, total_recommendations)
    
    # Page divider
    if page > 0:
        current_y += 2
    
    # Add recommendations for this page
    for i in range(start_idx, end_idx):
        rec = recommendations[i]
        panel = generate_detail_panel(rec, i + 1, current_y, panel_id)
        panels.append(panel)
        current_y += 20
        panel_id += 1
    
    # Page break marker (except after last page)
    if page < total_pages - 1:
        panels.append({
            "datasource": {"type": "postgres", "uid": "PCC52D03280B7034C"},
            "gridPos": {"h": 2, "w": 24, "x": 0, "y": current_y},
            "id": panel_id,
            "options": {
                "code": {"language": "plaintext", "showLineNumbers": False, "showMiniMap": False},
                "content": f"---\n\n## 📄 Page {page + 2} of {total_pages} | Recommendations {end_idx + 1}-{min(end_idx + ITEMS_PER_PAGE, total_recommendations)} of {total_recommendations}\n\n---",
                "mode": "markdown"
            },
            "pluginVersion": "11.4.0",
            "title": "",
            "type": "text",
            "transparent": True
        })
        current_y += 2
        panel_id += 1

# Create final dashboard
dashboard = {
    "annotations": {"list": []},
    "editable": True,
    "fiscalYearStartMonth": 0,
    "graphTooltip": 0,
    "id": None,
    "links": [],
    "panels": panels,
    "refresh": "",
    "schemaVersion": 39,
    "tags": ["azure", "cost-optimization", "ai-recommendations"],
    "templating": {"list": []},
    "time": {"from": "now-30d", "to": "now"},
    "timepicker": {},
    "timezone": "",
    "title": "AI Cost Optimization Recommendations",
    "uid": "ai-cost-optimization-real",
    "version": 0
}

# Save dashboard
output_file = "config/grafana/dashboards/ai-recommendations-real.json"
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(dashboard, f, indent=2, ensure_ascii=False)

print(f"✅ Dashboard generated: {output_file}")
print(f"📊 Total recommendations: {total_recommendations}")
print(f"📄 Pages: {total_pages} ({ITEMS_PER_PAGE} per page)")
print(f"🎨 Style: Matching AI Cost Optimization Recommendations")
print(f"🔄 Restart Grafana to see the updated dashboard")
