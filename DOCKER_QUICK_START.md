# 🚀 Quick Start Guide - Architecture Review in Docker

This guide shows you how to run the complete Azure Cost Monitoring system with the Architecture Review multi-agent system in Docker containers.

## 📋 Prerequisites

- Docker Desktop installed and running
- PowerShell (Windows) or Bash (Linux/Mac)
- Azure OpenAI credentials configured in `.env` file

## 🎯 Quick Start (2 Steps)

### Step 1: Deploy with Docker

```powershell
# Run the deployment script
.\deploy_docker.ps1
```

### Step 2: Access the Dashboard

Open your browser to: **http://localhost:3001**

Login with:
- **Username**: `admin`
- **Password**: `AzureCost2025!SecurePass`

## 🎨 Available Dashboards

After logging into Grafana, you'll see three dashboards:

1. **Azure Cost Trends** - Historical cost analysis
2. **AI Recommendations** - Cost optimization suggestions  
3. **Architecture Reviews** 🆕 - Multi-agent architecture analysis

## 🏗️ Architecture Review Dashboard

The Architecture Reviews dashboard includes:

### 1. Interactive Review UI (Top Panel)
- Embedded web interface to run architecture reviews
- Enter problem statements and get instant multi-agent analysis
- Three agents collaborate: Architect → Reviewer → Approver
- Download results as JSON or Markdown

### 2. Statistics Panels
- **Total Architecture Reviews** - Count of all reviews
- **Approved Architecture Savings** - Estimated cost savings
- **Reviews Over Time** - Trend chart
- **Recent Reviews Table** - Latest 20 reviews with status

## 🔧 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Compose Stack                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Nginx      │  │   Grafana    │  │  FastAPI     │      │
│  │   :3001      │←→│   :3000      │←→│   :8000      │      │
│  └──────────────┘  └──────────────┘  └──────┬───────┘      │
│                                               │               │
│  ┌──────────────┐  ┌──────────────┐         │               │
│  │ PostgreSQL   │←→│ Prometheus   │←────────┘               │
│  │   :5432      │  │   :9090      │                         │
│  └──────────────┘  └──────────────┘                         │
│                                                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │         Architecture Review Service                    │  │
│  │  Agent 1: Architect (Azure OpenAI o4-mini)           │  │
│  │  Agent 2: Reviewer (Effort/Cost/Time analysis)       │  │
│  │  Agent 3: Approver (Final decision maker)            │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## 🎮 How to Use Architecture Review

### Via Grafana Dashboard

1. Navigate to **Architecture Review Dashboard**
2. Scroll to the top panel with the embedded UI
3. Enter your problem statement in the text area
4. Click **"Run Architecture Review"**
5. Wait 2-3 minutes for the three agents to analyze
6. View results:
   - **Agent 1 Proposal**: Azure architecture recommendation
   - **Agent 2 Review**: Effort, complexity, time estimates
   - **Agent 3 Decision**: Approval/rejection with reasoning
7. Download results as JSON or Markdown

### Via API Directly

```bash
# Run a review
curl -X POST http://localhost:8000/architecture/review \
  -H "Content-Type: application/json" \
  -d '{
    "problem_statement": "We need to migrate our monolithic app to microservices..."
  }'

# List all reviews
curl http://localhost:8000/architecture/reviews

# Get specific review
curl http://localhost:8000/architecture/review/{review_id}
```

### Via Web UI

Open: **http://localhost:8000/static/architecture_review.html**

## 📊 Example Problem Statement

```
We need to enhance our Azure cost monitoring system.

CURRENT SETUP:
- Python backend (FastAPI) running in Docker
- PostgreSQL database storing cost data
- Grafana for visualization
- Collecting costs from 5-10 Azure subscriptions

NEW REQUIREMENTS:
- Scale to 50+ Azure subscriptions
- Add predictive cost forecasting (ML-based)
- Implement automated budget alerts
- Deploy to Azure (currently local Docker)
- Support 100+ concurrent users

CONSTRAINTS:
- Budget: $2000-3000/month
- Team: 2 engineers
- Timeline: 3 months
- Must maintain current functionality
```

## 🔍 Monitoring & Logs

### View Container Logs

```powershell
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f grafana
docker-compose logs -f postgres
```

### Check Service Health

```powershell
docker-compose ps
```

### Restart Services

```powershell
docker-compose restart api
```

## 🛑 Stop & Clean Up

### Stop Services

```powershell
docker-compose down
```

### Stop and Remove Data

```powershell
docker-compose down -v
```

## 🔧 Configuration

### Environment Variables (.env)

```env
# Azure OpenAI (Required for Architecture Review)
AZURE_OPENAI_KEY=your-key-here
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=o4-mini

# Database
POSTGRES_PASSWORD=AzureCost2025!DbPass

# Grafana
GRAFANA_ADMIN_PASSWORD=AzureCost2025!SecurePass
```

### Volumes

Data is persisted in Docker volumes:
- `postgres_data` - Database storage
- `grafana_data` - Dashboards and settings
- `prometheus_data` - Metrics storage
- `./architecture_review` - Review results (files)

## 🐛 Troubleshooting

### Architecture Review Not Working

1. **Check Azure OpenAI credentials**:
   ```powershell
   docker-compose logs api | Select-String "AZURE_OPENAI"
   ```

2. **Verify API is running**:
   ```powershell
   curl http://localhost:8000/health
   ```

3. **Check architecture review service**:
   ```powershell
   docker-compose logs api | Select-String "architecture"
   ```

### Grafana Dashboard Not Loading

1. **Check Grafana logs**:
   ```powershell
   docker-compose logs grafana
   ```

2. **Verify datasource connection**:
   - Open Grafana → Configuration → Data Sources
   - Test the PostgreSQL connection

3. **Reimport dashboard**:
   - Configuration → Dashboards → Import
   - Upload `config/grafana/dashboards/architecture-reviews.json`

### Cannot Access Services

1. **Check if containers are running**:
   ```powershell
   docker-compose ps
   ```

2. **Check port conflicts**:
   ```powershell
   netstat -ano | findstr ":8000"
   netstat -ano | findstr ":3001"
   ```

3. **Restart Docker Desktop**

## 📚 Additional Resources

- **API Documentation**: http://localhost:8000/docs
- **Prometheus Metrics**: http://localhost:9090
- **PostgreSQL**: `postgresql://postgres:AzureCost2025!DbPass@localhost:5432/azure_cost_dev`

## 🔐 Security Notes

- Change default passwords in `.env` before production deployment
- The `.env` file contains sensitive credentials - never commit to git
- Use Azure Key Vault for production secrets
- Enable HTTPS with proper certificates for production

## 📞 Support

For issues or questions:
1. Check the logs: `docker-compose logs -f`
2. Review this guide
3. Check the main README.md for detailed documentation

---

**Happy Architecture Reviewing! 🎉**
