# VisioVoice

AI-powered lip-reading system that transcribes speech from silent video footage using deep learning.

**Repository**: https://github.com/Mmanas-tech/VisioVoice  
**License**: MIT

---

## Features

- **Lip-Reading**: Transcribes speech from silent video using AV-HuBERT (Facebook Research) and custom 3D CNN
- **Video Processing**: Accepts MP4, MOV, AVI, MKV up to 2GB with automatic face detection and lip extraction
- **Audio Synthesis**: Multi-backend TTS (pyttsx3, ElevenLabs, Bark) converts transcriptions to speech
- **Real-time Updates**: WebSocket progress streaming during video processing
- **Export Formats**: JSON, SRT, VTT, DOCX, PDF with timestamped transcriptions and confidence scores
- **Authentication**: JWT-based auth with role-based access control
- **Rate Limiting**: Configurable per-endpoint rate limits via Redis
- **Dark/Light Theme**: Toggle between themes in the frontend

---

## Architecture

```
VisioVoice/
├── app/                        # FastAPI backend
│   ├── api/v1/endpoints/       # REST API routes (auth, audio, health)
│   ├── core/                   # Security, rate limiter, WebSocket, exceptions
│   ├── ml/                     # ML pipeline
│   │   ├── av_hubert_inference.py  # AV-HuBERT model wrapper
│   │   ├── lip_reading_model.py    # Custom 3D ResNet CNN
│   │   ├── model_manager.py        # Dual-backend model manager
│   │   ├── model_inference.py      # Unified inference dispatcher
│   │   ├── video_preprocessing.py  # Face detection, lip extraction
│   │   └── audio/              # TTS service
│   ├── services/               # Business logic
│   └── models/                 # SQLAlchemy DB models
├── frontend/                   # React + TypeScript + Vite
│   ├── src/pages/              # Dashboard, Landing
│   ├── src/components/         # Navbar, Projects, Settings panels
│   └── src/store/              # Zustand state management
├── tests/                      # 84 unit & integration tests
├── models/                     # Model checkpoints (gitignored)
├── requirements.txt            # Python dependencies
├── docker-compose.yml          # 8-service stack
└── .env.example                # Environment variables template
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+
- Redis 7+
- Docker & Docker Compose (optional)

### 1. Clone & Setup

```bash
git clone https://github.com/Mmanas-tech/VisioVoice.git
cd VisioVoice
```

### 2. Backend

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate    # Linux/Mac

pip install -r requirements.txt
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

### 4. Environment Variables

```bash
copy .env.example .env         # Windows
# cp .env.example .env         # Linux/Mac
```

Edit `.env` with your database URL, Redis URL, JWT secret, and API keys.

### 5. Docker Compose (Full Stack)

```bash
docker compose up -d
```

Starts 8 services: backend, frontend, PostgreSQL, Redis, Celery worker, Celery beat, and monitoring.

---

## AV-HuBERT Model Setup

The primary lip-reading model uses [Facebook's AV-HuBERT](https://github.com/facebookresearch/av_hubert).

### Download Checkpoint

Download `self_large_vox_433h.pt` from:
```
https://dl.fbaipublicfiles.com/avhubert/model/lrs3_vox/vsr/self_large_vox_433h.pt
```

Place it in `models/av_hubert.pt`.

### Model Architecture

| Component | Details |
|-----------|---------|
| **Encoder** | 24-layer Transformer, 1024-dim, 16 heads |
| **Decoder** | 6-layer Transformer, 768-dim, 4 heads |
| **Input** | Grayscale 88x88 video frames, normalized `(px/255 - 0.421) / 0.165` |
| **Vocabulary** | 1000 SentencePiece tokens |
| **Parameters** | 477M total |

### Inference

```python
from app.ml.av_hubert_inference import load_av_hubert

model = load_av_hubert("models/av_hubert.pt", device="auto")
result = model.infer_single_video(video_frames)
print(result["text"])  # Transcribed text
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/auth/register` | Register new user |
| `POST` | `/api/v1/auth/login` | Login, returns JWT |
| `POST` | `/api/v1/auth/refresh-token` | Refresh access token |
| `POST` | `/api/v1/audio/transcribe` | Upload video for transcription |
| `GET` | `/api/v1/audio/status/{id}` | Get transcription status |
| `GET` | `/api/v1/audio/download/{id}` | Download result (SRT/JSON/DOCX/PDF) |
| `GET` | `/health` | Health check |
| `WS` | `/ws/{client_id}` | Real-time progress updates |

---

## Tech Stack

### Backend
- **FastAPI** 0.104+ — async REST API
- **SQLAlchemy** 2.0+ — ORM with PostgreSQL
- **Redis** — caching, rate limiting, WebSocket pub/sub
- **Celery** — background task queue
- **PyTorch** 2.6+ — deep learning inference
- **Fairseq** 0.12.2 — AV-HuBERT model loading
- **OpenCV** — video processing
- **MediaPipe** — face/landmark detection

### Frontend
- **React** 18+ with TypeScript
- **Vite** — build tool
- **Tailwind CSS** — styling
- **Zustand** — state management
- **Socket.IO** — real-time communication

---

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# With coverage
python -m pytest tests/ --cov=app --cov-report=html
```

---

## Configuration

Key environment variables (see `.env.example` for full list):

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://localhost:5432/visiovoice` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379` |
| `JWT_SECRET_KEY` | Secret for JWT signing | *(must set)* |
| `AV_HUBERT_CHECKPOINT` | Path to model checkpoint | `models/av_hubert.pt` |
| `AV_HUBERT_DEVICE` | Inference device | `auto` |
| `ELEVENLABS_API_KEY` | ElevenLabs TTS key | *(optional)* |
| `RATE_LIMIT_PER_MINUTE` | API rate limit | `60` |

---

## Deployment

See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for guides covering:
- Docker Compose (recommended for development)
- AWS ECS with Terraform
- Kubernetes
- Railway.app
- Self-hosted VPS

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

**Last Updated**: August 2026  
**Created by**: [Manas](https://github.com/Mmanas-tech)
