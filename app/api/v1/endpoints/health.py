"""Health check and monitoring endpoints."""

import logging
import os
import shutil
from datetime import datetime, timezone

import psutil
from fastapi import APIRouter, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    generate_latest,
    multiprocess,
)

from app import __version__
from app.config import get_settings
from app.models.schemas import HealthResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Health"])

registry = CollectorRegistry()

try:
    multiprocess
    registry = CollectorRegistry()
except Exception:
    pass


def check_database() -> str:
    """Check database connectivity."""
    try:
        from app.db.database import engine
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        return "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return "unhealthy"


def check_redis() -> str:
    """Check Redis connectivity."""
    try:
        import redis
        settings = get_settings()
        client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        client.ping()
        return "healthy"
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return "unhealthy"


def check_celery() -> str:
    """Check Celery worker availability."""
    try:
        from app.tasks.celery_app import celery_app
        inspect = celery_app.control.inspect(timeout=2)
        active = inspect.active()
        if active:
            return "healthy"
        return "degraded"
    except Exception as e:
        logger.error(f"Celery health check failed: {e}")
        return "unhealthy"


def check_disk_space() -> str:
    """Check available disk space."""
    try:
        usage = shutil.disk_usage("/")
        free_gb = usage.free / (1024 ** 3)
        if free_gb < 1:
            return "critical"
        elif free_gb < 5:
            return "warning"
        return "healthy"
    except Exception:
        return "unknown"


def check_gpu() -> bool:
    """Check GPU availability."""
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


@router.get("/health", response_model=HealthResponse)
def health_check():
    """Comprehensive health check endpoint."""
    db_status = check_database()
    redis_status = check_redis()
    celery_status = check_celery()
    disk_status = check_disk_space()
    gpu_available = check_gpu()

    overall = "healthy"
    if "unhealthy" in [db_status, redis_status]:
        overall = "unhealthy"
    elif "degraded" in [db_status, redis_status, celery_status] or disk_status == "warning":
        overall = "degraded"

    return HealthResponse(
        status=overall,
        timestamp=datetime.now(timezone.utc),
        components={
            "database": db_status,
            "redis": redis_status,
            "celery": celery_status,
            "disk_space": disk_status,
            "gpu_available": gpu_available,
        },
        version=__version__,
    )


@router.get("/ready")
def readiness_check():
    """Readiness probe for Kubernetes."""
    db_status = check_database()
    if db_status != "healthy":
        return Response(status_code=503, content="Not ready")
    return {"status": "ready"}


@router.get("/live")
def liveness_check():
    """Liveness probe for Kubernetes."""
    return {"status": "alive"}


@router.get("/metrics")
def metrics():
    """Prometheus metrics endpoint."""
    try:
        return Response(
            content=generate_latest(registry),
            media_type=CONTENT_TYPE_LATEST,
        )
    except Exception:
        return Response(content="# No metrics available", media_type="text/plain")
