import os
import ssl
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from celery import Celery

# Get Redis URL from environment - validate it's not empty
REDIS_URL = os.getenv("REDIS_URL", "").strip()
if not REDIS_URL:
    # Fallback for development
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6380/0")


def _ensure_ssl_param(url: str) -> str:
    """
    Celery's Redis backend requires rediss:// URLs to contain
    `ssl_cert_reqs` as a query parameter. Append it if missing.
    """
    if not url.startswith("rediss://"):
        return url
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    if "ssl_cert_reqs" not in qs:
        separator = "&" if parsed.query else ""
        new_query = f"{parsed.query}{separator}ssl_cert_reqs=CERT_NONE"
        parsed = parsed._replace(query=new_query)
    return urlunparse(parsed)


REDIS_URL = _ensure_ssl_param(REDIS_URL)

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
    broker_connection_retry_on_startup=True,
)

# Additional SSL configuration for rediss:// URLs (Upstash)
if REDIS_URL.startswith("rediss://"):
    celery_app.conf.update(
        broker_use_ssl={
            "ssl_cert_reqs": ssl.CERT_NONE,
        },
        redis_backend_use_ssl={
            "ssl_cert_reqs": ssl.CERT_NONE,
        },
    )
