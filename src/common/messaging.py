"""
Message queue abstraction module.

Provides Redis Pub/Sub messaging and Celery task queue integration.
"""

from typing import Any, Callable, Dict, Optional

import redis
from celery import Celery
from kombu import Queue

from src.common.config import get_config
from src.common.logging_config import get_logger

logger = get_logger(__name__)


class MessageQueue:
    """Redis Pub/Sub message queue."""

    def __init__(self):
        """Initialize message queue."""
        self.config = get_config()
        self._redis_client: Optional[redis.Redis] = None

    def get_redis_client(self) -> redis.Redis:
        """
        Get Redis client.

        Returns:
            Redis client instance
        """
        if self._redis_client is None:
            self._redis_client = self._create_redis_client()
        return self._redis_client

    def _create_redis_client(self) -> redis.Redis:
        """
        Create Redis client.

        Returns:
            Redis client instance
        """
        redis_config = self.config.redis

        client = redis.Redis(
            host=redis_config.host,
            port=redis_config.port,
            db=redis_config.db,
            password=redis_config.password,
            decode_responses=redis_config.decode_responses,
            max_connections=redis_config.max_connections,
            ssl=redis_config.ssl,
            socket_keepalive=True,
            socket_connect_timeout=5,
            retry_on_timeout=True,
        )

        # Test connection
        try:
            client.ping()
            logger.info(f"Redis client connected: {redis_config.host}:{redis_config.port}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

        return client

    def publish(self, channel: str, message: Dict[str, Any]) -> int:
        """
        Publish message to channel.

        Args:
            channel: Channel name
            message: Message data (will be JSON serialized)

        Returns:
            Number of subscribers that received the message
        """
        import json
        
        client = self.get_redis_client()
        serialized = json.dumps(message)
        
        try:
            count = client.publish(channel, serialized)
            logger.debug(f"Published message to {channel}: {count} subscribers")
            return count
        except Exception as e:
            logger.error(f"Failed to publish message to {channel}: {e}")
            raise

    def subscribe(self, channel: str, callback: Callable[[Dict[str, Any]], None]) -> None:
        """
        Subscribe to channel and process messages.

        Args:
            channel: Channel name
            callback: Callback function to process messages
        """
        import json
        
        client = self.get_redis_client()
        pubsub = client.pubsub()
        
        try:
            pubsub.subscribe(channel)
            logger.info(f"Subscribed to channel: {channel}")
            
            for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        callback(data)
                    except Exception as e:
                        logger.error(f"Error processing message from {channel}: {e}")
        except Exception as e:
            logger.error(f"Subscription error on {channel}: {e}")
            raise
        finally:
            pubsub.unsubscribe(channel)

    def close(self) -> None:
        """Close Redis connection."""
        if self._redis_client:
            self._redis_client.close()
            logger.info("Redis connection closed")


# Message queue topics
class Topics:
    """Message queue topic names."""
    COST_DATA_COLLECTED = "cost.data.collected"
    ALERT_TRIGGERED = "alert.triggered"
    ALERT_RESOLVED = "alert.resolved"
    RECOMMENDATION_GENERATED = "recommendation.generated"
    RECOMMENDATION_IMPLEMENTED = "recommendation.implemented"
    BUDGET_THRESHOLD_EXCEEDED = "budget.threshold.exceeded"
    ANOMALY_DETECTED = "anomaly.detected"


# Celery application
def create_celery_app() -> Celery:
    """
    Create Celery application.

    Returns:
        Celery app instance
    """
    config = get_config()
    celery_config = config.celery

    app = Celery(
        "azure_cost_agent",
        broker=celery_config.broker_url,
        backend=celery_config.result_backend,
    )

    # Configure Celery
    app.conf.update(
        task_serializer=celery_config.task_serializer,
        result_serializer=celery_config.result_serializer,
        accept_content=celery_config.accept_content,
        timezone=celery_config.timezone,
        enable_utc=celery_config.enable_utc,
        worker_prefetch_multiplier=celery_config.worker_prefetch_multiplier,
        worker_max_tasks_per_child=celery_config.worker_max_tasks_per_child,
        task_track_started=True,
        task_time_limit=3600,  # 1 hour
        task_soft_time_limit=3300,  # 55 minutes
        task_acks_late=True,
        worker_disable_rate_limits=False,
        broker_connection_retry_on_startup=True,
    )

    # Define task queues
    app.conf.task_queues = (
        Queue("default", routing_key="task.default"),
        Queue("monitoring", routing_key="task.monitoring"),
        Queue("alerting", routing_key="task.alerting"),
        Queue("recommendations", routing_key="task.recommendations"),
    )

    # Default queue
    app.conf.task_default_queue = "default"
    app.conf.task_default_routing_key = "task.default"

    # Auto-discover tasks
    app.autodiscover_tasks([
        "src.monitoring.scheduler",
        "src.alerting.alert_manager",
        "src.recommendations.engines.recommendation_engine",
    ])

    logger.info("Celery app created successfully")
    return app


# Global Celery app instance
celery_app = create_celery_app()


# Global message queue instance
_message_queue: Optional[MessageQueue] = None


def get_message_queue() -> MessageQueue:
    """
    Get global message queue instance.

    Returns:
        MessageQueue instance
    """
    global _message_queue
    if _message_queue is None:
        _message_queue = MessageQueue()
    return _message_queue


def publish_message(topic: str, message: Dict[str, Any]) -> int:
    """
    Publish message to topic.

    Args:
        topic: Topic name
        message: Message data

    Returns:
        Number of subscribers
    """
    mq = get_message_queue()
    return mq.publish(topic, message)


def close_message_queue() -> None:
    """Close message queue connection."""
    global _message_queue
    if _message_queue:
        _message_queue.close()
        _message_queue = None
