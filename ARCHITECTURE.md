# Azure Cost Management System - Architecture

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              External Clients                                │
│                    (Web UI, CLI, Mobile App, Third-party)                    │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
                                     │ HTTPS/REST
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            FastAPI Application                               │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                           API Gateway Layer                            │  │
│  │  • Authentication & Authorization (Azure AD, API Keys)                │  │
│  │  • Rate Limiting (100 req/min per user)                               │  │
│  │  • Request Validation & Sanitization                                  │  │
│  │  • CORS, Security Headers                                             │  │
│  │  • Request ID Tracking                                                │  │
│  │  • Error Handling & Logging                                           │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                               │
│  ┌───────────────────┬──────────────────────┬─────────────────────────┐    │
│  │  Monitoring API   │   Alerting API       │  Recommendation API     │    │
│  │  /api/v1/costs/*  │  /api/v1/alerts/*    │  /api/v1/recommendations│    │
│  └─────────┬─────────┴──────────┬───────────┴───────────┬─────────────┘    │
└────────────┼────────────────────┼───────────────────────┼──────────────────┘
             │                    │                       │
             ▼                    ▼                       ▼
┌──────────────────────┐ ┌──────────────────────┐ ┌──────────────────────┐
│  MONITORING LAYER    │ │   ALERTING LAYER     │ │ RECOMMENDATION LAYER │
├──────────────────────┤ ├──────────────────────┤ ├──────────────────────┤
│                      │ │                      │ │                      │
│ Data Collectors      │ │ Rules Engine         │ │ Azure Advisor        │
│ ├─ Cost Collector    │ │ ├─ Rule Parser       │ │ ├─ Advisor Client    │
│ ├─ Usage Collector   │ │ ├─ Rule Evaluator    │ │ └─ Resource Graph    │
│ └─ Budget Collector  │ │ └─ Templates         │ │                      │
│                      │ │                      │ │ Analyzers            │
│ Data Processors      │ │ Detectors            │ │ ├─ Compute Analyzer  │
│ ├─ Data Normalizer   │ │ ├─ Threshold Det.    │ │ ├─ Storage Analyzer  │
│ ├─ Metrics Calc.     │ │ ├─ Anomaly Det.(ML)  │ │ ├─ Database Analyzer │
│ └─ Anomaly Detector  │ │ └─ Forecast Det.     │ │ └─ Network Analyzer  │
│                      │ │                      │ │                      │
│ Storage Layer        │ │ Notification Svc     │ │ Recommendation Eng.  │
│ ├─ Repositories      │ │ ├─ Email Sender      │ │ ├─ Scoring System    │
│ ├─ Query Methods     │ │ ├─ Slack Sender      │ │ ├─ Savings Calc.     │
│ └─ Caching           │ │ ├─ Teams Sender      │ │ └─ ROI Calculator    │
│                      │ │ ├─ SMS Sender        │ │                      │
│ Job Scheduler        │ │ └─ Webhook Sender    │ │ Remediation          │
│ ├─ Hourly Collection │ │                      │ │ ├─ Auto Remediation  │
│ ├─ Daily Aggregation │ │ Alert Manager        │ │ └─ Tracking          │
│ └─ Anomaly Detection │ │ ├─ Lifecycle Mgmt    │ │                      │
│                      │ │ ├─ Deduplication     │ │ Report Generator     │
└──────────┬───────────┘ │ ├─ Escalation        │ └───────────┬──────────┘
           │             │ └─ Grouping          │             │
           │             └──────────┬───────────┘             │
           │                        │                         │
           └────────────────────────┼─────────────────────────┘
                                    │
                            Message Queue Topics
                            ┌──────────────────┐
                            │ Redis Pub/Sub    │
                            ├──────────────────┤
                            │ • cost.data      │
                            │ • alert.triggered│
                            │ • alert.resolved │
                            │ • recommendation │
                            │ • anomaly        │
                            └────────┬─────────┘
                                     │
        ┌────────────────────────────┼────────────────────────────┐
        │                            │                            │
        ▼                            ▼                            ▼
┌────────────────┐          ┌────────────────┐          ┌────────────────┐
│  Celery Worker │          │  Celery Worker │          │  Celery Worker │
│   (Monitoring) │          │   (Alerting)   │          │ (Recommend.)   │
└───────┬────────┘          └───────┬────────┘          └────────┬───────┘
        │                           │                            │
        └───────────────────────────┼────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │     Celery Beat Scheduler     │
                    │  (Cron-based Task Scheduling) │
                    └───────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│   PostgreSQL     │      │      Redis       │      │  Azure Services  │
│   TimescaleDB    │      │  Cache & Queue   │      │                  │
├──────────────────┤      ├──────────────────┤      ├──────────────────┤
│ • cost_records   │      │ • Session Cache  │      │ • Cost Mgmt API  │
│ • cost_agg.      │      │ • Query Cache    │      │ • Advisor API    │
│ • cost_budgets   │      │ • Pub/Sub Topics │      │ • Resource Graph │
│ • anomalies      │      │ • Celery Broker  │      │ • Monitor API    │
│ • forecasts      │      │ • Rate Limiting  │      │ • Key Vault      │
│ • resource_meta  │      └──────────────────┘      │ • App Insights   │
│ • alert_rules    │                                │ • Managed ID     │
│ • recommendations│                                └──────────────────┘
└──────────────────┘
```

## Data Flow

### 1. Cost Monitoring Flow
```
Azure Cost API → Cost Collector → Data Normalizer → Database
                                                          │
                                                          ├→ Metrics Calculator → Aggregations
                                                          ├→ Anomaly Detector → Anomalies
                                                          └→ Pub/Sub → Alerting Layer
```

### 2. Alert Processing Flow
```
Monitoring Layer → Pub/Sub → Alert Detectors → Rule Engine → Notification Services
                                      │                              │
                                      ├→ Email (SMTP)               │
                                      ├→ Slack (Webhook)            │
                                      ├→ Teams (Webhook)            │
                                      ├→ SMS (Twilio)               │
                                      └→ Custom Webhooks            │
                                                                     ▼
                                                          Alert Manager (DB)
```

### 3. Recommendation Generation Flow
```
Azure Advisor API ┐
Resource Graph    ├→ Analyzers → Recommendation Engine → Savings Calculator
Monitor API      ┘                        │                       │
                                          ├→ Scoring System       │
                                          └→ Database             │
                                                                  ▼
                                                          Recommendations
```

## Component Interaction Matrix

| Component | Monitoring | Alerting | Recommendations | Database | Redis | Azure |
|-----------|-----------|----------|-----------------|----------|-------|-------|
| **Monitoring** | - | Publishes events | - | Read/Write | Cache/Pub | Cost API |
| **Alerting** | Subscribes | - | - | Read/Write | Cache/Pub | - |
| **Recommendations** | Reads data | - | - | Read/Write | Cache | Advisor, Graph, Monitor |
| **Database** | Stores costs | Stores alerts | Stores recommendations | - | - | - |
| **Redis** | Caches queries | Pub/Sub | Caches analysis | - | - | - |
| **Azure** | Source data | - | Source recommendations | - | - | - |

## Security Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Security Layers                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Authentication Layer                                     │
│     ├─ Azure AD (OAuth 2.0/OIDC)                           │
│     ├─ API Keys                                             │
│     ├─ Managed Identity (for Azure resources)              │
│     └─ Service Principal (for external clients)            │
│                                                              │
│  2. Authorization Layer (RBAC)                              │
│     ├─ Admin Role (full access)                            │
│     ├─ Analyst Role (read + recommendations)               │
│     ├─ Viewer Role (read-only)                             │
│     └─ System Role (internal services)                     │
│                                                              │
│  3. Network Security                                         │
│     ├─ TLS 1.3 (all communications)                        │
│     ├─ Private Endpoints (Azure services)                  │
│     ├─ Network Security Groups                             │
│     └─ DDoS Protection                                      │
│                                                              │
│  4. Data Security                                            │
│     ├─ Encryption at Rest (AES-256)                        │
│     ├─ Encryption in Transit (TLS)                         │
│     ├─ Azure Key Vault (secrets)                           │
│     └─ Data Masking (sensitive fields)                     │
│                                                              │
│  5. Application Security                                     │
│     ├─ Input Validation (Pydantic)                         │
│     ├─ SQL Injection Prevention (ORM)                      │
│     ├─ XSS Prevention                                       │
│     ├─ CSRF Protection                                      │
│     ├─ Rate Limiting                                        │
│     └─ Security Headers                                     │
│                                                              │
│  6. Monitoring & Auditing                                    │
│     ├─ Request Logging                                      │
│     ├─ Audit Trail (all actions)                           │
│     ├─ Anomaly Detection (access patterns)                 │
│     └─ Security Alerts                                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Deployment Architecture

### Development Environment
```
Developer Workstation
├─ Docker Compose
│  ├─ PostgreSQL + TimescaleDB
│  ├─ Redis
│  ├─ API (FastAPI)
│  ├─ Celery Worker
│  └─ Celery Beat
└─ Local Configuration (dev.yaml)
```

### Production Environment (Azure)
```
Azure Subscription
├─ Azure Container Apps
│  ├─ API Service (auto-scaling)
│  ├─ Worker Service (auto-scaling)
│  └─ Scheduler Service
├─ Azure Database for PostgreSQL (Flexible Server)
│  └─ TimescaleDB Extension
├─ Azure Cache for Redis (Premium)
├─ Azure Key Vault (secrets)
├─ Azure Application Insights (monitoring)
├─ Azure Log Analytics (logs)
├─ Azure Container Registry (images)
└─ Virtual Network (private connectivity)
```

## Scalability Strategy

### Horizontal Scaling
- **API Layer**: Auto-scale based on CPU/memory (2-10 instances)
- **Worker Layer**: Auto-scale based on queue depth (2-20 instances)
- **Database**: Read replicas for query distribution

### Vertical Scaling
- **Database**: Scale up CPU/memory as data grows
- **Redis**: Increase memory for larger cache

### Data Partitioning
- **TimescaleDB Hypertables**: Automatic time-based partitioning
- **Sharding**: By subscription ID for multi-tenant scenarios

## High Availability

### Component Redundancy
- **API**: Multiple instances behind load balancer
- **Workers**: Multiple instances processing queue
- **Database**: Primary with sync replicas
- **Redis**: Cluster mode with replication

### Disaster Recovery
- **Database Backups**: Automated daily backups, 30-day retention
- **Point-in-Time Restore**: 7-day window
- **Geo-Replication**: Optional for critical deployments

## Performance Optimization

### Database Level
- Composite indexes for common queries
- Materialized views for aggregations
- Query result caching (Redis)
- Connection pooling

### Application Level
- Async I/O (FastAPI + asyncio)
- Batch processing for bulk operations
- Circuit breakers for external APIs
- Retry with exponential backoff

### Caching Strategy
```
L1: Application memory (short-lived, <1 min)
L2: Redis cache (5-60 min TTL)
L3: Database query cache (TimescaleDB)
```

## Monitoring & Observability

### Application Metrics
- Request rate, latency, error rate
- API endpoint performance
- Celery task execution time
- Database query performance

### Business Metrics
- Cost data collection success rate
- Alert delivery success rate
- Recommendation acceptance rate
- Savings achieved

### System Health
- CPU, memory, disk usage
- Database connections
- Redis memory usage
- Task queue length

### Alerting
- System alerts (infrastructure issues)
- Application alerts (errors, performance)
- Business alerts (data quality, SLA violations)

---

**This architecture is designed for:**
- ✅ High scalability (1000+ resources, 10+ subscriptions)
- ✅ High availability (99.9% uptime)
- ✅ Security first (defense in depth)
- ✅ Performance optimized (<500ms API response)
- ✅ Cost efficient (right-sized resources)
- ✅ Maintainable (modular, documented)
