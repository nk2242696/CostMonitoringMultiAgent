# Technical Review & Enhancement Roadmap
## Azure Cost Monitoring System - Production Grade Assessment

**Review Date:** November 7, 2025  
**Reviewer:** Senior Software Engineer  
**System Version:** 1.0 (Current State)

---

## 📊 Executive Summary

### System Overview
A Docker-based Azure cost monitoring platform with:
- **5 microservices** (PostgreSQL/TimescaleDB, Prometheus, Grafana, FastAPI, Exporter)
- **Real Azure data ingestion** (565 records, 1 subscription, 11 services, 30-day window)
- **3 Grafana dashboards** (basic costs, AI recommendations, top-down analysis)
- **AI-powered recommendations** via Azure OpenAI

### Health Score: 6.5/10 🟡

**Strengths:** Solid foundation, real data integration, modern stack  
**Weaknesses:** Production readiness gaps, limited scalability, incomplete monitoring

---

## 🔍 Current State Analysis

### ✅ What's Working Well

#### 1. **Architecture Foundation (8/10)**
```
✓ Microservices architecture with Docker Compose
✓ PostgreSQL with TimescaleDB for time-series optimization
✓ Prometheus for metrics collection
✓ Grafana for visualization
✓ FastAPI for REST API
```

**Strengths:**
- Clean separation of concerns
- Industry-standard tools
- Containerized deployment
- Proper database indexing on `date`, `subscription_id`, `service_name`

**Evidence:**
```sql
-- Well-designed schema
Indexes:
    "azure_costs_pkey" PRIMARY KEY, btree (id)
    "ix_azure_costs_date" btree (date)
    "ix_azure_costs_service_name" btree (service_name)
    "ix_azure_costs_subscription_id" btree (subscription_id)
```

#### 2. **Data Collection (7/10)**
```python
# Real Azure Cost Management API integration
from src.monitoring.azure_cost_collector import AzureCostCollector

# Proper data model
class AzureCost(Base):
    subscription_id, service_name, resource_group, 
    resource_id, cost, currency, date, collected_at
```

**Strengths:**
- Real Azure Cost Management API integration
- 30-day historical data (Oct 8 - Nov 6, 2025)
- 565 cost records across 11 services
- Proper timestamp tracking

**Current Coverage:**
- 1 subscription (CSC-Eng-Common-NonProd)
- $281.97 total spend
- Services: Logic Apps ($165), Functions ($88), Defender ($14), Container Registry ($12)

#### 3. **Visualization Layer (7/10)**
**Working Dashboards:**
1. `azure-costs-dashboard.json` - Basic cost overview with 30-day filters
2. `ai-recommendations-enhanced.json` - AI recommendations with plain markdown
3. `azure-cost-analysis.json` - Top-down analysis (subscription → resource groups → services → resources)

**Strengths:**
- Multiple visualization types (pie charts, time series, tables, stat panels)
- Proper SQL queries with aggregations
- Currency formatting
- Legend configuration

---

### ❌ Critical Issues

#### 1. **Prometheus Exporter Failure (CRITICAL 🔴)**
```bash
Status: Restarting (1) 56 seconds ago
Error: ModuleNotFoundError: No module named 'prometheus_client'
```

**Impact:** 
- Metrics not being exported
- Prometheus scraping failing
- No real-time monitoring
- Alerting system non-functional

**Root Cause:** Missing dependency in Docker image

#### 2. **No Region Data (HIGH 🟠)**
```sql
-- Current schema lacks region column
-- Queries fail: SELECT ... region ... FROM azure_costs
```

**Impact:**
- Cannot show "Cost by Region" pie charts
- Location-based optimization impossible
- Compliance/governance reporting limited

**Current Workaround:** Pattern matching in resource group names (brittle)

#### 3. **Single Subscription Limitation (MEDIUM 🟡)**
```
Current: 1 subscription (CSC-Eng-Common-NonProd)
Enterprise Need: 50-500+ subscriptions
```

**Impact:**
- Not enterprise-ready
- No cross-subscription analytics
- Limited business value

#### 4. **No Alerting System (HIGH 🟠)**
```
Planned: Threshold alerts, anomaly detection, multi-channel notifications
Current: None implemented
```

**Impact:**
- Reactive instead of proactive cost management
- Budget overruns undetected
- No incident response

