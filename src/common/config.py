"""
Configuration management module.

Loads configuration from YAML files based on environment.
Supports environment variable substitution and Azure Key Vault integration.
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings


class AzureConfig(BaseSettings):
    """Azure configuration."""
    tenant_id: str
    subscription_ids: List[str]
    use_managed_identity: bool = True
    client_id: Optional[str] = None
    client_secret: Optional[str] = None


class DatabaseConfig(BaseSettings):
    """Database configuration."""
    host: str
    port: int = 5432
    database: str = "cost_agent.db"
    username: str = ""
    password: str = ""
    pool_size: int = 10
    max_overflow: int = 20
    echo_sql: bool = False
    ssl_mode: Optional[str] = None
    use_sqlite: bool = False

    @property
    def url(self) -> str:
        """Get database URL."""
        if self.use_sqlite or not self.host:
            return f"sqlite:///{self.database}"
        ssl = f"?sslmode={self.ssl_mode}" if self.ssl_mode else ""
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}{ssl}"


class RedisConfig(BaseSettings):
    """Redis configuration."""
    host: str
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    decode_responses: bool = True
    max_connections: int = 50
    ssl: bool = False

    @property
    def url(self) -> str:
        """Get Redis URL."""
        password_part = f":{self.password}@" if self.password else ""
        protocol = "rediss" if self.ssl else "redis"
        return f"{protocol}://{password_part}{self.host}:{self.port}/{self.db}"


class CeleryConfig(BaseSettings):
    """Celery configuration."""
    broker_url: str
    result_backend: str
    task_serializer: str = "json"
    result_serializer: str = "json"
    accept_content: List[str] = Field(default_factory=lambda: ["json"])
    timezone: str = "UTC"
    enable_utc: bool = True
    worker_prefetch_multiplier: int = 4
    worker_max_tasks_per_child: int = 1000


class APIConfig(BaseSettings):
    """API configuration."""
    title: str = "Azure Cost Management System"
    version: str = "0.1.0"
    description: str = "Comprehensive cost monitoring, alerting, and recommendations"
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    cors_origins: List[str] = Field(default_factory=list)
    rate_limit: Dict[str, Any] = Field(default_factory=dict)


class MonitoringConfig(BaseSettings):
    """Monitoring configuration."""
    collection_intervals: Dict[str, str] = Field(default_factory=dict)
    retention: Dict[str, int] = Field(default_factory=dict)
    anomaly_detection: Dict[str, Any] = Field(default_factory=dict)


class AlertingConfig(BaseSettings):
    """Alerting configuration."""
    enabled: bool = True
    default_thresholds: Dict[str, float] = Field(default_factory=dict)
    deduplication_window_minutes: int = 60
    escalation_timeout_minutes: int = 30
    notification_channels: Dict[str, Any] = Field(default_factory=dict)


class RecommendationsConfig(BaseSettings):
    """Recommendations configuration."""
    enabled: bool = True
    analysis_schedule: str = "0 0 * * 0"
    lookback_days: int = 30
    minimum_savings_threshold: float = 10.0
    confidence_threshold: float = 0.70
    analyzers: Dict[str, Any] = Field(default_factory=dict)


class LoggingConfig(BaseSettings):
    """Logging configuration."""
    level: str = "INFO"
    format: str = "json"
    output: str = "console"
    file_path: str = "logs/app.log"
    rotation: str = "1 day"
    retention: str = "30 days"
    include_request_id: bool = True


class SecurityConfig(BaseSettings):
    """Security configuration."""
    secret_key: str
    key_vault_url: Optional[str] = None
    use_key_vault: bool = False
    api_key_header: str = "X-API-Key"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60


class FeaturesConfig(BaseSettings):
    """Feature flags configuration."""
    enable_ml_anomaly_detection: bool = True
    enable_forecasting: bool = True
    enable_auto_remediation: bool = False
    enable_recommendation_tracking: bool = True
    enable_savings_reporting: bool = True


class Config:
    """Main configuration class."""

    def __init__(self, environment: Optional[str] = None):
        """
        Initialize configuration.

        Args:
            environment: Environment name (dev, staging, prod). Defaults to ENVIRONMENT env var.
        """
        self.environment = environment or os.getenv("ENVIRONMENT", "dev")
        self._config_data = self._load_config()

        # Initialize all config sections
        self.azure = AzureConfig(**self._config_data.get("azure", {}))
        self.database = DatabaseConfig(**self._config_data.get("database", {}))
        self.redis = RedisConfig(**self._config_data.get("redis", {}))
        self.celery = CeleryConfig(**self._config_data.get("celery", {}))
        self.api = APIConfig(**self._config_data.get("api", {}))
        self.monitoring = MonitoringConfig(**self._config_data.get("monitoring", {}))
        self.alerting = AlertingConfig(**self._config_data.get("alerting", {}))
        self.recommendations = RecommendationsConfig(**self._config_data.get("recommendations", {}))
        self.logging = LoggingConfig(**self._config_data.get("logging", {}))
        self.security = SecurityConfig(**self._config_data.get("security", {}))
        self.features = FeaturesConfig(**self._config_data.get("features", {}))

    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration from YAML file.

        Returns:
            Configuration dictionary
        """
        config_dir = Path(__file__).parent.parent.parent / "config"
        config_file = config_dir / f"{self.environment}.yaml"

        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_file}")

        with open(config_file, "r") as f:
            config_data = yaml.safe_load(f)

        # Substitute environment variables
        return self._substitute_env_vars(config_data)

    def _substitute_env_vars(self, config: Any) -> Any:
        """
        Recursively substitute environment variables in configuration.

        Args:
            config: Configuration data (dict, list, or string)

        Returns:
            Configuration with substituted values
        """
        if isinstance(config, dict):
            return {key: self._substitute_env_vars(value) for key, value in config.items()}
        elif isinstance(config, list):
            return [self._substitute_env_vars(item) for item in config]
        elif isinstance(config, str):
            # Match ${VAR_NAME} or ${VAR_NAME:default_value}
            pattern = r"\$\{([^}:]+)(?::([^}]*))?\}"
            
            def replace_env_var(match: re.Match) -> str:
                var_name = match.group(1)
                default_value = match.group(2) if match.group(2) is not None else ""
                return os.getenv(var_name, default_value)
            
            return re.sub(pattern, replace_env_var, config)
        else:
            return config

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by key.

        Args:
            key: Configuration key (supports dot notation, e.g., "azure.tenant_id")
            default: Default value if key not found

        Returns:
            Configuration value
        """
        keys = key.split(".")
        value = self._config_data

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default

        return value


# Global configuration instance
_config: Optional[Config] = None


def get_config() -> Config:
    """
    Get global configuration instance.

    Returns:
        Configuration instance
    """
    global _config
    if _config is None:
        _config = Config()
    return _config


def reload_config(environment: Optional[str] = None) -> Config:
    """
    Reload configuration.

    Args:
        environment: Environment name

    Returns:
        New configuration instance
    """
    global _config
    _config = Config(environment)
    return _config
