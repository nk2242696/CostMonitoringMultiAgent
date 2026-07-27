"""
Generate Enhanced Grafana Dashboard with Real Azure OpenAI Recommendations
- Pagination (5 recommendations per page)
- Color-coded priorities and savings
- Point-wise implementation steps and best practices
"""

import psycopg2
import json
import re

# Database connection
conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="azure_cost_dev",
    user="postgres",
    password="AzureCost2025!DbPass"
)

cursor = conn.cursor()

# Fetch recommendations ordered by potential savings
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

cursor.execute("SELECT SUM(potential_savings) FROM ai_recommendations WHERE status = 'pending';")
total_savings = cursor.fetchone()[0]

cursor.execute("SELECT SUM(current_cost) FROM ai_recommendations WHERE status = 'pending';")
total_cost = cursor.fetchone()[0]

conn.close()

# Helper functions
def get_priority_color(priority):
    """Return color emoji and background color for priority"""
    priority = priority.lower() if priority else "medium"
    if priority == "high":
        return "🔴", "#ff6b6b"
    elif priority == "medium":
        return "🟡", "#ffd93d"
    else:
        return "🟢", "#6bcf7f"

def get_savings_color(savings):
    """Return color based on savings amount"""
    if savings >= 8000:
        return "#ff6b6b"  # Red for high savings
    elif savings >= 6000:
        return "#ffd93d"  # Yellow for medium savings
    else:
        return "#6bcf7f"  # Green for lower savings

def parse_steps_to_list(text):
    """Parse JSON array or text into markdown list"""
    if not text:
        return ""
    
    # Try to parse as JSON array
    try:
        steps = json.loads(text)
        if isinstance(steps, list):
            return "\n".join([f"- {step}" for step in steps])
    except:
        pass
    
    # Parse numbered list format
    lines = text.split('\n')
    result = []
    for line in lines:
        line = line.strip()
        if line and (line[0].isdigit() or line.startswith('Step')):
            # Remove numbering
            line = re.sub(r'^(\d+\.|\d+\)|\w+\s+\d+:)', '', line).strip()
            result.append(f"- {line}")
        elif line.startswith('-') or line.startswith('•'):
            result.append(f"- {line[1:].strip()}")
    
    return "\n".join(result) if result else text

def generate_recommendation_panel(rec, rank, y_position):
    """Generate a single recommendation detail panel"""
    rec_id, service_name, title, description, recommendation_text, \
    potential_savings, current_cost, savings_percentage, \
    priority, implementation_effort, category = rec
    
    priority_emoji, priority_color = get_priority_color(priority)
    savings_color = get_savings_color(potential_savings)
    
    # Parse steps
    action_steps = parse_steps_to_list(recommendation_text)
    
    # Build markdown content
    content = f"""# {priority_emoji} {rank}. {title}

<div style="background: linear-gradient(135deg, {savings_color}22 0%, {priority_color}22 100%); padding: 15px; border-radius: 8px; border-left: 4px solid {savings_color};">

### 💰 Potential Monthly Savings: **${potential_savings:,.2f}** ({savings_percentage:.1f}% reduction)

**🎯 Priority:** {priority_emoji} **{priority.upper() if priority else 'MEDIUM'}** | **⏱️ Effort:** **{implementation_effort.upper() if implementation_effort else 'MEDIUM'}**

**📊 Service:** **{service_name}** | **💵 Current Cost:** **${current_cost:,.2f}/month**

</div>

---

## 📋 Current Issue

{description}

---

## 💡 Implementation Steps

{action_steps}

---

## ✅ Key Benefits

- **Immediate Cost Reduction:** Save ${potential_savings:,.2f} monthly
- **Resource Optimization:** Improve {service_name} efficiency
- **Performance Enhancement:** Better resource allocation
- **Scalability:** Right-sized for your workload

---

## 📚 Recommended Actions

1. **Review** the implementation steps carefully
2. **Test** changes in a non-production environment first
3. **Monitor** performance metrics after implementation
4. **Document** configuration changes for audit trail
5. **Validate** cost savings after 7 days

"""
    
    return {
        "datasource": {
            "type": "postgres",
            "uid": "PCC52D03280B7034C"
        },
        "gridPos": {
            "h": 22,
            "w": 24,
            "x": 0,
            "y": y_position
        },
        "id": 100 + rec_id,
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

# Generate dashboard panels
panels = []
current_y = 0

# Summary Stats
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
                        {"color": "#6bcf7f", "value": 50000},
                        {"color": "#4ecdc4", "value": 100000}
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
                        {"color": "#1d3557", "value": 7}
                    ]
                }
            }
        },
        "gridPos": {"h": 6, "w": 6, "x": 6, "y": 0},
        "id": 2,
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
            "rawSql": "SELECT COUNT(*) as \"Active Recommendations\" FROM ai_recommendations WHERE status = 'pending';"
        }],
        "title": "📊 Active Recommendations",
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
                        {"color": "#f08080", "value": None},
                        {"color": "#ee6c4d", "value": 5}
                    ]
                }
            }
        },
        "gridPos": {"h": 6, "w": 6, "x": 12, "y": 0},
        "id": 3,
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
            "rawSql": "SELECT COUNT(*) as \"High Priority\" FROM ai_recommendations WHERE status = 'pending' AND priority = 'high';"
        }],
        "title": "🔴 High Priority Items",
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
                        {"color": "#90e0ef", "value": None},
                        {"color": "#00b4d8", "value": 20}
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
            "rawSql": f"SELECT {(total_savings/total_cost*100):.1f} as \"Potential Savings %\";"
        }],
        "title": "📈 Potential Cost Reduction",
        "type": "stat"
    }
])