#### 5. **No Authentication/Authorization (CRITICAL 🔴)**
```
Grafana: admin/admin123 (default)
API: No auth middleware
Database: postgres/postgres
```

**Impact:**
- Security vulnerability
- Not production-ready
- Compliance violations (SOC2, ISO27001)

#### 6. **Limited Data Retention (MEDIUM 🟡)**
```
Current: 30 days (565 records)
Enterprise Need: 13+ months for YoY analysis
```

#### 7. **No High Availability (MEDIUM 🟡)**
```
Single instance for each service
No failover, no load balancing
SPOF: PostgreSQL, Grafana
```

#### 8. **Pie Chart Display Issues (LOW 🟢)**
```
Issue: Grafana pie charts showing "no data" despite valid queries
Root Cause: Query format (metric/value vs actual column names)
Status: Partially resolved, needs validation
```

---

## 🏗️ Technical Debt Assessment

### Code Quality (6/10)
**Good:**
- Python type hints in data models
- Environment variable configuration
- Logging setup
- SQLAlchemy ORM usage

**Needs Improvement:**
- No unit tests found
- No integration tests
- No CI/CD pipeline
- Hardcoded credentials in docker-compose.yml
- No error handling strategy
- Missing API documentation (OpenAPI/Swagger)

### Database Design (7/10)
**Good:**
- TimescaleDB for time-series optimization
- Proper indexing strategy
- Foreign key design

**Needs Improvement:**
- No partitioning strategy (will hit performance issues at scale)
- Missing columns: `region`, `tags`, `meter_category`, `resource_location`
- No data lifecycle management (archival, purging)
- No backup strategy documented

### Observability (4/10)
**Critical Gaps:**
- Prometheus exporter broken
- No distributed tracing (OpenTelemetry)
- No centralized logging (ELK/Loki)
- No SLIs/SLOs defined
- No error rate tracking
- No latency percentiles (p50, p95, p99)

---

## 🎯 Enhancement Roadmap

### Phase 1: Stabilization (Week 1-2) 🔥 CRITICAL

#### 1.1 Fix Prometheus Exporter
```dockerfile
# Dockerfile - Add missing dependency
RUN pip install prometheus-client==0.19.0
```

