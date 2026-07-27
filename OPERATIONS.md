# Operations Guide - Azure Cost Monitoring

## Quick Start

### Prerequisites
- Docker Desktop installed and running
- Azure subscription with appropriate permissions
- Python 3.11+ (for local development)

### Environment Setup

1. **Clone the repository and configure environment**
```bash
cd CostMonitoring
```

2. **Set environment variables**
Edit `.env` file with secure passwords:
```bash
GRAFANA_ADMIN_PASSWORD=YourSecurePassword
POSTGRES_PASSWORD=YourSecureDbPassword
```

3. **Apply database migrations**
```bash
# Install Alembic if not already installed
pip install alembic

# Apply all migrations
alembic upgrade head
```

4. **Build and start services**
```bash
# Build Docker images
docker-compose build

# Start all services
docker-compose up -d

# Verify all containers are running
docker ps
```

### Service Access

| Service | URL | Credentials |
|---------|-----|-------------|
| Grafana | http://localhost:3000 | admin / (see .env) |
| Prometheus | http://localhost:9090 | N/A |
| API | http://localhost:8000 | N/A |
| API Docs | http://localhost:8000/docs | N/A |
| Exporter | http://localhost:8001/metrics | N/A |
| PostgreSQL | localhost:5432 | postgres / (see .env) |

## Daily Operations

### Collecting Cost Data

The system automatically collects Azure cost data. To trigger manual collection:

```bash
docker exec -it azure-cost-api python scripts/collect_azure_costs.py
```

### Viewing Dashboards

1. Navigate to Grafana at http://localhost:3000
2. Available dashboards:
   - **Azure Costs Dashboard** - Main cost overview (30-day view)
   - **AI Recommendations** - AI-powered optimization suggestions
   - **Azure Cost Analysis** - Top-down cost breakdown

### Health Checks

Check system health:
```bash
# API health check
curl http://localhost:8000/health

# Prometheus metrics
curl http://localhost:8001/metrics

# Container status
docker ps
docker stats --no-stream
```

## Troubleshooting

### Container Issues

**View logs:**
```bash
# All containers
docker-compose logs --tail=50

# Specific service
docker logs azure-cost-api --tail=50
docker logs azure-cost-exporter --tail=50
docker logs azure-cost-grafana --tail=50
docker logs azure-cost-db --tail=50
docker logs azure-cost-prometheus --tail=50
```

**Restart containers:**
```bash
# Restart all services
docker-compose restart

# Restart specific service
docker-compose restart api
docker-compose restart exporter
```

**Rebuild containers:**
```bash
# Rebuild and restart
docker-compose down
docker-compose build
docker-compose up -d
```

### Database Issues

**Connect to database:**
```bash
docker exec -it azure-cost-db psql -U postgres -d azure_cost_dev
```

**Check table schema:**
```sql
\d azure_costs
```

**Verify data:**
```sql
SELECT COUNT(*) FROM azure_costs;
SELECT * FROM azure_costs ORDER BY date DESC LIMIT 10;
```

**Check migration status:**
```sql
SELECT * FROM alembic_version;
```

### Prometheus Exporter Issues

**Common issue: ModuleNotFoundError**
```bash
# Rebuild with updated dependencies
docker-compose build exporter
docker-compose up -d exporter

# Verify it's running
docker logs azure-cost-exporter --tail=20
curl http://localhost:8001/metrics
```

### Grafana Issues

**Dashboard not loading:**
1. Clear browser cache (Ctrl+F5)
2. Check Grafana logs: `docker logs azure-cost-grafana --tail=50`
3. Verify datasource connection in Grafana UI (Settings > Data Sources)

**Pie charts showing "no data":**
1. Test queries in PostgreSQL directly
2. Check Grafana query editor for syntax errors
3. Verify time range filter matches data date range
4. Check panel configuration (reduceOptions, field overrides)

**Reset admin password:**
```bash
docker exec -it azure-cost-grafana grafana-cli admin reset-admin-password NewPassword123
```

## Backup and Restore

### Database Backup

**Create backup:**
```bash
# Backup to file
docker exec azure-cost-db pg_dump -U postgres azure_cost_dev > backup_$(date +%Y%m%d).sql

# Compressed backup
docker exec azure-cost-db pg_dump -U postgres azure_cost_dev | gzip > backup_$(date +%Y%m%d).sql.gz
```

