"""
Common utilities module.

Provides helper functions and decorators used across the application.
"""

import functools
import hashlib
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

from circuitbreaker import circuit
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.common.logging_config import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


def generate_request_id() -> str:
    """
    Generate unique request ID.

    Returns:
        UUID string
    """
    return str(uuid.uuid4())


def generate_hash(data: str) -> str:
    """
    Generate SHA-256 hash of data.

    Args:
        data: Data to hash

    Returns:
        Hexadecimal hash string
    """
    return hashlib.sha256(data.encode()).hexdigest()


def retry_with_backoff(
    max_attempts: int = 3,
    initial_wait: float = 1.0,
    max_wait: float = 10.0,
    exceptions: tuple = (Exception,),
) -> Callable:
    """
    Decorator for retrying with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        initial_wait: Initial wait time in seconds
        max_wait: Maximum wait time in seconds
        exceptions: Tuple of exception types to retry on

    Returns:
        Decorator function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        @retry(
            retry=retry_if_exception_type(exceptions),
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=initial_wait, max=max_wait),
            reraise=True,
        )
        def wrapper(*args: Any, **kwargs: Any) -> T:
            return func(*args, **kwargs)
        return wrapper
    return decorator


def circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    expected_exception: type = Exception,
) -> Callable:
    """
    Decorator for circuit breaker pattern.

    Args:
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Seconds to wait before attempting recovery
        expected_exception: Exception type to catch

    Returns:
        Decorator function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        @circuit(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exception=expected_exception,
        )
        def wrapper(*args: Any, **kwargs: Any) -> T:
            return func(*args, **kwargs)
        return wrapper
    return decorator


def timing_decorator(func: Callable[..., T]) -> Callable[..., T]:
    """
    Decorator to measure function execution time.

    Args:
        func: Function to measure

    Returns:
        Wrapped function
    """
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            elapsed = time.time() - start_time
            logger.info(
                f"Function {func.__name__} took {elapsed:.4f} seconds",
                function=func.__name__,
                elapsed_seconds=elapsed,
            )
    return wrapper


def parse_date_range(
    date_from: Optional[Union[str, datetime]] = None,
    date_to: Optional[Union[str, datetime]] = None,
    default_days: int = 30,
) -> tuple[datetime, datetime]:
    """
    Parse date range with defaults.

    Args:
        date_from: Start date (string or datetime)
        date_to: End date (string or datetime)
        default_days: Default number of days if dates not provided

    Returns:
        Tuple of (start_date, end_date)
    """
    if date_to is None:
        end_date = datetime.utcnow()
    elif isinstance(date_to, str):
        end_date = datetime.fromisoformat(date_to)
    else:
        end_date = date_to

    if date_from is None:
        start_date = end_date - timedelta(days=default_days)
    elif isinstance(date_from, str):
        start_date = datetime.fromisoformat(date_from)
    else:
        start_date = date_from

    return start_date, end_date


def chunk_list(items: List[T], chunk_size: int) -> List[List[T]]:
    """
    Split list into chunks.

    Args:
        items: List to chunk
        chunk_size: Size of each chunk

    Returns:
        List of chunks
    """
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


def flatten_dict(
    d: Dict[str, Any],
    parent_key: str = "",
    sep: str = ".",
) -> Dict[str, Any]:
    """
    Flatten nested dictionary.

    Args:
        d: Dictionary to flatten
        parent_key: Parent key for recursion
        sep: Separator for nested keys

    Returns:
        Flattened dictionary
    """
    items: List[tuple] = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    Safely divide two numbers.

    Args:
        numerator: Numerator
        denominator: Denominator
        default: Default value if division by zero

    Returns:
        Division result or default
    """
    if denominator == 0:
        return default
    return numerator / denominator


def percentage_change(old_value: float, new_value: float) -> float:
    """
    Calculate percentage change.

    Args:
        old_value: Old value
        new_value: New value

    Returns:
        Percentage change (-100 to +inf)
    """
    if old_value == 0:
        return 100.0 if new_value > 0 else 0.0
    return ((new_value - old_value) / abs(old_value)) * 100


def format_currency(amount: float, currency: str = "USD") -> str:
    """
    Format currency amount.

    Args:
        amount: Amount to format
        currency: Currency code

    Returns:
        Formatted currency string
    """
    symbols = {
        "USD": "$",
        "EUR": "€",
        "GBP": "£",
        "JPY": "¥",
    }
    symbol = symbols.get(currency, currency)
    return f"{symbol}{amount:,.2f}"


def truncate_string(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate string to maximum length.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated

    Returns:
        Truncated string
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def validate_azure_resource_id(resource_id: str) -> bool:
    """
    Validate Azure resource ID format.

    Args:
        resource_id: Resource ID to validate

    Returns:
        True if valid, False otherwise
    """
    # Azure resource IDs follow pattern:
    # /subscriptions/{subscription-id}/resourceGroups/{resource-group-name}/...
    parts = resource_id.split("/")
    return (
        len(parts) >= 5
        and parts[1] == "subscriptions"
        and parts[3] == "resourceGroups"
    )


def get_resource_id_parts(resource_id: str) -> Dict[str, str]:
    """
    Extract parts from Azure resource ID.

    Args:
        resource_id: Azure resource ID

    Returns:
        Dictionary with resource ID parts
    """
    parts = resource_id.split("/")
    result: Dict[str, str] = {}

    for i in range(1, len(parts), 2):
        if i + 1 < len(parts):
            result[parts[i]] = parts[i + 1]

    return result


class Singleton(type):
    """Metaclass for singleton pattern."""

    _instances: Dict[type, Any] = {}

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        """Create or return existing instance."""
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]
