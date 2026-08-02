<div align="center">

# 🗣️ VisioVoice

### AI-powered lip-reading system that transcribes speech from silent video footage

*Deep learning meets computer vision — turn silent video into text and speech.*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![Node](https://img.shields.io/badge/Node.js-18%2B-green.svg)](https://nodejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.6%2B-EE4C2C.svg)](https://pytorch.org/)

[Repository](https://github.com/Mmanas-tech/VisioVoice) · [Quick Start](#-quick-start) · [API Reference](#-api-endpoints) · [Deployment](#-deployment)

</div>

---

## ✨ Features

| | |
|---|---|
| 👄 **Lip-Reading** | Transcribes speech from silent video using AV-HuBERT (Meta AI) + a custom 3D CNN |
| 🎬 **Video Processing** | Accepts MP4, MOV, AVI, MKV up to 2GB, with automatic face detection & lip extraction |
| 🔊 **Audio Synthesis** | Multi-backend TTS (pyttsx3, ElevenLabs, Bark) converts transcriptions back to speech |
| ⚡ **Real-Time Updates** | WebSocket progress streaming while video processes |
| 📄 **Export Formats** | JSON, SRT, VTT, DOCX, PDF — with timestamps & confidence scores |
| 🔐 **Authentication** | JWT-based auth with role-based access control |
| 🚦 **Rate Limiting** | Configurable per-endpoint limits via Redis |
| 🌗 **Dark / Light Theme** | Toggle in the frontend UI |

---

## 🏗️ Architecture

```
VisioVoice/
├── app/                            # FastAPI backend
│   ├── api/v1/endpoints/           # REST routes (auth, audio, health)
│   ├── core/                       # Security, rate limiter, WebSocket, exceptions
│   ├── ml/                         # ML pipeline
│   │   ├── av_hubert_inference.py  # AV-HuBERT model wrapper
│   │   ├── lip_reading_model.py    # Custom 3D ResNet CNN
│   │   ├── model_manager.py        # Dual-backend model manager
│   │   ├── model_inference.py      # Unified inference dispatcher
│   │   ├── video_preprocessing.py  # Face detection, lip extraction
│   │   └── audio/                  # TTS service
│   ├── services/                   # Business logic
│   └── models/                     # SQLAlchemy DB models
├── frontend/                       # React + TypeScript + Vite
│   ├── src/pages/                  # Dashboard, Landing
│   ├── src/components/             # Navbar, Projects, Settings panels
│   └── src/store/                  # Zustand state management
├── tests/                          # 84 unit & integration tests
├── models/                         # Model checkpoints (gitignored)
├── requirements.txt                # Python dependencies
├── docker-compose.yml              # 8-service stack
└── .env.example                    # Environment variables template
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+
- Redis 7+
- Docker & Docker Compose *(optional)*

### 1 · Clone

```bash
git clone https://github.com/Mmanas-tech/VisioVoice.git
cd VisioVoice
```

### 2 · Backend Setup

```bash
python -m venv venv

# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

pip install -r requirements.txt
```

### 3 · Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### 4 · Configure Environment

```bash
# Windows
copy .env.example .env
# Linux/Mac
cp .env.example .env
```

Edit `.env` with your database URL, Redis URL, JWT secret, and API keys.

### 5 · Or Run the Full Stack with Docker

```bash
docker compose up -d
```

Spins up all **8 services**: backend, frontend, PostgreSQL, Redis, Celery worker, Celery beat, and monitoring.

---

## 🧠 AV-HuBERT Model Setup

The primary lip-reading model uses [Meta's AV-HuBERT](https://github.com/facebookresearch/av_hubert).

### Download the Checkpoint

```
https://dl.fbaipublicfiles.com/avhubert/model/lrs3_vox/vsr/self_large_vox_433h.pt
```

Place the downloaded file at `models/av_hubert.pt`.

### Model Architecture

| Component | Details |
|---|---|
| **Encoder** | 24-layer Transformer · 1024-dim · 16 heads |
| **Decoder** | 6-layer Transformer · 768-dim · 4 heads |
| **Input** | Grayscale 88×88 frames, normalized `(px/255 − 0.421) / 0.165` |
| **Vocabulary** | 1,000 SentencePiece tokens |
| **Parameters** | 477M total |

### Inference Example

```python
from app.ml.av_hubert_inference import load_av_hubert

model = load_av_hubert("models/av_hubert.pt", device="auto")
result = model.infer_single_video(video_frames)

print(result["text"])  # → Transcribed text
```

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/auth/register` | Register a new user |
| `POST` | `/api/v1/auth/login` | Login, returns JWT |
| `POST` | `/api/v1/auth/refresh-token` | Refresh access token |
| `POST` | `/api/v1/audio/transcribe` | Upload video for transcription |
| `GET` | `/api/v1/audio/status/{id}` | Get transcription status |
| `GET` | `/api/v1/audio/download/{id}` | Download result (SRT / JSON / DOCX / PDF) |
| `GET` | `/health` | Health check |
| `WS` | `/ws/{client_id}` | Real-time progress updates |

---

## 🛠️ Tech Stack

<table>
<tr>
<td valign="top" width="50%">

**Backend**
- FastAPI 0.104+ — async REST API
- SQLAlchemy 2.0+ — ORM with PostgreSQL
- Redis — caching, rate limiting, WebSocket pub/sub
- Celery — background task queue
- PyTorch 2.6+ — deep learning inference
- Fairseq 0.12.2 — AV-HuBERT model loading
- OpenCV — video processing
- MediaPipe — face/landmark detection

</td>
<td valign="top" width="50%">

**Frontend**
- React 18+ with TypeScript
- Vite — build tool
- Tailwind CSS — styling
- Zustand — state management
- Socket.IO — real-time communication

</td>
</tr>
</table>

---

## ✅ Testing

```bash
# Run all tests
python -m pytest tests/ -v

# With coverage report
python -m pytest tests/ --cov=app --cov-report=html
```

---

## ⚙️ Configuration

Key environment variables — see `.env.example` for the full list.

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://localhost:5432/visiovoice` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379` |
| `JWT_SECRET_KEY` | Secret for JWT signing | *must set* |
| `AV_HUBERT_CHECKPOINT` | Path to model checkpoint | `models/av_hubert.pt` |
| `AV_HUBERT_DEVICE` | Inference device | `auto` |
| `ELEVENLABS_API_KEY` | ElevenLabs TTS key | *optional* |
| `RATE_LIMIT_PER_MINUTE` | API rate limit | `60` |

---

## 🚢 Deployment

Full guides available in [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md), covering:

- 🐳 Docker Compose *(recommended for development)*
- ☁️ AWS ECS with Terraform
- ☸️ Kubernetes
- 🚂 Railway.app
- 🖥️ Self-hosted VPS

---

## 📄 License

Released under the **MIT License**. See [LICENSE](LICENSE) for full details.

---

<div align="center">

**Last Updated:** August 2026 &nbsp;·&nbsp; **Created by** [Manas](https://github.com/Mmanas-tech)

</div>
