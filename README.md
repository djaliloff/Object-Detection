<div align="center">

<img src="https://img.shields.io/badge/version-1.0-blue?style=for-the-badge" alt="Version 1.0"/>
<img src="https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>
<img src="https://img.shields.io/badge/React-JavaScript-61DAFB?style=for-the-badge&logo=react&logoColor=black" alt="React"/>
<img src="https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker"/>
<img src="https://img.shields.io/badge/PostgreSQL-TimescaleDB-336791?style=for-the-badge&logo=postgresql&logoColor=white" alt="PostgreSQL"/>
<img src="https://img.shields.io/badge/YOLOv8-ONNX-00BFFF?style=for-the-badge" alt="YOLOv8"/>

# 🎯 AI-Powered Multi-Modal Video Surveillance Platform

### RGB / IR / Thermal Fusion · Real-Time Object Detection · Event Intelligence

> **A comprehensive, microservice-based AI surveillance platform supporting RGB, Near-Infrared (NIR), and Long-Wave Infrared (LWIR/Thermal) camera fusion.**

[📚 Documentation](#-documentation) · [🚀 Quick Start](#-quick-start) · [🏗️ Architecture](#️-system-architecture) · [🤖 AI Pipeline](#-ai-inference-pipeline) · [🤝 Contributing](#-contributing)

</div>

---

## 📋 Table of Contents

- [Executive Summary](#-executive-summary)
- [Key Features](#-key-features)
- [System Architecture](#️-system-architecture)
- [Technology Stack](#-technology-stack)
- [Quick Start](#-quick-start)
- [AI Inference Pipeline](#-ai-inference-pipeline)
- [Event Detection Engine](#-event-detection-engine)
- [Database Design](#️-database-design)
- [Frontend Dashboard](#-frontend-dashboard)
- [API Reference](#-api-reference)
- [Deployment](#-deployment)
- [Testing Strategy](#-testing-strategy)
- [Datasets](#-recommended-datasets)
- [Security & Privacy](#-security--privacy)
- [Modularity & Extensions](#-modularity--extension-points)
- [Risk Management](#️-risk-management)
- [Deliverables](#-deliverables)

---

## 🔭 Executive Summary

This platform is a **production-grade, modular AI video surveillance system** that processes multi-modal camera feeds — RGB, near-infrared (NIR), and long-wave infrared (LWIR/thermal) — in real time. It provides:

- 🟢 **Real-time object detection** with bounding-box overlays (< 500 ms end-to-end latency)
- 🔴 **Multi-frame event detection**: intrusion, loitering, line-crossing, abandoned objects
- 🎞️ **RGB-T fusion inference** with illumination-aware gating for 24/7 robustness
- 🗄️ **Full data historization** in PostgreSQL/TimescaleDB (frames, detections, events, snapshots)

The architecture follows strict separation of concerns, standardized interfaces (REST + WebSocket + gRPC), and a plugin system for adding new models or modalities without touching core infrastructure.

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 🌈 **Multi-Modal Fusion** | RGB, Thermal-only, and RGB-T synchronized fusion modes per camera |
| ⚡ **< 500ms Latency** | Frame capture to browser display end-to-end |
| 🤖 **YOLOv8/v11 Detection** | ONNX Runtime or Triton for portable GPU/CPU inference |
| 🔢 **Object Tracking** | ByteTrack (fast) or DeepSORT (Re-ID) per camera |
| 🚨 **Smart Events** | Intrusion, loitering, line-crossing, abandoned object, speed anomaly |
| 📺 **WebRTC Streaming** | Sub-200 ms video via go2rtc (RTSP → WebRTC) |
| 🗺️ **Zone Editor** | Browser canvas–based polygon/line drawing per camera view |
| 📊 **Analytics Dashboard** | Detection counts, event heatmaps, camera uptime metrics |
| 🔭 **ONVIF Discovery** | Auto-discover cameras on local subnet via WS-Discovery |
| 🔐 **JWT Auth + RBAC** | Admin / Operator / Viewer role-based access |
| 🐘 **TimescaleDB** | Time-series partitioned storage with configurable retention |
| 🔌 **Plugin System** | Add models, event types, and notification channels without touching core |

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React + JS)                        │
│   MultiCameraGrid · EventTimeline · ZoneEditor · AnalyticsDashboard │
└────────────────────────────┬────────────────────────────────────────┘
                             │ WebSocket / REST
┌────────────────────────────▼────────────────────────────────────────┐
│                    BACKEND API (FastAPI)                             │
│          JWT Auth · REST /api/v1/ · Socket.io WebSocket             │
└────┬──────────────────────────────────────┬───────────────────────--┘
     │ PostgreSQL/TimescaleDB                │ Redis Streams
┌────▼──────┐   ┌──────────────┐   ┌────────▼──────────┐
│  Database │   │ Event Engine │◄──│  AI Inference     │
│  (PG+TSB) │   │  ByteTrack   │   │  ONNX/Triton      │
└───────────┘   │  DeepSORT    │   │  YOLOv8 RGB/IR/   │
                │  Zone Logic  │   │  RGB-T Fusion     │
                └──────────────┘   └───────────────────┘
                                            ▲ Redis Streams
                               ┌────────────┴──────────────┐
                               │   Camera Gateway          │
                               │   RTSP · ONVIF · SDK      │
                               │   go2rtc (WebRTC)         │
                               └───────────────────────────┘
                                    ▲          ▲         ▲
                               RGB Cams   Thermal    Dual-Sensor
```

### Microservices

| Service | Responsibility | Tech |
|---|---|---|
| **Camera Gateway** | RTSP ingestion, ONVIF discovery, frame routing | Python, OpenCV, GStreamer |
| **AI Inference Engine** | RGB/thermal/fusion detection, model serving | Python, ONNX Runtime, Triton |
| **Event Processor** | Object tracking, intrusion/loitering/event logic | Python, NumPy, Shapely |
| **Backend API** | REST + WebSocket, auth, business logic, DB access | FastAPI, SQLAlchemy |
| **Frontend Dashboard** | Live cameras, event feed, admin panels | React.js, JavaScript, Tailwind |
| **Message Broker** | Async inter-service messaging | Redis Streams / RabbitMQ |

### Inter-Service Communication

- **Redis Streams** — high-throughput frame/detection queuing with consumer groups
- **WebSocket (Socket.io)** — real-time bidirectional frontend updates
- **REST API** — configuration, historical queries, admin operations
- **gRPC (optional)** — Triton Inference Server for GPU-optimized inference at scale

---

## 🛠️ Technology Stack

### Backend
| Layer | Technology |
|---|---|
| API Framework | FastAPI (async, auto OpenAPI docs) |
| ORM | SQLAlchemy + Alembic migrations |
| Database | PostgreSQL 16 + TimescaleDB extension |
| Message Queue | Redis 7 Streams |
| AI Runtime | ONNX Runtime / NVIDIA Triton |
| Object Tracking | ByteTrack / DeepSORT |
| Computer Vision | OpenCV, GStreamer |
| Geometry | Shapely (zone/line intersection) |
| Auth | JWT (PyJWT) + bcrypt |
| Metrics | Prometheus + Grafana |

### Frontend
| Layer | Technology |
|---|---|
| Framework | React.js + JavaScript (v22) |
| Styling | Tailwind CSS |
| State | Zustand |
| Data Fetching | TanStack Query (React Query) |
| Real-Time | Socket.io-client |
| Video | go2rtc (WebRTC) / HLS.js / JSMpeg |
| Canvas Overlay | Konva.js / Fabric.js |
| Charts | Recharts |
| Testing | Playwright, Vitest |

### Infrastructure
| Layer | Technology |
|---|---|
| Containerization | Docker + Docker Compose |
| CI/CD | GitHub Actions + GHCR |
| Video Relay | go2rtc (RTSP → WebRTC) |
| Linting | Black, isort, ESLint, Prettier |
| Logging | structlog (JSON structured) |

---

## 🚀 Quick Start

### Prerequisites

- **Docker** ≥ 24 + **Docker Compose** V2
- (Optional) NVIDIA GPU with CUDA 11.8+ for accelerated inference
- Git

### 1. Clone the Repository

```bash
git clone https://github.com/djaliloff/Object-Detection.git 
cd Object-Detection
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your settings:
# - DATABASE_URL
# - REDIS_URL
# - JWT_SECRET_KEY
# - Camera RTSP credentials
```

### 3. Start All Services

```bash
docker compose up --build
```

> 💡 **No GPU?** The AI engine automatically falls back to CPU-based ONNX Runtime. Use `YOLOv8n` (nano) for reasonable CPU performance.

### 4. Access the Dashboard

| Service | URL |
|---|---|
| Frontend Dashboard | http://localhost:80 |
| Backend API (Swagger) | http://localhost:8000/docs |
| WebSocket | ws://localhost:8080/ws/live |
| go2rtc WebRTC | http://localhost:1984 |
| Grafana Monitoring | http://localhost:3000 |

### 5. First Login

Default admin credentials (change immediately):
```
Username: admin
Password: changeme
```

## 🤖 AI Inference Pipeline

### Model Roadmap (Phased Development)

| Phase | Model | Modality | Dataset | Target | Timeline |
|---|---|---|---|---|---|
| **Phase 1** | YOLOv8n/s (COCO pre-trained) | RGB only | COCO | mAP@50 > 0.45 | Weeks 1–3 |
| **Phase 2** | YOLOv8s (fine-tuned) | Thermal only | FLIR ADAS | Per-class mAP day/night | Weeks 4–6 |
| **Phase 3a** | Two-stream YOLOv8 | RGB-T late fusion | KAIST, LLVIP | LAMR, mAP@50 | Weeks 7–9 |
| **Phase 3b** | Gated fusion (IAF-style) | RGB-T + illumination gate | KAIST, LLVIP | +5% over concat baseline | Weeks 9–10 |
| **Phase 4** | Distilled thermal-only | Thermal (night deployment) | Knowledge distillation | < 5% drop vs fusion | Week 11 |

### Multi-Modal Stream Routing

The Camera Gateway tags each frame with its modality. The AI router dispatches accordingly:

```
modality=rgb     →  RGB detection pipeline (YOLOv8/v11)
modality=thermal →  Thermal pipeline (CRT-YOLO or fine-tuned FLIR)
modality=rgb_t   →  Fusion pipeline (two-stream + illumination gate)
```

Synchronized RGB-T pairs are temporally aligned within a **50 ms tolerance window** before being dispatched to fusion inference.

### RGB-T Fusion Architecture

Three progressive fusion strategies are implemented:

1. **Late Fusion Baseline** — Two independent YOLOv8 backbones; feature maps from FPN/PAN concatenated before the shared detection head.
2. **Illumination-Aware Gating (IAF-style)** — Scalar gate `α ∈ [0,1]` determined by RGB image luminance: `F_fused = α·F_rgb + (1−α)·F_thermal`. At night, α → 0, automatically relying on thermal features.
3. **Cross-Modal Attention (Advanced)** — Transformer cross-attention between backbone branches at each FPN level, enabling selective feature exchange (highest accuracy, requires careful tuning).

### Reference Research

| Paper | Contribution |
|---|---|
| El Ahmar et al. (CVPR 2023) | Sigmoid-gated early fusion, +9% mAP |
| MRD-YOLO (2024) | Interaction-based multispectral fusion on FLIR & M3FD |
| MDQF (2025) | Dual DETR branches with cross-modal query exchange |
| IAF-RCNN | Illumination-Aware Faster R-CNN canonical baseline |
| CRT-YOLO (2025) | Thermal-only detector with multi-scale attention |

---

## 🚨 Event Detection Engine

### Tracking

| Tracker | Strength | Use Case |
|---|---|---|
| **ByteTrack** | Lightweight, handles low-confidence detections | Most deployments (recommended default) |
| **DeepSORT** | Re-ID feature extractor for occlusion robustness | Dense/crowded scenes |

### Event Types

| Event | Trigger Logic | Required Config |
|---|---|---|
| **Intrusion** | Track centroid enters exclusion zone polygon | Zone polygon, dwell threshold (e.g. 2s) |
| **Loitering** | Track stays in zone > T seconds with minimal displacement | Zone polygon, T threshold, displacement threshold |
| **Line Crossing** | Track trajectory intersects virtual line (A→B, B→A, both) | Line coords, direction |
| **Abandoned Object** | Static non-person detection persists > T seconds | T threshold, min object area |
| **Speed Anomaly** | Track displacement/time exceeds calibrated threshold | Speed threshold, pixel-to-meter calibration |

### Zone & Line Configuration

Operators draw zones and lines directly on the live camera view in the browser. Coordinates are stored as JSONB arrays in **normalized [0,1] relative coordinates** for resolution independence.

---

## 🗄️ Database Design

### Core Schema

| Table | Description |
|---|---|
| `cameras` | Camera registry, RTSP URL, credentials (encrypted), modality, status |
| `camera_groups` | Logical grouping by zone/building |
| `frames` | Frame metadata (actual images stored on disk/S3) |
| `detections` | Per-frame: bbox, class, confidence, track_id, features (JSONB) |
| `tracks` | Aggregated track lifecycle across frames |
| `events` | Multi-frame events with severity, zone, snapshot refs |
| `zones` | Per-camera polygons and counting lines (JSONB) |
| `users` | Authentication with role (Admin/Operator/Viewer) |
| `audit_log` | Full audit trail of user actions |

### Indexing Strategy

- B-tree on `(camera_id, timestamp)` — all time-series tables
- GIN on `event_data` and `features_json` JSONB — flexible querying
- Partial index on `events WHERE status = 'new'` — fast alert retrieval
- Composite on `detections(camera_id, object_class, timestamp)` — analytics queries

### Data Retention

The `detections` table is partitioned by time range (daily/weekly) using PostgreSQL declarative partitioning. A background job automatically drops partitions beyond the configured retention window (7d / 30d / 1y).

---

## 💻 Frontend Dashboard

### Video Rendering

```
RTSP Camera → go2rtc → WebRTC API → Browser (<200ms latency)
                ↓
         MJPEG fallback over WebSocket (1–4 cams, simple setup)
```

Detection bounding boxes are rendered on an **HTML5 Canvas layer** over the video element — no re-encoding required, fully toggleable.

### UI Components

| Component | Description | Priority |
|---|---|---|
| **MultiCameraGrid** | Responsive 1×1 → 4×4 grid with drag-to-rearrange | 🔴 High |
| **CameraFullView** | Full-screen single cam with PTZ controls + live overlay | 🔴 High |
| **EventTimeline** | Chronological event feed, filterable by type/camera/time | 🔴 High |
| **ZoneEditor** | Canvas polygon/line drawing tool on camera view | 🔴 High |
| **CameraManager** | CRUD, ONVIF discovery, connection test | 🔴 High |
| **AnalyticsDashboard** | Detection counts, event frequency, uptime charts (Recharts) | 🟡 Medium |
| **UserAdmin** | User management + role assignment | 🟡 Medium |
| **SystemConfig** | Retention policies, detection thresholds, notifications | 🟡 Medium |

---

## 📡 API Reference

Base URL: `http://localhost:8000/api/v1/`

Interactive docs (Swagger UI): `http://localhost:8000/docs`

### Core Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET/POST` | `/cameras` | List all cameras / Register new camera |
| `GET/PUT/DELETE` | `/cameras/{id}` | Get, update, or remove a camera |
| `POST` | `/cameras/discover` | Trigger ONVIF network discovery |
| `GET` | `/cameras/{id}/health` | Camera health metrics (FPS, errors) |
| `GET` | `/detections` | Query detections (camera, class, time, pagination) |
| `GET` | `/events` | Query events with filters |
| `PUT` | `/events/{id}/status` | Update event status (new/viewed/resolved) |
| `GET/POST` | `/zones` | List / Create detection zones |
| `POST` | `/auth/login` | JWT authentication |
| `GET` | `/analytics/summary` | Aggregated dashboard statistics |
| `WS` | `/ws/live` | Real-time frames + detections + events |

### WebSocket Event Types

| Event | Payload |
|---|---|
| `frame_update` | base64 annotated frame + detection metadata |
| `detection` | Lightweight detection JSON (WebRTC mode) |
| `event_alert` | New event: type, severity, camera, thumbnail |
| `camera_status` | Online/offline/error state change |
| `config_change` | Zone or system config update |

---

## 🐳 Deployment

### Repository Structure

```
multimodal-vs-platform/
├── camera-gateway/
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
├── ai-engine/
│   ├── Dockerfile
│   ├── inference.py
│   ├── model_registry.yaml
│   └── requirements.txt
├── event-processor/
│   ├── Dockerfile
│   ├── processor.py
│   └── requirements.txt
├── backend-api/
│   ├── Dockerfile
│   ├── main.py          ← FastAPI app
│   ├── models.py
│   ├── database.py
│   └── requirements.txt
├── frontend/
│   ├── Dockerfile
│   ├── public/
│   └── src/
│       ├── components/
│       ├── pages/
│       └── App.jsx
├── docker-compose.yml   ← orchestrates all services
├── docker-compose.override.yml  ← gitignored (local tweaks only)
├── .env.example         ← committed template
├── .env                 ← gitignored (your secrets)
├── .gitignore
└── README.md
```

### What Is / Isn't Tracked by Git

| File / Folder | In Git | Reason |
|---|---|---|
| `Dockerfile` (each service) | ✅ Yes | Must be versioned |
| `docker-compose.yml` | ✅ Yes | Must be versioned |
| `docker-compose.override.yml` | ❌ No | Local dev tweaks only |
| `.env` | ❌ No | Contains secrets |
| `.env.example` | ✅ Yes | Safe template |
| `/data/`, `/models/`, `/snapshots/` | ❌ No | Runtime data, too large |
| `*.onnx`, `*.pt`, `*.engine` | ❌ No | Large binary model files |
| `node_modules/` | ❌ No | Rebuilt via `npm install` |
| `__pycache__/`, `.venv/` | ❌ No | Rebuilt locally |

### Docker Compose Services (Planned)

| Container | Base Image | Exposed Port | Volume |
|---|---|---|---|
| `camera-gateway` | `python:3.11-slim` + OpenCV | Internal | `/data/frames` |
| `ai-engine` | `python:3.11-slim` + ONNX Runtime | `8001` (gRPC) | `/models` |
| `event-processor` | `python:3.11-slim` | Internal | — |
| `backend-api` | `python:3.11-slim` + FastAPI | `8000` (HTTP), `8080` (WS) | — |
| `frontend` | `node:22-alpine` → `nginx:alpine` | `80` / `443` | — |
| `postgres` | `timescale/timescaledb:latest-pg16` | `5432` | `/db-data` |
| `redis` | `redis:7-alpine` | `6379` | — |
| `go2rtc` | `alexxit/go2rtc` | `1984`, `8555` (WebRTC) | — |

> 💡 **No GPU?** Set `AI_BACKEND=onnxruntime-cpu` in `.env`. The engine falls back to CPU inference automatically. Use `YOLOv8n` (nano) for acceptable performance.

### Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

```env
# Database
DATABASE_URL=postgresql://user:password@postgres:5432/surveillance

# Redis
REDIS_URL=redis://redis:6379

# Auth
JWT_SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256
JWT_EXPIRE_HOURS=8

# AI Engine
AI_BACKEND=onnxruntime-gpu   # or onnxruntime-cpu
MODEL_PATH=/models

# go2rtc WebRTC relay
GO2RTC_URL=http://go2rtc:1984

# Camera credentials (per camera, also configurable via UI)
DEFAULT_RTSP_USER=admin
DEFAULT_RTSP_PASS=password
```

### Starting the Stack

```bash
# Full stack (requires Docker + Docker Compose V2)
docker compose up --build

# CPU-only (no GPU)
AI_BACKEND=onnxruntime-cpu docker compose up --build

# Demo mode — mock RTSP cameras from video files (no hardware needed)
docker compose --profile demo up
```

### Service URLs

| Service | URL |
|---|---|
| Frontend Dashboard | http://localhost:80 |
| Backend API (Swagger) | http://localhost:8000/docs |
| WebSocket | ws://localhost:8080/ws/live |
| go2rtc WebRTC | http://localhost:1984 |
| Grafana Monitoring | http://localhost:3000 |
| Prometheus Metrics | http://localhost:9090 |

### CI/CD Pipeline

```
[Push to feature/*]
      ↓
[Pre-commit: Black + isort + ESLint + Prettier]
      ↓
[GitHub Actions: Lint → Unit Tests → Docker Build → Integration Tests]
      ↓
[Push to ghcr.io (GitHub Container Registry)]
      ↓
[Merge to develop → staging deploy]
[Merge to main   → production deploy]
```

### Monitoring

- **Prometheus** — metrics exposed by each Python service via `prometheus_client`
- **Grafana** — dashboards: inference latency, frame throughput, queue depth, camera uptime
- **Structured JSON logging** — via `structlog`, collected by Docker's logging driver

---

## 🧪 Testing Strategy

| Level | Scope | Tools | Coverage Target |
|---|---|---|---|
| **Unit** | Preprocessing, NMS, zone geometry, JWT validation | pytest, Jest/Vitest | > 70% core logic |
| **Integration** | API → DB, Gateway → Redis, Event → API | pytest + testcontainers | All critical data paths |
| **End-to-End** | Synthetic cam → detection → event → frontend notification | Playwright, custom Python | Top 5 user scenarios |
| **Model** | Detection accuracy on held-out test sets | Ultralytics val, custom eval scripts | mAP within 2% of baseline |
| **Performance** | Latency benchmarks (< 500ms frame-to-display, < 100ms inference) | Locust (API), custom timing | All KPI criteria |

A **mock-camera service** replays RTSP-tagged pre-recorded video (including FLIR ADAS & LLVIP thermal sequences) for fully offline testing with labeled ground truth.

---

## 📦 Recommended Datasets

| Dataset | Modality | Size | Classes | Use Case |
|---|---|---|---|---|
| **FLIR ADAS Thermal** | Thermal (8–14 µm) | ~26K images | Person, car, bicycle, dog | Thermal-only baseline training |
| **KAIST Multispectral** | RGB + Thermal (paired) | 95K pairs | Pedestrian | RGB-T fusion training & LAMR benchmark |
| **LLVIP** | RGB + IR (low-light, paired) | 15K pairs | Pedestrian | Night-time fusion validation |
| **M3FD** | RGB + Thermal (multi-scene) | 4.2K pairs | Person, car, bus, truck, lamp | Cross-scenario fusion evaluation |
| **DroneVehicle** | RGB + IR (aerial) | 56.8K images | Vehicle classes (rotated boxes) | Aerial extension (optional) |
| **COCO 2017** | RGB | 118K / 5K | 80 classes | RGB pre-training & general benchmarks |

---

## 🔐 Security & Privacy

### Network Security
- RTSPS (RTSP over TLS) where camera firmware supports it
- All inter-service traffic on Docker internal network
- HTTPS via nginx reverse proxy with Let's Encrypt certificates
- Camera credentials encrypted at rest using Fernet symmetric encryption

### Application Security
- JWT tokens with 8h expiry + HTTP-only secure refresh cookies
- Role-based access control enforced at API middleware (Admin / Operator / Viewer)
- Pydantic model validation on all API endpoints
- Rate limiting on `/auth/login` against brute-force
- CORS restricted to known frontend origins

### Privacy & Ethics
- **Data minimization**: detection metadata stored, not raw video where possible
- **Configurable retention** with automatic deletion of expired data
- **Audit logging** of all user access to video feeds and event data
- **Anonymization option**: optional face blurring for stored snapshots
- **18-07 / GDPR compliance** documentation template for national deployments

---

## 🔌 Modularity & Extension Points

### Plugin Architecture

| Plugin Type | How to Add |
|---|---|
| **Model Plugin** | Export to ONNX → add entry to `model_registry.yaml` → configure per camera |
| **Event Plugin** | Create Python class inheriting `BaseEventDetector` in `events/detectors/` |
| **Notification Plugin** | Implement `send()` method for email, SMS, MQTT, Telegram, webhook |
| **Camera Adapter** | Implement `CameraAdapter` with `start()`, `stop()`, `get_frame()` |

### Future Extension Roadmap

- 📊 **Analytics**: heatmap generation, path analysis, dwell time
- 🧠 **AI Extensions**: face recognition (opt-in), license plate recognition, fight/fall detection
- ☁️ **Infrastructure**: multi-site federation, cloud backup, edge-cloud split inference
- 🔗 **Integrations**: MQTT for IoT/smart home, IFTTT webhooks, alarm system integration

---

## ⚠️ Risk Management

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| No GPU | Medium | High | ONNX CPU fallback; YOLOv8n; shared GPU server or Colab for training |
| Thermal camera unavailable | High | Medium | FLIR ADAS dataset replayed as mock RTSP streams |
| RGB-T alignment issues | Medium | Medium | Start with late fusion (misalignment-tolerant); pre-aligned datasets (KAIST, LLVIP) |
| Latency > 500ms | Medium | High | Profile each stage; frame skipping; reduce input resolution; go2rtc WebRTC |
| DB bottleneck at scale | Low | High | TimescaleDB partitioning; batch inserts; configurable detection logging frequency |
| Team coordination failures | Medium | Medium | OpenAPI contracts in Week 1; weekly integration builds; shared Docker Compose |
| Scope creep | High | Medium | Strict phase gates; deferred backlog managed in GitHub Projects |

---

## 📁 Deliverables

1. ✅ **Source code repository** — Docker Compose deployment, CI/CD pipeline, this README
2. ✅ **Working demo** — Live multi-camera dashboard with real-time detection and event alerts (minimum 2 cameras: RGB + thermal replay)
3. ✅ **Model evaluation report** — mAP/LAMR tables for RGB-only, thermal-only, and fusion with day/night breakdowns
4. ✅ **API documentation** — Auto-generated OpenAPI spec with example requests/responses
5. ✅ **System architecture document** — Updated diagrams, data flow descriptions, deployment guide
6. ✅ **User guide** — Camera setup, zone configuration, event monitoring, system administration
7. ✅ **Ethics & privacy assessment** — Data handling practices, retention policies, privacy documentation

---

## 📚 Reference Projects

| Project | Key Takeaway |
|---|---|
| [Frigate NVR](https://frigate.video) | Event pipeline architecture, hardware acceleration, zone-based detection |
| [Kerberos.io](https://kerberos.io) | Microservice-per-camera pattern, Kubernetes-ready packaging |
| [SharpAI DeepCamera](https://github.com/SharpAI) | Person Re-ID pipeline, vector DB integration |
| [ZoneMinder](https://zoneminder.com) | Camera management patterns, storage/retention policies |
| [Viseron](https://viseron.netlify.app) | Multi-backend inference abstraction, hardware-agnostic AI |
| [DeepDetect](https://www.deepdetect.com) | REST API inference server, multi-framework (ONNX, TensorRT, PyTorch) |

---


<div align="center">

**Version 1.0 March 2026**

*Produced as a comprehensive engineering guide.*

*Bridging practical software engineering with computer vision research.*

</div>
