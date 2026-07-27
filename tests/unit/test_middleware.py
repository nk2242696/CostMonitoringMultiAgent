"""Unit tests for API middleware."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api.middleware import _TokenBucket


class TestTokenBucket:
    """Tests for the rate limit token bucket."""

    def test_initial_capacity(self):
        bucket = _TokenBucket(rate=1.0, capacity=10)
        assert bucket.tokens == 10.0

    def test_consume_reduces_tokens(self):
        bucket = _TokenBucket(rate=0.0, capacity=5)  # No refill
        assert bucket.consume() is True
        assert bucket.tokens < 5.0

    def test_consume_fails_when_empty(self):
        bucket = _TokenBucket(rate=0.0, capacity=1)
        bucket.tokens = 0.0
        assert bucket.consume() is False

    def test_consume_all_tokens(self):
        bucket = _TokenBucket(rate=0.0, capacity=3)
        assert bucket.consume() is True
        assert bucket.consume() is True
        assert bucket.consume() is True
        assert bucket.consume() is False


class TestExceptions:
    """Tests for custom exception classes."""

    def test_not_found_error(self):
        from src.api.exceptions import NotFoundError

        exc = NotFoundError("Budget", "budget-123")
        assert exc.status_code == 404
        assert exc.error_code == "NOT_FOUND"
        assert "Budget" in exc.message
        assert "budget-123" in exc.message

    def test_validation_error(self):
        from src.api.exceptions import ValidationError

        exc = ValidationError("Invalid date range", field="start_date")
        assert exc.status_code == 422
        assert exc.details["field"] == "start_date"

    def test_conflict_error(self):
        from src.api.exceptions import ConflictError

        exc = ConflictError("Budget already exists")
        assert exc.status_code == 409

    def test_rate_limit_error(self):
        from src.api.exceptions import RateLimitError

        exc = RateLimitError(retry_after=30)
        assert exc.status_code == 429
        assert exc.details["retry_after_seconds"] == 30

    def test_external_service_error(self):
        from src.api.exceptions import ExternalServiceError

        exc = ExternalServiceError("Azure Cost Management", "API unavailable")
        assert exc.status_code == 502
        assert "Azure Cost Management" in exc.message
