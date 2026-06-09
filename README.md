# Lip-Reading AI Backend

Production-grade backend for transcribing speech from silent video footage using Deep Learning.

## Architecture

```
FastAPI (API) + Celery (Async Tasks) + PostgreSQL (DB) + Redis (Cache/Queue)
                           ↓
              PyTorch Lip-Reading Model
```

## Quick Start

### 1. Clone and configure

```bash
cp .env.example .env
# Edit .env with your settings
```

### 2. Run with Docker (recommended)

```bash
docker-compose up -d
```

This starts:
- **app** (port 8000) - FastAPI backend
- **postgres** (port 5432) - Database
- **redis** (port 6379) - Cache & message broker
- **celery-worker** - Async task processing
- **celery-beat** - Scheduled tasks

### 3. Run locally (development)

```bash
# Install dependencies
pip install -r requirements.txt

# Start PostgreSQL and Redis (or use Docker for just these)
docker-compose up -d postgres redis

# Run migrations
alembic upgrade head

# Start the application
uvicorn app.main:app --reload --port 8000

# Start Celery worker
celery -A app.tasks.celery_app worker -l info -Q transcription
```

## API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API Endpoints

### Authentication
- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login and get tokens
- `POST /api/v1/auth/refresh-token` - Refresh access token
- `POST /api/v1/auth/logout` - Logout (invalidate token)
- `GET /api/v1/auth/me` - Get current user profile

### Videos
- `POST /api/v1/videos/upload` - Upload video file
- `GET /api/v1/videos` - List user videos
- `GET /api/v1/videos/{id}` - Get video details
- `DELETE /api/v1/videos/{id}` - Soft delete video
- `GET /api/v1/videos/{id}/download` - Download video

### Transcriptions
- `POST /api/v1/transcriptions/process` - Submit for transcription
- `GET /api/v1/transcriptions/{id}` - Get transcription result
- `GET /api/v1/transcriptions/{id}/status` - Get processing status
- `GET /api/v1/transcriptions/{id}/export?format=srt` - Export (json/srt/vtt)
- `DELETE /api/v1/transcriptions/{id}` - Delete transcription
- `POST /api/v1/transcriptions/batch-process` - Batch submit

### Health
- `GET /api/v1/health` - Full health check
- `GET /api/v1/ready` - Readiness probe
- `GET /api/v1/live` - Liveness probe
- `GET /api/v1/metrics` - Prometheus metrics

## Testing

```bash
pytest tests/ -v
pytest tests/ --cov=app --cov-report=html
```

## Project Structure

```
app/
├── main.py              # FastAPI application
├── config.py            # Settings management
├── core/                # Security, exceptions, logging
├── models/              # ORM models & Pydantic schemas
├── api/v1/endpoints/    # API route handlers
├── services/            # Business logic
├── tasks/               # Celery async tasks
├── ml/                  # ML model & preprocessing
└── db/                  # Database & migrations
```

## Key Features

- JWT authentication with refresh tokens
- Async video processing via Celery
- Multi-format transcription export (JSON, SRT, VTT)
- Structured JSON logging
- Prometheus metrics
- Health check endpoints
- Docker deployment ready
- Alembic database migrations
- Comprehensive test suite
