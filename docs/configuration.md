# Configuration

Copy `.env.example` to `.env`. Docker Compose reads this file automatically.

Edit `config/workspace.yaml` to describe non-secret organization context,
environments, subscriptions, required tags, exclusions, budget, risk tolerance,
and remediation policy. Keep credentials in `.env`, never in workspace YAML.

## Required values

- `POSTGRES_PASSWORD`
- `SECRET_KEY`
- `GRAFANA_ADMIN_PASSWORD`

Use separate, randomly generated values. Never commit `.env`.

## Azure

Use a service principal locally by setting tenant, client ID, and client secret. The identity needs `Reader` and `Cost Management Reader` at each monitored scope. Managed identity is preferred in Azure-hosted environments.

`AZURE_SUBSCRIPTION_IDS` is comma-separated. Blank enables subscription discovery.

## Language models

`LLM_PROVIDER` supports `disabled`, `azure_openai`, and `openai_compatible`. Enabled providers require `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL`. Azure deployments may also set `LLM_API_VERSION`.

The application does not log API keys. If model calls fail, chat falls back to deterministic cost guidance.

## Optional Databricks configuration

Set `DATABRICKS_HOST` and `DATABRICKS_TOKEN` only when Spark job analysis needs to retrieve runs directly. Offline Spark plan analysis does not require these values.
