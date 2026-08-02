"""Celery task tests."""

from unittest.mock import MagicMock, patch, AsyncMock
import pytest

from app.tasks.celery_app import celery_app


class TestCeleryApp:
    """Test Celery application configuration."""

    def test_celery_app_name(self):
        assert celery_app.main == "lipread_worker"

    def test_celery_broker_url(self):
        assert "redis" in celery_app.conf.broker_url

    def test_celery_result_backend(self):
        assert "redis" in celery_app.conf.result_backend

    def test_celery_serialization(self):
        assert celery_app.conf.accept_content == ["json"]
        assert celery_app.conf.result_serializer == "json"
        assert celery_app.conf.task_serializer == "json"

    def test_celery_timezone(self):
        assert celery_app.conf.timezone == "UTC"

    def test_celery_task_routes(self):
        routes = celery_app.conf.task_routes
        assert "app.tasks.transcription_tasks.*" in routes
        assert "app.tasks.audio_synthesis_tasks.*" in routes
        assert routes["app.tasks.transcription_tasks.*"]["queue"] == "transcription"
        assert routes["app.tasks.audio_synthesis_tasks.*"]["queue"] == "audio"

    def test_celery_task_limits(self):
        assert celery_app.conf.task_soft_time_limit == 1800
        assert celery_app.conf.task_time_limit == 1860

    def test_celery_retry_settings(self):
        assert celery_app.conf.task_acks_late is True
        assert celery_app.conf.worker_prefetch_multiplier == 1
