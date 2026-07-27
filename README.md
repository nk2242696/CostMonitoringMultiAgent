# Azure Cost Management System

A comprehensive, production-ready Azure Cost Management System with three distinct layers: **Monitoring**, **Alerting**, and **Recommendations**. This system provides real-time cost visibility, intelligent alerting on anomalies and budget thresholds, and actionable cost optimization recommendations.

## 🤖 **NEW: Three-Agent Architecture Review System**

**Get brutally honest Azure architecture feedback before you build!**

This project now includes a powerful **AutoGen-based multi-agent system** that proposes, critiques, and approves Azure architectures with sharp focus on:
- ✅ **Cost awareness** (surfaces hidden costs like VPN Gateway, Log Analytics ingestion)
- ✅ **Execution reality** (realistic time estimates, skill gap analysis)
- ✅ **Anti-over-engineering** (challenges unnecessary complexity)

**Quick start:**
```bash
pip install pyautogen openai
python run_architecture_review.py --template cost_monitoring
```

**📚 Documentation:**
- [Quick Start Guide](QUICK_START_AGENTS.md) - 5-minute setup
- [Full Documentation](AGENT_SYSTEM_README.md) - Complete system guide
- [Decision Guide](DECISION_GUIDE.md) - When to use which mode
- [Workflow Diagrams](AGENT_WORKFLOW_DIAGRAM.md) - Visual architecture

---

## 🎯 Key Features

### Layer 1: Monitoring
- Real-time cost data collection from Azure Cost Management API
- Multi-subscription support
- Time-series storage with TimescaleDB optimization
- Historical trend analysis and forecasting
- Anomaly detection using statistical methods
- RESTful API for cost data access

### Layer 2: Alerting
- Threshold-based alerts (budget, daily spend, etc.)
- ML-powered anomaly detection
- Predictive alerts based on spending patterns
- Multi-channel notifications (Email, Slack, Teams, SMS, Webhooks)
- Alert lifecycle management (acknowledgment, escalation, deduplication)
- Complex rule engine with customizable conditions

### Layer 3: Recommendations
- Azure Advisor integration
- Compute optimization (right-sizing, idle VMs, Reserved Instances)
- Storage optimization (orphaned disks, tier recommendations)
- Database optimization (sizing, serverless recommendations)
- Network optimization (unused IPs, data transfer costs)
- ROI calculation and savings tracking

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Application                      │
├─────────────────────────────────────────────────────────────┤
│  Monitoring Layer  │  Alerting Layer  │ Recommendation Layer │
├────────────────────┼──────────────────┼─────────────────────┤
│   Data Collection  │   Rules Engine   │     Analyzers       │
│   Metrics Calc     │   Detectors      │   Savings Calc      │
│   Anomaly Detect   │   Notifications  │   Azure Advisor     │
├────────────────────┴──────────────────┴─────────────────────┤
│              Redis Pub/Sub (Message Queue)                   │
├─────────────────────────────────────────────────────────────┤
│         PostgreSQL + TimescaleDB  │      Redis Cache        │
└─────────────────────────────────────────────────────────────┘
```

## 📋 Prerequisites

- Python 3.10 or higher
- PostgreSQL 14+ with TimescaleDB extension
- Redis 6+
- Azure Subscription with appropriate permissions
- Azure AD App Registration or Managed Identity

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/azure-cost-agent.git
cd azure-cost-agent
```

### 2. Install Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment

Copy the example configuration and update with your values:

```bash
cp config/dev.yaml.example config/dev.yaml
# Edit config/dev.yaml with your Azure credentials and database settings
```

### 4. Setup Database

```bash
# Run database migrations
alembic upgrade head
```

### 5. Run the Application

```bash
# Start the API server
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# Start the Celery worker (in another terminal)
celery -A src.common.messaging.celery_app worker --loglevel=info

# Start the Celery beat scheduler (in another terminal)
celery -A src.common.messaging.celery_app beat --loglevel=info
```

### 6. Access the API

- **API Documentation**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## 🐳 Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## 📊 API Endpoints

### Monitoring Layer

- `GET /api/v1/costs/summary` - Cost summary by period
- `GET /api/v1/costs/by-resource-group` - Costs by resource group
- `GET /api/v1/costs/by-service` - Costs by Azure service
- `GET /api/v1/costs/trends` - Cost trends over time
- `GET /api/v1/costs/anomalies` - Detected cost anomalies
- `GET /api/v1/costs/forecast` - Cost forecasts

### Alerting Layer

- `POST /api/v1/alerts/rules` - Create alert rule
- `GET /api/v1/alerts/rules` - List all alert rules
- `GET /api/v1/alerts/active` - Get active alerts
- `POST /api/v1/alerts/{id}/acknowledge` - Acknowledge alert
- `POST /api/v1/alerts/{id}/resolve` - Resolve alert
- `GET /api/v1/alerts/history` - Alert history

### Recommendation Layer

- `GET /api/v1/recommendations` - List all recommendations
- `GET /api/v1/recommendations/{id}` - Get recommendation details
- `POST /api/v1/recommendations/{id}/accept` - Accept recommendation
- `POST /api/v1/recommendations/{id}/implement` - Mark as implemented
- `GET /api/v1/recommendations/savings-report` - Savings achieved

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/monitoring/test_cost_collector.py
```

## 📦 Project Structure

```
azure-cost-agent/
├── src/
│   ├── monitoring/          # Layer 1: Cost Monitoring
│   ├── alerting/            # Layer 2: Alerting
│   ├── recommendations/     # Layer 3: Recommendations
│   ├── common/              # Shared utilities
│   └── api/                 # FastAPI application
├── tests/                   # Test suite
├── migrations/              # Database migrations
├── config/                  # Configuration files
├── docker/                  # Docker files
├── docs/                    # Documentation
└── scripts/                 # Utility scripts
```

## 🔧 Configuration

Configuration is managed through YAML files in the `config/` directory:

- `dev.yaml` - Development environment
- `staging.yaml` - Staging environment
- `prod.yaml` - Production environment

Key configuration sections:

- **Azure**: Credentials, subscription IDs, tenant ID
- **Database**: PostgreSQL connection settings
- **Redis**: Cache and message queue settings
- **Notifications**: Email, Slack, Teams, SMS settings
- **Monitoring**: Collection intervals, retention policies
- **Alerting**: Default thresholds, escalation policies
- **Recommendations**: Analysis schedules, savings targets

## 🔐 Security

- Azure Managed Identity for authentication (no stored credentials)
- Role-Based Access Control (RBAC)
- TLS 1.3 for all communications
- Encrypted secrets using Azure Key Vault
- Rate limiting (100 req/min per user)
- Audit logging for all actions
- Input validation and sanitization

## 📈 Performance Metrics

- Data collection latency: <5 minutes
- Alert trigger latency: <2 minutes
- API response time: <500ms (95th percentile)
- Database query time: <100ms (common queries)
- Supports 1000+ resources across 10+ subscriptions

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📞 Support

For support, email support@example.com or open an issue on GitHub.

## 🗺️ Roadmap

- [ ] Web-based dashboard UI
- [ ] Mobile app for alerts
- [ ] AI-powered cost analysis chatbot
- [ ] Multi-cloud support (AWS, GCP)
- [ ] Automated remediation workflows
- [ ] Cost allocation and chargeback
- [ ] Natural language query interface

## 🙏 Acknowledgments

- Azure SDK for Python
- FastAPI framework
- TimescaleDB for time-series optimization
- Prophet for forecasting
