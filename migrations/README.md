# Alembic Database Migration Configuration

This directory will contain database migrations created with Alembic.

## Setup

Initialize Alembic (run once):
```bash
alembic init migrations
```

## Creating Migrations

Auto-generate migration from model changes:
```bash
alembic revision --autogenerate -m "Description of changes"
```

Create empty migration:
```bash
alembic revision -m "Description of changes"
```

## Applying Migrations

Upgrade to latest:
```bash
alembic upgrade head
```

Upgrade by one revision:
```bash
alembic upgrade +1
```

Downgrade by one revision:
```bash
alembic downgrade -1
```

## Migration History

View current revision:
```bash
alembic current
```

View migration history:
```bash
alembic history
```

## Important Notes

- Always review auto-generated migrations before applying
- Test migrations in development first
- Create TimescaleDB hypertables in migrations
- Include proper indexes for performance
- Handle data migrations carefully
