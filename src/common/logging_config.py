"""
Logging configuration module.

Provides structured logging with JSON format and request tracking.
"""

import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from contextvars import ContextVar

import structlog
from pythonjsonlogger import jsonlogger

from src.common.config import get_config

# Context variable for request ID tracking
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


def setup_logging() -> None:
    """Setup structured logging configuration."""
    config = get_config()
    log_config = config.logging

    # Create logs directory if it doesn't exist
    if log_config.output in ("file", "both"):
        log_file = Path(log_config.file_path)
        log_file.parent.mkdir(parents=True, exist_ok=True)

    # Configure log level
    log_level = getattr(logging, log_config.level.upper(), logging.INFO)

    # Setup handlers
    handlers = []

    if log_config.output in ("console", "both"):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        handlers.append(console_handler)

    if log_config.output in ("file", "both"):
        file_handler = logging.FileHandler(log_config.file_path)
        file_handler.setLevel(log_level)
        handlers.append(file_handler)

    # Configure formatter based on format type
    if log_config.format == "json":
        formatter = CustomJsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            rename_fields={
                "asctime": "timestamp",
                "levelname": "level",
                "name": "logger",
            }
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    for handler in handlers:
        handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()
    for handler in handlers:
        root_logger.addHandler(handler)

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            add_request_id,
            structlog.processors.JSONRenderer() if log_config.format == "json"
            else structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Silence noisy loggers
    logging.getLogger("azure").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with field renaming."""

    def __init__(self, *args: Any, rename_fields: Optional[Dict[str, str]] = None, **kwargs: Any):
        """
        Initialize custom JSON formatter.

        Args:
            rename_fields: Dictionary mapping original field names to new names
        """
        super().__init__(*args, **kwargs)
        self.rename_fields = rename_fields or {}

    def add_fields(
        self,
        log_record: Dict[str, Any],
        record: logging.LogRecord,
        message_dict: Dict[str, Any]
    ) -> None:
        """
        Add fields to log record with renaming.

        Args:
            log_record: Log record dictionary
            record: LogRecord instance
            message_dict: Message dictionary
        """
        super().add_fields(log_record, record, message_dict)

        # Rename fields
        for old_name, new_name in self.rename_fields.items():
            if old_name in log_record:
                log_record[new_name] = log_record.pop(old_name)

        # Add request ID if available
        request_id = request_id_var.get()
        if request_id:
            log_record["request_id"] = request_id

        # Add extra context
        if hasattr(record, "extra"):
            log_record.update(record.extra)


def add_request_id(
    logger: Any, method_name: str, event_dict: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Add request ID to log event.

    Args:
        logger: Logger instance
        method_name: Method name
        event_dict: Event dictionary

    Returns:
        Updated event dictionary
    """
    request_id = request_id_var.get()
    if request_id:
        event_dict["request_id"] = request_id
    return event_dict


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Get a structured logger.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Structured logger instance
    """
    return structlog.get_logger(name)


def set_request_id(request_id: str) -> None:
    """
    Set request ID for the current context.

    Args:
        request_id: Request ID
    """
    request_id_var.set(request_id)


def get_request_id() -> Optional[str]:
    """
    Get request ID from the current context.

    Returns:
        Request ID or None
    """
    return request_id_var.get()


def clear_request_id() -> None:
    """Clear request ID from the current context."""
    request_id_var.set(None)


# Initialize logging when module is imported
setup_logging()
