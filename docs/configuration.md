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

The application does not log API keys. Legacy chat falls back to deterministic cost guidance. An enabled agent workflow reports a safe failure explicitly rather than presenting fallback output as AI-generated.

## Multi-agent runtime

The LangGraph runtime is staged behind `AGENT_RUNTIME_ENABLED=false`. It uses the same `LLM_*` provider settings and supports optional `AGENT_CHAT_MODEL` and `AGENT_BACKGROUND_MODEL` deployment overrides.

Safety and cost limits are configured with:

- `AGENT_NODE_TIMEOUT_SECONDS` and `AGENT_WORKFLOW_TIMEOUT_SECONDS`
- `AGENT_MAX_REFINEMENT_ROUNDS`
- `AGENT_MAX_TOOL_CALLS` and `AGENT_MAX_MODEL_CALLS`
- `AGENT_CHECKPOINT_RETENTION_DAYS`
- `AGENT_BACKGROUND_SCHEDULE`

Enable the flag only after Alembic has upgraded the database and the configured model supports structured output and tool calling. No agent tool can mutate Azure or execute generated scripts.

## Optional Databricks configuration

Set `DATABRICKS_HOST` and `DATABRICKS_TOKEN` only when Spark job analysis needs to retrieve runs directly. Offline Spark plan analysis does not require these values.
