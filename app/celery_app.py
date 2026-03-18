import os
from celery import Celery

# Get Redis URL from environment - validate it's not empty
REDIS_URL = os.getenv("REDIS_URL", "").strip()
if not REDIS_URL:
    # Fallback for development
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6380/0")

celery_app = Celery(
    "infiniteseo_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.worker"]
)

# Configure Redis connection settings for TLS support
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Redis-specific settings for TLS connections
    broker_connection_retry_on_startup=True,
    broker_transport_options={
        'master_name': 'mymaster'
    } if 'rediss://' in REDIS_URL else {},  # Only for Redis Sentinel
)