**Deliverables:**
- ✓ Fix ModuleNotFoundError
- ✓ Restart exporter container
- ✓ Verify metrics endpoint (http://localhost:8001/metrics)
- ✓ Configure Prometheus scraping

#### 1.2 Add Security Layer
```python
# API Authentication
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt

# Grafana LDAP/OAuth
GF_AUTH_LDAP_ENABLED=true
GF_AUTH_OAUTH_AUTO_LOGIN=true
```

**Deliverables:**
- ✓ JWT-based API authentication
- ✓ Grafana OAuth/LDAP integration
- ✓ PostgreSQL SSL connection
- ✓ Secrets management (Azure Key Vault / HashiCorp Vault)
- ✓ Role-based access control (RBAC)

#### 1.3 Multi-Subscription Support
```python
# Enhanced data collection
subscriptions = [
    "CSC-Eng-Common-NonProd",
    "CSC-Eng-Common-Prod",
    "CSC-Data-Platform-Dev",
    # ... 50+ subscriptions
]

# Parallel collection with asyncio
async def collect_all_subscriptions():
    tasks = [collect_subscription(sub_id) for sub_id in subscriptions]
    await asyncio.gather(*tasks)
```

**Deliverables:**
- ✓ Async Azure Cost Management API client
- ✓ Subscription configuration file (YAML/JSON)
- ✓ Rate limiting and retry logic
- ✓ Progress tracking dashboard

---

### Phase 2: Data Enrichment (Week 3-4) 📊

#### 2.1 Schema Enhancement
```sql
-- Add missing columns
ALTER TABLE azure_costs 
ADD COLUMN region VARCHAR(50),
ADD COLUMN resource_location VARCHAR(50),
ADD COLUMN meter_category VARCHAR(255),
ADD COLUMN meter_subcategory VARCHAR(255),
ADD COLUMN tags JSONB,
ADD COLUMN unit_of_measure VARCHAR(50),
ADD COLUMN quantity NUMERIC(18,6);

-- Add composite indexes
CREATE INDEX idx_costs_sub_service_date 
ON azure_costs(subscription_id, service_name, date DESC);

CREATE INDEX idx_costs_region_date 
ON azure_costs(region, date DESC);

-- Add GIN index for tags
CREATE INDEX idx_costs_tags ON azure_costs USING GIN (tags);
```

**Deliverables:**
- ✓ Migration script with rollback
- ✓ Backfill historical data
- ✓ Update collection scripts
- ✓ Update Grafana dashboards

#### 2.2 Tag-Based Cost Allocation
```python
# Cost center tagging
tags = {
    "CostCenter": "Engineering",
    "Environment": "Production",
    "Project": "DataPlatform",
    "Owner": "kumar.nikhi@company.com"
}

# Chargeback reports by tag
def generate_chargeback_report(cost_center: str, month: str):
    """Generate monthly chargeback report by cost center"""
```

**Deliverables:**
- ✓ Tag extraction from Azure resources
- ✓ Cost allocation dashboard
- ✓ Chargeback report automation
- ✓ Tag compliance monitoring

#### 2.3 Advanced Analytics
```python
# Forecasting with Prophet
from prophet import Prophet

def forecast_costs(historical_data, periods=30):
    """Forecast next 30 days of costs"""
    
# Anomaly detection with IsolationForest
from sklearn.ensemble import IsolationForest

def detect_anomalies(daily_costs):
    """Detect unusual spending patterns"""
```

**Deliverables:**
- ✓ ML-based cost forecasting (30, 60, 90 days)
- ✓ Anomaly detection alerts
- ✓ Trend analysis (MoM, YoY)
- ✓ Budget burn rate calculation

---

### Phase 3: Alerting System (Week 5-6) 🚨

#### 3.1 Rule Engine
```python
# Alert rules configuration
alert_rules = {
    "daily_budget_exceeded": {
        "condition": "daily_cost > budget * 1.2",
        "severity": "high",
        "channels": ["email", "slack", "pagerduty"]
    },
    "cost_spike_detected": {
        "condition": "daily_cost > avg_cost * 2",
        "severity": "medium",
        "channels": ["email", "slack"]
    },
    "subscription_over_budget": {
        "condition": "monthly_cost > budget",
        "severity": "critical",
        "channels": ["email", "slack", "teams", "pagerduty"]
    }
}
```

**Deliverables:**
- ✓ Flexible rule engine (YAML config)
- ✓ Multiple severity levels (critical, high, medium, low)
- ✓ Alert deduplication logic
- ✓ Alert acknowledgement workflow

#### 3.2 Notification Channels
```python
# Multi-channel notification
from integrations import (
    EmailNotifier,
    SlackNotifier,
    TeamsNotifier,
    PagerDutyNotifier,
    WebhookNotifier
)

class AlertManager:
    def send_alert(self, alert: Alert, channels: List[str]):
        for channel in channels:
            notifier = self.get_notifier(channel)
            notifier.send(alert)
```

**Deliverables:**
- ✓ Email (SMTP/SendGrid)
- ✓ Slack webhooks
- ✓ Microsoft Teams
- ✓ PagerDuty integration
- ✓ Custom webhooks
- ✓ SMS (Twilio)

#### 3.3 Alert Dashboard
```json
// Grafana alert panel
{
  "title": "Active Cost Alerts",
  "panels": [
    {"type": "stat", "title": "Critical Alerts"},
    {"type": "table", "title": "Recent Alerts"},
    {"type": "timeseries", "title": "Alert Frequency"}
  ]
}
```

---

### Phase 4: Optimization Engine (Week 7-8) 💰

#### 4.1 Azure Advisor Integration
```python
from azure.mgmt.advisor import AdvisorManagementClient

class AdvisorIntegration:
    def get_cost_recommendations(self, subscription_id):
        """Fetch Azure Advisor cost recommendations"""
        recommendations = self.client.recommendations.list(
            filter="Category eq 'Cost'"
        )
        return self.parse_recommendations(recommendations)
```

**Recommendation Types:**
- Right-size or shutdown underutilized VMs
- Buy reserved instances for better pricing
- Delete unattached disks
- Use Azure Hybrid Benefit
- Optimize storage tiers
- Remove unused IP addresses

#### 4.2 Custom Optimization Rules
```python
# Idle VM detection
def detect_idle_vms(threshold_cpu=5, days=7):
    """Find VMs with <5% CPU for 7+ days"""
    
# Orphaned resources
def find_orphaned_disks():
    """Find unattached managed disks"""
    
# Reserved instance recommendations
def calculate_ri_savings(vm_usage_data):
    """Calculate potential RI savings"""
```

#### 4.3 Savings Tracking
```sql
-- Savings table
CREATE TABLE cost_savings (
    id SERIAL PRIMARY KEY,
    recommendation_id VARCHAR(100),
    subscription_id VARCHAR(100),
    resource_id VARCHAR(500),
    recommendation_type VARCHAR(100),
    estimated_monthly_savings NUMERIC(18,2),
    actual_monthly_savings NUMERIC(18,2),
    status VARCHAR(50), -- pending, implemented, verified, rejected
    implemented_date TIMESTAMP,
    verified_date TIMESTAMP
);
```

---

### Phase 5: Enterprise Features (Week 9-12) 🏢

#### 5.1 Multi-Tenancy
```python
# Tenant isolation
class TenantContext:
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.subscriptions = get_tenant_subscriptions(tenant_id)
        
# Row-level security
CREATE POLICY tenant_isolation ON azure_costs
USING (subscription_id IN (
    SELECT subscription_id FROM tenant_subscriptions 
    WHERE tenant_id = current_setting('app.tenant_id')
));
```

**Deliverables:**
- ✓ Tenant-specific dashboards
- ✓ Data isolation policies
- ✓ Tenant provisioning API
- ✓ Usage billing per tenant

#### 5.2 High Availability
```yaml
# docker-compose-ha.yml
services:
  postgres-primary:
    image: timescale/timescaledb-ha:latest
    
  postgres-replica:
    image: timescale/timescaledb-ha:latest
    
  grafana:
    deploy:
      replicas: 3
      
  api:
    deploy:
      replicas: 3
      
  nginx:
    image: nginx:alpine
    # Load balancer config
```

**Deliverables:**
- ✓ PostgreSQL streaming replication
- ✓ Grafana clustering (shared database)
- ✓ API horizontal scaling
- ✓ NGINX load balancer
- ✓ Health checks and auto-recovery

#### 5.3 Data Lifecycle Management
```python
# Automated archival
def archive_old_data():
    """Move 90+ day data to cold storage"""
    conn.execute("""
        INSERT INTO azure_costs_archive 
        SELECT * FROM azure_costs 
        WHERE date < CURRENT_DATE - INTERVAL '90 days'
    """)
    conn.execute("""
        DELETE FROM azure_costs 
        WHERE date < CURRENT_DATE - INTERVAL '90 days'
    """)

# Scheduled job (Airflow/Celery)
@daily_task
def run_data_lifecycle():
    archive_old_data()
    vacuum_database()
    update_statistics()
```

#### 5.4 Governance & Compliance
```python
# Audit logging
CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100),
    action VARCHAR(100),
    resource_type VARCHAR(100),
    resource_id VARCHAR(500),
    timestamp TIMESTAMP DEFAULT NOW(),
    ip_address VARCHAR(50),
    user_agent TEXT,
    details JSONB
);

# Cost policy enforcement
def enforce_budget_policy(subscription_id, monthly_cost):
    policy = get_budget_policy(subscription_id)
    if monthly_cost > policy.hard_limit:
        trigger_resource_lockdown(subscription_id)
        notify_finance_team(subscription_id, monthly_cost)
```

---

### Phase 6: DevOps & Automation (Week 13-14) 🔧

#### 6.1 CI/CD Pipeline
```yaml
# .github/workflows/main.yml
name: CI/CD Pipeline

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Run unit tests
        run: pytest tests/ --cov=src --cov-report=xml
      
      - name: Run integration tests
        run: pytest tests/integration/
      
      - name: Security scan
        run: |
          bandit -r src/
          safety check
  
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Build Docker images
        run: docker-compose build
      
      - name: Push to registry
        run: docker-compose push
  
  deploy:
    runs-on: ubuntu-latest
    needs: [test, build]
    steps:
      - name: Deploy to staging
        run: kubectl apply -f k8s/staging/
      
      - name: Run smoke tests
        run: pytest tests/smoke/
      
      - name: Deploy to production
        run: kubectl apply -f k8s/production/
```

#### 6.2 Infrastructure as Code
```terraform
# terraform/main.tf
module "cost_monitoring" {
  source = "./modules/cost-monitoring"
  
  environment = "production"
  region      = "eastus2"
  
  aks_cluster = {
    node_count = 3
    vm_size    = "Standard_D4s_v3"
  }
  
  postgres = {
    sku_name = "GP_Gen5_4"
    storage_mb = 102400
  }
  
  grafana = {
    replicas = 3
  }
}
```

#### 6.3 Monitoring & Observability
```python
# OpenTelemetry instrumentation
from opentelemetry import trace, metrics
from opentelemetry.exporter.otlp.proto.grpc import OTLPSpanExporter

tracer = trace.get_tracer(__name__)

@tracer.start_as_current_span("collect_azure_costs")
def collect_costs(subscription_id: str):
    span = trace.get_current_span()
    span.set_attribute("subscription.id", subscription_id)
    
    try:
        costs = fetch_costs_from_azure(subscription_id)
        span.set_attribute("costs.count", len(costs))
        return costs
    except Exception as e:
        span.record_exception(e)
        raise
```

**Deliverables:**
- ✓ OpenTelemetry tracing
- ✓ Prometheus metrics (RED/USE)
- ✓ ELK Stack for logs
- ✓ SLO monitoring (99.9% uptime)
- ✓ On-call runbooks

#### 6.4 Testing Strategy
```python
# tests/unit/test_cost_collector.py
def test_azure_cost_collection():
    collector = AzureCostCollector(subscription_id="test")
    costs = collector.collect_daily_costs()
    assert len(costs) > 0
    assert all(c.cost >= 0 for c in costs)

# tests/integration/test_api.py
def test_cost_api_endpoint():
    response = client.get("/api/costs?start_date=2025-11-01")
    assert response.status_code == 200
    assert "costs" in response.json()

# tests/e2e/test_dashboard.py
def test_grafana_dashboard_loads():
    driver.get("http://localhost:3000/d/azure-cost-analysis")
    assert "Azure Cost Analysis" in driver.title
```

**Test Coverage Goals:**
- Unit tests: 80%+
- Integration tests: Key workflows
- E2E tests: Critical user journeys
- Performance tests: Load testing (JMeter/Locust)

---

## 📈 Metrics & KPIs

### System Health Metrics
```
Availability SLO: 99.9% (43.8 minutes downtime/month)
API Latency: p95 < 500ms, p99 < 1s
Data Freshness: < 1 hour lag
Dashboard Load Time: < 3 seconds
```

### Business Metrics
```
Cost Visibility: 100% of Azure subscriptions
Savings Identified: $X per month
Savings Realized: Y% implementation rate
Alert Response Time: < 15 minutes
Budget Accuracy: ±5% forecast error
```

### Operational Metrics
```
Data Pipeline Success Rate: 99.5%
API Error Rate: < 0.1%
Alert False Positive Rate: < 5%
Dashboard Active Users: Track weekly
Mean Time to Recovery (MTTR): < 30 minutes
```

---

## 🚀 Quick Wins (Can Be Done Today)

### 1. Fix Prometheus Exporter (15 mins)
```bash
# Add to requirements.txt
prometheus-client==0.19.0

# Rebuild and restart
docker-compose build exporter
docker-compose up -d exporter
```

### 2. Add Region to Schema (30 mins)
```sql
ALTER TABLE azure_costs ADD COLUMN region VARCHAR(50);

-- Backfill from resource_id
UPDATE azure_costs 
SET region = SUBSTRING(resource_id FROM '/locations/([^/]+)');

CREATE INDEX idx_costs_region ON azure_costs(region);
```

### 3. Enable Grafana Authentication (10 mins)
```env
# .env
GF_SECURITY_ADMIN_PASSWORD=<strong-password>
GF_AUTH_ANONYMOUS_ENABLED=false
GF_AUTH_BASIC_ENABLED=true
```

### 4. Add Health Check Endpoints (20 mins)
```python
# src/api/health.py
@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "database": check_db_connection(),
        "azure_api": check_azure_api(),
        "timestamp": datetime.utcnow()
    }
```

### 5. Document Current System (1 hour)
```markdown
# Create OPERATIONS.md
- How to deploy
- How to backup/restore
- How to scale
- Troubleshooting guide
- Contact information
```

---

## 💼 Cost Estimate

### Phase 1-2 (Stabilization + Data Enrichment): 4 weeks
```
Senior Engineer: 160 hours × $150/hr = $24,000
DevOps Engineer: 80 hours × $120/hr = $9,600
QA Engineer: 40 hours × $100/hr = $4,000
Total: $37,600
```

### Phase 3-4 (Alerting + Optimization): 4 weeks
```
Senior Engineer: 160 hours × $150/hr = $24,000
ML Engineer: 80 hours × $140/hr = $11,200
Total: $35,200
```

### Phase 5-6 (Enterprise + DevOps): 4 weeks
```
Senior Engineer: 160 hours × $150/hr = $24,000
DevOps Engineer: 160 hours × $120/hr = $19,200
Security Engineer: 40 hours × $160/hr = $6,400
Total: $49,600
```

**Grand Total: $122,400** (12 weeks)

### Infrastructure Costs (Annual)
```
Azure Kubernetes Service: $1,200/month
PostgreSQL Managed Instance: $800/month
Application Insights: $200/month
Azure Key Vault: $50/month
Storage (logs, backups): $150/month
Total: $2,400/month × 12 = $28,800/year
```

---

## 🎓 Recommendations Priority Matrix

### Critical (Do First) 🔴
1. Fix Prometheus exporter (broken monitoring)
2. Implement authentication/authorization
3. Add multi-subscription support
4. Set up automated backups

### High (Do Soon) 🟠
1. Build alerting system
2. Add region/tag data collection
3. Implement CI/CD pipeline
4. Add comprehensive testing

### Medium (Nice to Have) 🟡
1. ML-based forecasting
2. Azure Advisor integration
3. High availability setup
4. Advanced analytics dashboards

### Low (Future) 🟢
1. Multi-tenancy support
2. Mobile app
3. Custom reporting engine
4. Third-party integrations (ServiceNow, JIRA)

---

## 🏁 Success Criteria

### Week 4 Milestone
- [ ] All 5 containers healthy
- [ ] 10+ subscriptions being monitored
- [ ] Authentication enabled
- [ ] Daily automated backups
- [ ] 5 operational dashboards

### Week 8 Milestone
- [ ] Alerting system live (email + Slack)
- [ ] Region/tag-based reporting
- [ ] 500+ subscriptions monitored
- [ ] ML forecasting operational
- [ ] 50+ cost optimization recommendations

### Week 12 Milestone (Production Ready)
- [ ] 99.9% uptime SLO met
- [ ] HA setup deployed
- [ ] Full CI/CD pipeline
- [ ] 80%+ test coverage
- [ ] Security audit passed
- [ ] Documentation complete
- [ ] On-call runbooks ready

---

## 📚 References

### Internal Documentation
- `README.md` - System overview
- `ARCHITECTURE.md` - Technical architecture
- `AZURE_INTEGRATION_GUIDE.md` - Azure API setup
- `GRAFANA_DASHBOARD_GUIDE.md` - Dashboard creation

### External Resources
- [Azure Cost Management REST API](https://learn.microsoft.com/en-us/rest/api/cost-management/)
- [TimescaleDB Best Practices](https://docs.timescale.com/timescaledb/latest/how-to-guides/)
- [Grafana Provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/)
- [FastAPI Best Practices](https://fastapi.tiangolo.com/deployment/)
- [Prometheus Exporters](https://prometheus.io/docs/instrumenting/writing_exporters/)

---

## 🤝 Next Steps

### Immediate Actions (This Week)
1. **Schedule review meeting** with stakeholders
2. **Prioritize phases** based on business needs
3. **Assign team members** to critical tasks
4. **Set up project tracking** (JIRA/Azure DevOps)
5. **Fix Prometheus exporter** (15 min quick win)

### Questions to Answer
1. **What's the target go-live date?**
2. **How many subscriptions need monitoring?** (Current: 1, Target: ?)
3. **What's the budget for Phase 1-2?** (Recommended: $37,600)
4. **Who will be on-call?** (Need rotation schedule)
5. **What's the disaster recovery RTO/RPO?** (Recommend: 1 hour / 15 min)

---

**Document Owner:** Kumar Nikhi  
**Last Updated:** November 7, 2025  
**Next Review:** December 7, 2025
