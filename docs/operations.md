# Operations

## Lifecycle

- Start: `docker compose up --build -d`
- Status: `docker compose ps`
- Logs: `docker compose logs -f api worker`
- Stop: `docker compose down`
- Destructive local reset: `docker compose down -v`

## Migrations

The one-shot `migrate` service runs `alembic upgrade head`. API and worker startup depends on its successful completion. To inspect migration output, run `docker compose logs migrate`.

## Backups

Back up before upgrades:

`docker compose exec postgres pg_dump -U cost_monitor -d azure_cost -Fc -f /tmp/azure_cost.dump`

Copy the dump out of the container and store it securely. Test restoration regularly in a separate environment.

## Health

- `/health/live` checks the API process.
- `/health/ready` verifies database connectivity and migration state.
- `/health` reports safe component status.
- `/metrics` exposes Prometheus metrics.

## Troubleshooting

If API or worker does not start, inspect PostgreSQL and migration logs first. Validate `.env` values with `docker compose run --rm api cost-monitor config validate`. AI configuration errors affect AI-dependent workflows; use `LLM_PROVIDER=disabled` to run deterministic analysis without a model.