# Summary Table
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
                "properties": [{
                    "id": "mappings",
                    "value": [
                        {"options": {"high": {"color": "red", "index": 0, "text": "🔴 HIGH"}}, "type": "value"},
                        {"options": {"medium": {"color": "yellow", "index": 1, "text": "🟡 MEDIUM"}}, "type": "value"},
                        {"options": {"low": {"color": "green", "index": 2, "text": "🟢 LOW"}}, "type": "value"}
                    ]
                }]
            },
            {
                "matcher": {"id": "byName", "options": "Potential Savings"},
                "properties": [
                    {"id": "unit", "value": "currencyUSD"},
                    {"id": "custom.cellOptions", "value": {"type": "color-background"}},
                    {"id": "thresholds", "value": {
                        "mode": "absolute",
                        "steps": [
                            {"color": "green", "value": None},
                            {"color": "yellow", "value": 6000},
                            {"color": "red", "value": 8000}
                        ]
                    }}
                ]
            }
        ]
    },
    "gridPos": {"h": 13, "w": 24, "x": 0, "y": 6},
    "id": 5,
    "options": {"cellHeight": "sm", "footer": {"countRows": False, "fields": "", "reducer": ["sum"], "show": False}, "showHeader": True},
    "pluginVersion": "11.4.0",
    "targets": [{
        "datasource": {"type": "postgres", "uid": "PCC52D03280B7034C"},
        "format": "table",
        "rawQuery": True,
        "rawSql": """
            SELECT 
                ROW_NUMBER() OVER (ORDER BY potential_savings DESC) as "#",
                service_name as "Service",
                title as "Recommendation",
                potential_savings as "Potential Savings",
                priority as "Priority",
                implementation_effort as "Effort"
            FROM ai_recommendations 
            WHERE status = 'pending'
            ORDER BY potential_savings DESC;
        """
    }],
    "title": "📋 AI Recommendations Summary",
    "type": "table"
})

current_y = 19

# Generate detail panels with pagination (5 per page)
ITEMS_PER_PAGE = 5
total_pages = (total_recommendations + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE

for page in range(total_pages):
    # Page header
    start_idx = page * ITEMS_PER_PAGE
    end_idx = min(start_idx + ITEMS_PER_PAGE, total_recommendations)
    
    page_header = {
        "datasource": {"type": "postgres", "uid": "PCC52D03280B7034C"},
        "gridPos": {"h": 3, "w": 24, "x": 0, "y": current_y},
        "id": 50 + page,
        "options": {
            "code": {"language": "plaintext", "showLineNumbers": False, "showMiniMap": False},
            "content": f"# 📄 Page {page + 1} of {total_pages} | Recommendations {start_idx + 1}-{end_idx} of {total_recommendations}",
            "mode": "markdown"
        },
        "pluginVersion": "11.4.0",
        "title": "",
        "type": "text",
        "transparent": True
    }
    panels.append(page_header)
    current_y += 3
    
    # Add recommendations for this page
    for i in range(start_idx, end_idx):
        rec = recommendations[i]
        panel = generate_recommendation_panel(rec, i + 1, current_y)
        panels.append(panel)
        current_y += 22

# Create complete dashboard
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
    "timezone": "browser",
    "title": "🤖 AI Cost Optimization Recommendations (Real Azure OpenAI)",
    "uid": "ai-recommendations-real",
    "version": 0,
    "weekStart": ""
}

# Save dashboard
output_file = "config/grafana/dashboards/ai-recommendations-real.json"
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(dashboard, f, indent=2, ensure_ascii=False)

print(f"✅ Enhanced dashboard generated: {output_file}")
print(f"📊 Total recommendations: {total_recommendations}")
print(f"📄 Total pages: {total_pages} ({ITEMS_PER_PAGE} recommendations per page)")
print(f"💰 Total potential savings: ${total_savings:,.2f}")
print(f"🔄 Restart Grafana to load the new dashboard")