**Restore from backup:**
```bash
# From SQL file
cat backup_20251106.sql | docker exec -i azure-cost-db psql -U postgres -d azure_cost_dev

# From compressed file
gunzip -c backup_20251106.sql.gz | docker exec -i azure-cost-db psql -U postgres -d azure_cost_dev
```

### Configuration Backup

Important files to backup:
- `.env` - Environment variables
- `docker-compose.yml` - Container configuration
- `config/grafana/dashboards/*.json` - Grafana dashboards
- `migrations/versions/*.py` - Database migrations

## Monitoring

### Key Metrics to Watch

1. **Data Collection**
   - Last collection timestamp
   - Number of records collected
   - Collection errors

2. **Database**
   - Connection count
   - Query performance
   - Disk usage

3. **API**
   - Response times
   - Error rates
   - Request volume

4. **Container Health**
   - CPU usage
   - Memory usage
   - Restart count

### Alerts Setup

Configure alerts for:
- Daily spend > threshold
- No data collection in 24 hours
- Database connection failures
- Container restarts

## Maintenance

### Regular Tasks

**Daily:**
- Check container health: `docker ps`
- Verify data collection: Check Grafana dashboards

**Weekly:**
- Review logs for errors
- Check disk space: `docker system df`
- Backup database

**Monthly:**
- Update Docker images: `docker-compose pull`
- Review and update dependencies
- Audit security settings

### Database Maintenance

**Vacuum and analyze:**
```bash
docker exec -it azure-cost-db psql -U postgres -d azure_cost_dev -c "VACUUM ANALYZE azure_costs;"
```

**Check table sizes:**
```bash
docker exec -it azure-cost-db psql -U postgres -d azure_cost_dev -c "
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
"
```

## Security

### Best Practices

1. **Change default passwords** in `.env` file
2. **Never commit `.env`** to version control
3. **Use strong passwords** (minimum 16 characters)
4. **Enable SSL** for PostgreSQL in production
5. **Restrict network access** using firewall rules
6. **Regular security updates** for Docker images

### Updating Passwords

1. Stop containers: `docker-compose down`
2. Update `.env` file with new passwords
3. Start containers: `docker-compose up -d`
4. Update connection strings if needed

## Performance Tuning

### Database Optimization

```sql
-- Add indexes for common queries
CREATE INDEX IF NOT EXISTS idx_costs_service ON azure_costs(service_name);
CREATE INDEX IF NOT EXISTS idx_costs_date_service ON azure_costs(date, service_name);
CREATE INDEX IF NOT EXISTS idx_costs_subscription_date ON azure_costs(subscription_id, date);
```

### Docker Resource Limits

Edit `docker-compose.yml` to add resource limits:
```yaml
services:
  postgres:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

## Migration Guide

### Applying New Migrations

```bash
# Check current version
alembic current

# Show pending migrations
alembic history

# Apply all pending migrations
alembic upgrade head

# Rollback last migration (if needed)
alembic downgrade -1
```

### Creating New Migrations

```bash
# Auto-generate migration from model changes
alembic revision --autogenerate -m "description of changes"

# Create empty migration
alembic revision -m "description of changes"
```

## Support

### Getting Help

1. Check logs first: `docker-compose logs`
2. Review this operations guide
3. Check TECHNICAL_REVIEW_AND_ROADMAP.md for known issues
4. Search GitHub issues (if applicable)

### Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| ModuleNotFoundError: prometheus_client | Missing dependency | Rebuild exporter container |
| Connection refused (PostgreSQL) | Database not ready | Wait 30s, check health |
| Dashboard "no data" | Query/config issue | Check time range, test query |
| Container restarting | Application crash | Check logs for error details |

## Development

### Local Development Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Run API locally (without Docker)
python scripts/run_dev_server.py
```

### Testing

```bash
# Run test collection
python scripts/collect_azure_costs.py

# Test database connection
python scripts/test_db_connection.py

# Test AI recommendations
python scripts/test_ai_recommendations.py
```

## Disaster Recovery

### Complete System Restore

1. **Restore files from backup**
2. **Apply environment configuration**
```bash
cp backup/.env .env
```
3. **Rebuild containers**
```bash
docker-compose build
```
4. **Restore database**
```bash
cat backup.sql | docker exec -i azure-cost-db psql -U postgres -d azure_cost_dev
```
5. **Start services**
```bash
docker-compose up -d
```
6. **Verify health**
```bash
curl http://localhost:8000/health
```

---

**Last Updated:** November 2025  
**Version:** 1.0.0
