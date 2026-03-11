  
**AI-Powered Multi-Modal**

**Video Surveillance Platform**

RGB / IR / Thermal Fusion

Design & Implementation Report

Comprehensive Engineering Guide for Student Teams

Version 1.0 — March 2026

# **Table of Contents**

# **1\. Executive Summary**

This report presents the full design and implementation blueprint for a multi-modal AI video surveillance web application supporting RGB, near-infrared (NIR), and long-wave infrared (LWIR/thermal) camera feeds. The system targets real-time object detection with bounding-box annotations, multi-frame event detection (intrusion, loitering, abandoned objects), and persistent data historization in PostgreSQL. The architecture is modular and microservice-oriented so that students can work on independent modules in parallel while producing a cohesive, extensible platform.

The document consolidates the existing RGB prototype specification with the PFE thermal/IR research plan, filling the gaps between them and producing a unified engineering roadmap. It covers system architecture, technology selection, database design, AI pipeline specifics for both RGB-only and RGB-T fusion, frontend design, deployment strategy, testing plan, and a phased schedule optimized for a 12–14 week student project.

Key design principles include separation of concerns through microservices, standardized interfaces (REST \+ WebSocket \+ gRPC), container-first deployment with Docker Compose, and a plugin architecture for adding new detection models or modalities without touching core plumbing.

# **2\. Project Scope & Objectives**

## **2.1 Scope Definition**

The platform must support three operational modes: (1) RGB-only surveillance using standard IP cameras, (2) Thermal-only surveillance using LWIR cameras, and (3) RGB-T fusion for environments requiring robust day/night detection. Each mode should be selectable per camera or camera group, and the system must handle mixed fleets where some cameras are RGB and others are thermal or dual-sensor.

## **2.2 Primary Objectives**

* Real-time multi-camera monitoring with \< 500 ms end-to-end latency from capture to display

* AI-based object detection supporting at minimum person and vehicle classes, extensible to additional classes

* Multi-modal support: RGB, thermal (LWIR 8–14 µm), and synchronized RGB-T fusion

* Event detection engine for intrusion, loitering, line-crossing, and abandoned object scenarios

* Full data historization: per-frame detection attributes, event logs, and key-frame snapshots in PostgreSQL

* Modular, containerized architecture allowing independent development 

* Standards-based camera integration via ONVIF discovery and RTSP streaming

## **2.3 Out of Scope (Phase 1\)**

* Audio analytics and gunshot detection

* LiDAR or radar fusion

* Cloud-native multi-site federation (single-site focus)

* Mobile-native applications (responsive web only)

# **3\. Reference Projects & Inspiration**

Studying existing open-source surveillance systems accelerates development and reveals proven patterns. The following projects are recommended as architectural and functional references for the student teams.

| Project | Key Takeaway | Relevance |
| :---- | :---- | :---- |
| Frigate NVR | Real-time AI detection with Google Coral TPU offload, MQTT event bus, Home Assistant integration | Event pipeline architecture, hardware acceleration patterns, zone-based detection |
| Kerberos.io Agent | Lightweight, containerized, single-camera agent that scales via Kubernetes; open-source MIT | Microservice-per-camera pattern, cloud-optional design, Kubernetes-ready packaging |
| SharpAI DeepCamera | YOLO detection \+ ReID person tracking, Milvus vector DB for self-supervised learning | Person re-identification pipeline, vector DB integration for feature storage |
| ZoneMinder | Mature NVR with extensive camera support, zone-based motion detection, web interface | Camera management patterns, storage/retention policy implementation |
| Viseron | Docker-based NVR with YOLO support, face recognition, CUDA/Coral/Jetson acceleration | Multi-backend inference abstraction, hardware-agnostic AI pipeline |
| DeepDetect | REST API-based inference server supporting multiple ML frameworks | Model serving pattern via REST, multi-framework support (ONNX, TensorRT, PyTorch) |

## **3.1 RGB-T Fusion Research References**

For the thermal fusion component, the following academic projects and repositories provide direct code and methodology references that students should study:

* El Ahmar et al. — Enhanced Thermal-RGB Fusion (CVPR 2023 Workshop): sigmoid-gated early fusion achieving \+9% mAP improvement with negligible latency overhead. Code: github.com/wassimea/rgb-thermalfusion

* MRD-YOLO (2024) — YOLO-style multispectral detector with interaction-based fusion, benchmarked on FLIR Aligned and M3FD datasets

* MDQF (2025) — Modality-Decoupled Query Fusion using dual DETR branches with cross-modal query exchange, robust to single-modality degradation

* IAF-RCNN — Illumination-Aware Faster R-CNN with gated RGB/IR weighting, a canonical baseline to reproduce

* CRT-YOLO (2025) — Thermal-only detector with centralized feature regulation and efficient multi-scale attention

# **4\. System Architecture**

## **4.1 High-Level Architecture Overview**

The system follows a microservice architecture with five core services, a message broker, and shared storage. Each service is independently deployable as a Docker container and communicates through well-defined interfaces. This decomposition maps directly to student, allowing parallel development with minimal merge conflicts.

| Service | Responsibility | Technology | Team |
| :---- | :---- | :---- | :---- |
| Camera Gateway | RTSP ingestion, ONVIF discovery, frame extraction, multi-modal stream routing | Python, OpenCV, GStreamer | Team |
| AI Inference Engine | Object detection (RGB, thermal, fusion), model serving, batch/stream processing | Python, ONNX Runtime / TensorRT, Triton | Team |
| Event Processor | Object tracking (DeepSORT/ByteTrack), event logic (intrusion, loitering, line-crossing) | Python, NumPy, Shapely | Team |
| Backend API | REST API, WebSocket server, auth (JWT), business logic, DB access | Python, FastAPI, SQLAlchemy, Socket.io | Team |
| Frontend Dashboard | Multi-camera grid, live view, event timeline, admin panels, annotation overlay | React.js, TypeScript, Tailwind CSS | Team |
| Message Broker | Async communication between services, frame queuing, event pub/sub | Redis Streams or RabbitMQ | Shared infra |

## **4.2 Data Flow Pipeline**

The end-to-end data flow is designed as a pipeline with clear stage boundaries. Each stage consumes from an input queue and publishes to an output queue, enabling independent scaling and fault isolation.

1. Camera Gateway captures RTSP frames at configurable FPS (default 15 fps for RGB, 10 fps for thermal). Frames are decoded, timestamped, and published to the frame queue with metadata (camera\_id, modality, resolution).

2. AI Inference Engine consumes frames from the queue, routes them to the appropriate model (RGB-only YOLO, thermal-only, or RGB-T fusion), runs inference, and publishes detection results (bounding boxes, classes, confidence scores) to the detection queue.

3. Event Processor consumes detections, maintains per-camera tracking state (DeepSORT), evaluates event rules against configured zones/lines, and publishes confirmed events to the event queue.

4. Backend API persists detections and events to PostgreSQL, forwards real-time updates to connected frontend clients via WebSocket, and serves historical data via REST.

5. Frontend Dashboard renders live annotated video, event notifications, and historical analytics.

## **4.3 Inter-Service Communication**

Three communication patterns are used, each chosen for its strengths in the relevant context:

* Redis Streams for frame and detection data (high-throughput, ordered, consumer groups for load balancing)

* WebSocket (Socket.io) for frontend real-time updates (bidirectional, event-driven)

* REST API for configuration, historical queries, and admin operations (request-response, cacheable)

For the AI inference path specifically, if GPU inference needs to be centralized, gRPC to a Triton Inference Server can replace the Redis-based pattern, providing native support for model versioning and dynamic batching.

## **4.4 Multi-Modal Stream Routing**

A key architectural challenge is routing frames from different modalities to the correct inference pipeline. The Camera Gateway tags each frame with its modality type. The AI Inference Engine uses a router component that inspects this tag and dispatches accordingly:

* modality=rgb → RGB detection pipeline (YOLOv8/v11)

* modality=thermal → Thermal-only pipeline (CRT-YOLO or fine-tuned YOLO on FLIR)

* modality=rgb\_t → Fusion pipeline (two-stream backbone with illumination-aware gating)

For synchronized RGB-T cameras, the gateway performs temporal alignment by matching frames within a configurable tolerance window (default 50 ms) before publishing paired frames.

# **5\. Database Design**

## **5.1 Entity-Relationship Model**

PostgreSQL is the primary data store, chosen for its robust JSON support (JSONB), excellent indexing, and optional TimescaleDB extension for time-series optimization at scale. The schema follows the third normal form with strategic denormalization for query performance on hot paths.

### **5.1.1 Core Tables**

| Table | Key Columns | Purpose |
| :---- | :---- | :---- |
| cameras | id, name, ip, port, rtsp\_url, credentials (encrypted), modality, group\_id, config\_json, status, last\_seen | Camera registry and configuration |
| camera\_groups | id, name, description, location | Logical grouping (zones, buildings) |
| frames | id, camera\_id, timestamp, frame\_number, modality, resolution, storage\_path | Frame metadata (actual images on disk/S3) |
| detections | id, frame\_id, camera\_id, timestamp, object\_class, bbox (x1,y1,x2,y2), confidence, track\_id, features\_json | Per-frame detection attributes |
| tracks | id, camera\_id, object\_class, first\_seen, last\_seen, track\_length, avg\_confidence | Aggregated tracking state |
| events | id, event\_type, camera\_id, track\_id, start\_time, end\_time, severity, zone\_id, event\_data (JSONB), status, snapshot\_refs | Multi-frame events |
| zones | id, camera\_id, name, polygon (JSONB), zone\_type (exclusion/counting/alert), config\_json | Virtual detection zones per camera |
| users | id, username, email, password\_hash, role, last\_login | Authentication and authorization |
| audit\_log | id, user\_id, action, resource, timestamp, details\_json | System audit trail |

### **5.1.2 Indexing Strategy**

* B-tree indexes on (camera\_id, timestamp) for all time-series tables (detections, events, frames)

* GIN index on event\_data and features\_json JSONB columns for flexible querying

* Partial index on events WHERE status \= 'new' for fast unacknowledged event retrieval

* Composite index on detections(camera\_id, object\_class, timestamp) for analytics queries

### **5.1.3 Data Retention & Partitioning**

The detections table is the highest-volume table (potentially millions of rows per day with 16+ cameras). Use PostgreSQL declarative partitioning by time range (daily or weekly partitions). A background job drops partitions older than the configured retention period (7d, 30d, or 1y). Event snapshots are stored on the filesystem under a structured path: /data/snapshots/{camera\_id}/{YYYY-MM-DD}/{event\_id}\_{timestamp}.jpg, with only the path reference stored in the database.

# **6\. AI Inference Pipeline**

## **6.1 Model Selection Strategy**

The model selection balances accuracy, inference speed, and student feasibility. The recommended approach is a phased rollout: start with a pre-trained RGB model, then add thermal fine-tuning, and finally implement fusion.

| Phase | Model | Modality | Dataset | Target Metric | Week |
| :---- | :---- | :---- | :---- | :---- | :---- |
| Phase 1 | YOLOv8n/s (pre-trained COCO) | RGB only | COCO (pre-trained) | mAP@50 \> 0.45 | Weeks 1–3 |
| Phase 2 | YOLOv8s (fine-tuned) | Thermal only | FLIR ADAS | mAP per class (day/night) | Weeks 4–6 |
| Phase 3a | Two-stream YOLOv8 | RGB-T late fusion | KAIST, LLVIP | LAMR, mAP@50 | Weeks 7–9 |
| Phase 3b | Gated fusion (IAF-style) | RGB-T with illumination gate | KAIST, LLVIP | \+5% over concat | Weeks 9–10 |
| Phase 4 | Distilled thermal-only | Thermal (night deploy) | Knowledge distillation | \< 5% drop vs fusion | Week 11 |

## **6.2 RGB Detection Pipeline**

The RGB pipeline uses YOLOv8 (Ultralytics) exported to ONNX for production inference. The preprocessing chain is: resize to model input (640x640), normalize pixel values to \[0,1\], and batch if GPU memory allows. Post-processing applies non-maximum suppression (NMS) with IoU threshold 0.45 and confidence threshold 0.25 (configurable per deployment).

For serving, two options are recommended depending on team capacity:

* Simple path: Direct ONNX Runtime inference in Python, suitable for 1–4 cameras on a single GPU

* Scalable path: NVIDIA Triton Inference Server with dynamic batching, model versioning, and gRPC endpoints, suitable for 8–16+ cameras

## **6.3 Thermal Detection Pipeline**

Thermal images require specific preprocessing. Raw 14-bit radiometric data from LWIR cameras should be mapped to 8-bit using percentile clipping (2nd–98th percentile) or CLAHE (Contrast Limited Adaptive Histogram Equalization). The 8-bit single-channel image is then stacked to 3 channels (grayscale-to-RGB) for compatibility with standard backbones pre-trained on ImageNet/COCO.

Fine-tuning YOLOv8s on the FLIR ADAS dataset is the recommended baseline. Key training considerations include:

* Separate day/night evaluation splits to measure per-condition performance

* Augmentations: random horizontal flip, mosaic, and thermal-specific noise injection

* Learning rate: start at 0.01 with cosine annealing over 100 epochs

* Class mapping: merge FLIR’s fine-grained classes to match the target schema (person, vehicle, cyclist, animal)

## **6.4 RGB-T Fusion Architecture**

The recommended fusion approach follows a progressive complexity path that aligns with the PFE work plan:

### **6.4.1 Late Fusion Baseline**

Two independent backbones (e.g., YOLOv8 CSPDarknet) process RGB and thermal streams separately. Feature maps from the neck (FPN/PAN) are concatenated along the channel dimension, followed by a 1x1 convolution to reduce dimensionality, then fed to the shared detection head. This is the simplest fusion and serves as the baseline.

### **6.4.2 Illumination-Aware Gating**

Building on the IAF-RCNN concept: a lightweight MLP takes the average intensity of the RGB image (or a learned exposure proxy) as input and outputs a scalar gate α in \[0,1\]. Feature maps are fused as α·F\_rgb \+ (1−α)·F\_thermal. At night, α approaches 0, automatically relying on thermal features. This adds negligible computation but significantly improves robustness to illumination changes.

### **6.4.3 Cross-Modal Attention (Advanced)**

For sufficient GPU resources, a cross-attention mechanism (inspired by MDQF) can be inserted between the two backbone branches at each FPN level. Each modality’s queries attend to the other modality’s keys/values, enabling selective feature exchange. This yields the highest accuracy but requires careful tuning to avoid overfitting on small datasets.

## **6.5 Sensor Alignment Considerations**

RGB-T fusion requires spatial alignment of the two modalities. For dual-sensor cameras with factory calibration, the homography is typically provided. For separate cameras, a stereo calibration procedure using a heated checkerboard (visible in both RGB and thermal) produces the required transformation matrix. Late and mid-fusion approaches are more tolerant of minor misalignment than early fusion, which is why late fusion is recommended as the starting point.

# **7\. Event Detection Engine**

## **7.1 Object Tracking**

The event engine sits downstream of the detection pipeline and requires consistent object identities across frames. Two tracker options are recommended:

* ByteTrack: lightweight, association-based tracker that handles low-confidence detections well; recommended for most deployments

* DeepSORT: adds a Re-ID feature extractor for more robust identity maintenance across occlusions; heavier but better for crowded scenes

The tracker maintains a per-camera state dictionary mapping track IDs to trajectory histories (list of centroids \+ timestamps). Tracks are considered lost after N frames without association (configurable, default 30 frames).

## **7.2 Event Types & Detection Logic**

| Event Type | Trigger Logic | Required Config | Output Data |
| :---- | :---- | :---- | :---- |
| Intrusion | Track centroid enters exclusion zone polygon (point-in-polygon test using Shapely) | Zone polygon, dwell threshold (e.g., 2s) | track\_id, zone\_id, entry\_time, duration |
| Loitering | Track remains within a zone for \> T seconds without significant displacement | Zone polygon, time threshold, displacement threshold | track\_id, zone\_id, loiter\_duration, heatmap |
| Line Crossing | Track trajectory crosses a virtual line (segment intersection test) | Line coordinates, direction (A→B, B→A, both) | track\_id, line\_id, direction, crossing\_time |
| Abandoned Object | Static detection (non-person) persists for \> T seconds without associated moving track | Time threshold, min object area | bbox, duration, snapshot |
| Speed Anomaly | Track displacement/time exceeds threshold (requires calibrated pixel-to-meter mapping) | Speed threshold, calibration matrix | track\_id, speed\_estimate, trajectory |

## **7.3 Zone & Line Configuration**

Zones and lines are drawn by operators in the frontend using a canvas overlay on the camera view. The polygon/line coordinates are stored as JSONB arrays in the zones table, normalized to \[0,1\] relative coordinates for resolution independence. The event processor loads zone configurations at startup and reloads on change via a configuration change WebSocket event.

# **8\. Camera Gateway Service**

## **8.1 RTSP Ingestion**

Each camera connection runs in its own thread/asyncio task. OpenCV’s VideoCapture with the GStreamer backend is preferred over FFmpeg for lower latency. The pipeline string follows the pattern: rtspsrc location=\<url\> \! rtph264depay \! h264parse \! avdec\_h264 \! videoconvert \! appsink. For thermal cameras using proprietary SDKs (e.g., FLIR Spinnaker, Seek Thermal SDK), a thin adapter wraps the SDK and produces frames in the same normalized format.

## **8.2 ONVIF Discovery**

The python-onvif-zeep library provides ONVIF WS-Discovery to automatically find cameras on the local subnet. The discovery service runs periodically (every 60s) and compares found devices against the camera registry. New cameras are added with status ‘discovered’ pending operator confirmation. ONVIF also provides the GetStreamUri call to automatically retrieve RTSP URLs without manual configuration.

## **8.3 Health Monitoring**

Each camera connection publishes heartbeat metrics (frame rate, decode errors, connection status) to Redis. The backend API exposes a /cameras/health endpoint that aggregates these metrics. Cameras with no heartbeat for \> 30s are flagged offline, and a WebSocket event triggers a dashboard notification.

# **9\. Frontend Architecture**

## **9.1 Technology Stack**

The frontend uses React.js with TypeScript, Tailwind CSS for styling, and the following key libraries:

* Socket.io-client for real-time WebSocket communication

* React Query (TanStack Query) for REST API data fetching with caching

* Konva.js or Fabric.js for canvas-based zone drawing and annotation overlay

* HLS.js or JSMpeg for low-latency video rendering in the browser

* Zustand for lightweight global state management

* Recharts for analytics dashboards and detection statistics

## **9.2 Video Rendering Strategy**

Direct RTSP-to-browser is not possible. Two viable approaches, in order of recommendation:

* WebRTC via go2rtc: The go2rtc project converts RTSP to WebRTC with sub-200ms latency. The camera gateway runs go2rtc as a sidecar, and the frontend connects via the WebRTC API. This is the approach used by Frigate and DeepCamera.

* MJPEG over WebSocket: The backend encodes detection-annotated frames as JPEG and streams them over WebSocket. Simpler to implement but higher bandwidth. Suitable for 1–4 cameras.

For the detection overlay, bounding boxes and labels are rendered on an HTML5 Canvas layer positioned over the video element, rather than burned into the video stream. This allows toggling annotations without re-encoding.

## **9.3 Key UI Components**

| Component | Description | Priority |
| :---- | :---- | :---- |
| MultiCameraGrid | Responsive grid layout supporting 1x1, 2x2, 3x3, 4x4 configurations with drag-to-rearrange | High |
| CameraFullView | Full-screen single camera with PTZ controls (if supported), live detection overlay, and info panel | High |
| EventTimeline | Chronological feed of events with severity badges, filterable by type/camera/time range | High |
| ZoneEditor | Canvas overlay for drawing polygons (exclusion zones) and lines (counting lines) on camera views | High |
| AnalyticsDashboard | Charts showing detection counts by class/time, event frequency, camera uptime metrics | Medium |
| CameraManager | CRUD interface for cameras with ONVIF discovery button, connection test, and configuration forms | High |
| UserAdmin | User management with role assignment (Admin, Operator, Viewer), JWT session display | Medium |
| SystemConfig | Global settings: retention policies, detection thresholds, notification preferences | Medium |

# **10\. Backend API Design**

## **10.1 API Structure**

The backend API is built with FastAPI for its async support, automatic OpenAPI documentation, and native WebSocket handling. The API follows RESTful conventions with versioned endpoints under /api/v1/.

### **10.1.1 Core Endpoints**

| Method | Endpoint | Description |
| :---- | :---- | :---- |
| GET/POST | /api/v1/cameras | List all cameras / Register new camera |
| GET/PUT/DELETE | /api/v1/cameras/{id} | Get / Update / Remove camera |
| POST | /api/v1/cameras/discover | Trigger ONVIF network discovery |
| GET | /api/v1/cameras/{id}/health | Camera health metrics |
| GET | /api/v1/detections | Query detections with filters (camera, class, time range, pagination) |
| GET | /api/v1/events | Query events with filters |
| PUT | /api/v1/events/{id}/status | Update event status (new/viewed/resolved) |
| GET/POST | /api/v1/zones | List / Create detection zones |
| POST | /api/v1/auth/login | JWT authentication |
| GET | /api/v1/analytics/summary | Aggregated statistics for dashboard |
| WS | /ws/live | WebSocket for real-time frames \+ detections \+ events |

## **10.2 Authentication & Authorization**

JWT-based authentication with three roles: Admin (full access), Operator (camera management \+ event handling), and Viewer (read-only monitoring). Tokens expire after 8 hours with refresh token support. Passwords are hashed with bcrypt. All endpoints except /auth/login require a valid JWT in the Authorization header.

## **10.3 WebSocket Protocol**

The WebSocket connection at /ws/live uses Socket.io rooms for per-camera subscriptions. Event types include:

* frame\_update: base64-encoded annotated frame \+ detection metadata (for MJPEG mode)

* detection: lightweight detection JSON without frame data (for WebRTC mode where video is separate)

* event\_alert: new event notification with type, severity, camera, and thumbnail

* camera\_status: online/offline/error state changes

* config\_change: zone or system configuration updates requiring client refresh

# **11\. Deployment & DevOps**

## **11.1 Container Architecture**

All services are containerized with Docker and orchestrated via Docker Compose for development and single-node deployment. The docker-compose.yml defines the following services:

| Container | Base Image | Ports | Volumes |
| :---- | :---- | :---- | :---- |
| camera-gateway | python:3.11-slim \+ OpenCV | Internal only | /data/frames |
| ai-engine | nvcr.io/nvidia/tritonserver or python:3.11 \+ onnxruntime-gpu | 8001 (gRPC) | /models |
| event-processor | python:3.11-slim | Internal only | — |
| backend-api | python:3.11-slim \+ FastAPI | 8000 (HTTP), 8080 (WS) | — |
| frontend | node:20-alpine (build) → nginx:alpine (serve) | 80/443 | — |
| postgres | timescale/timescaledb:latest-pg16 | 5432 | /data/postgres |
| redis | redis:7-alpine | 6379 | — |
| go2rtc | alexxit/go2rtc | 1984 (API), 8555 (WebRTC) | — |

## **11.2 Development Environment**

Each student should be able to run the full stack locally with docker compose up. A .env.example file documents all required environment variables. For students without a GPU, the AI engine falls back to CPU-based ONNX Runtime (slower but functional). A mock-camera service generates synthetic RTSP streams from video files for testing without physical cameras.

## **11.3 CI/CD Pipeline**

* Git branching: main (stable), develop (integration), feature/\* (per-task branches)

* Pre-commit hooks: Black \+ isort (Python), ESLint \+ Prettier (TypeScript)

* GitHub Actions: lint → unit tests → build Docker images → integration tests

* Container registry: GitHub Container Registry (ghcr.io) for team image sharing

## **11.4 Monitoring & Observability**

* Prometheus metrics exposed by each Python service via prometheus\_client

* Grafana dashboards for inference latency, frame throughput, queue depth, and camera uptime

* Structured logging with Python’s structlog in JSON format, collected by Docker’s logging driver

# **12\. Security & Privacy**

## **12.1 Network Security**

* All RTSP streams should use RTSPS (RTSP over TLS) where camera firmware supports it

* Inter-service communication stays on a Docker internal network, not exposed to the host

* The frontend is served over HTTPS via an nginx reverse proxy with Let’s Encrypt certificates

* Camera credentials are encrypted at rest in PostgreSQL using Fernet symmetric encryption

## **12.2 Application Security**

* JWT tokens with short expiry (8h) and HTTP-only secure cookies for refresh tokens

* Role-based access control enforced at the API middleware level

* Input validation via Pydantic models on all API endpoints

* Rate limiting on authentication endpoints to prevent brute force

* CORS configuration restricted to known frontend origins

## **12.3 Privacy & Ethics**

Video surveillance systems carry significant privacy implications. The following measures should be documented and implemented:

* Data minimization: store detection metadata rather than full video where possible

* Configurable retention periods with automatic deletion of expired data

* Audit logging of all user access to video feeds and event data

* Anonymization option: optional face blurring for stored snapshots in non-security contexts

* Clear signage requirements documentation for deployment sites

* 18-07law/data protection compliance documentation template for National deployments

# **13\. Testing Strategy**

## **13.1 Testing Pyramid**

| Level | Scope | Tools | Coverage Target |
| :---- | :---- | :---- | :---- |
| Unit Tests | Individual functions: preprocessing, NMS, zone geometry, JWT validation | pytest, Jest/Vitest | \> 70% for core logic |
| Integration Tests | Service-to-service: API → DB, Gateway → Redis, Event Processor → API | pytest \+ testcontainers, Docker Compose | All critical data paths |
| End-to-End Tests | Full pipeline: synthetic camera → detection → event → frontend notification | Playwright (frontend), custom Python scripts | Top 5 user scenarios |
| Model Tests | Detection accuracy on held-out test sets, regression tests on known hard cases | Ultralytics val, custom eval scripts | mAP within 2% of baseline |
| Performance Tests | Latency benchmarks: frame-to-display \< 500ms, inference \< 100ms per frame | locust (API), custom timing | All ENF criteria |

## **13.2 Test Data Strategy**

A mock camera service replays pre-recorded video files as RTSP streams, enabling fully offline testing. For thermal testing, sample sequences from the FLIR ADAS and LLVIP datasets are converted to RTSP-compatible formats. The test suite includes labeled ground truth for validation: known detection counts per scene, known event triggers per scenario.

# **14\. Recommended Datasets**

The following datasets are recommended for training, validation, and benchmarking. Students should prioritize FLIR ADAS and KAIST for the core work, adding others as time permits.

| Dataset | Modality | Size | Classes | Use Case |
| :---- | :---- | :---- | :---- | :---- |
| FLIR ADAS Thermal | Thermal (8–14µm) | \~26K images | Person, car, bicycle, dog, other | Thermal-only baseline training |
| KAIST Multispectral | RGB \+ Thermal (paired) | 95K pairs | Pedestrian | RGB-T fusion training & LAMR benchmark |
| LLVIP | RGB \+ IR (low-light, paired) | 15K pairs | Pedestrian | Night-time fusion validation |
| M3FD | RGB \+ Thermal (multi-scene) | 4.2K pairs | Person, car, bus, motorcycle, truck, lamp | Cross-scenario fusion evaluation |
| DroneVehicle | RGB \+ IR (aerial) | 56.8K images | Vehicle classes (rotated boxes) | Aerial/drone extension (optional) |
| COCO 2017 | RGB | 118K train, 5K val | 80 classes | RGB pre-training and general benchmarks |

# **15\. Optimized Project Schedule (14 Weeks)**

The schedule is designed for parallel workstreams across student teams, with integration checkpoints every two weeks. Critical path items are marked. The schedule assumes 5–6 students working in parallel teams.

| Week | Team A (Gateway) | Team B (AI) | Team C (Events) | Team D (API) | Team E (Frontend) | Milestone |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| 1 | Env setup, Docker Compose skeleton | Env setup, YOLO baseline on COCO | Study ByteTrack/DeepSORT | FastAPI scaffold, DB schema | React scaffold, component stubs | Dev environment running |
| 2 | RTSP ingestion (OpenCV), frame publish to Redis | YOLO ONNX export, inference service | Tracker integration with mock detections | CRUD cameras, auth (JWT) | Camera grid layout, WebSocket client | Frame pipeline E2E |
| 3 | ONVIF discovery, camera health monitoring | Batch inference, GPU optimization | Intrusion zone logic (Shapely) | Detections & events REST endpoints | Live video (MJPEG/WebRTC) | Live detection display |
| 4 | Thermal camera adapter (FLIR SDK) | Fine-tune YOLO on FLIR ADAS | Line-crossing detection | Zone CRUD, WebSocket events | Zone drawing canvas (Konva) | Thermal support demo |
| 5 | RGB-T frame alignment & sync | Thermal eval (day/night split) | Loitering detection logic | Event status workflow | Event timeline component |  |
| 6 | go2rtc WebRTC integration | Late fusion baseline (KAIST) | Abandoned object detection | Analytics aggregation queries | Analytics dashboard (Recharts) | Mid-project review |
| 7 | Multi-camera stress test | Fusion eval on KAIST/LLVIP | Event rule configuration API | Data export (CSV/JSON) | User admin panel |  |
| 8 | Performance tuning, reconnection logic | Illumination-aware gating | Tracker parameter tuning | Retention policy automation | Camera config UI | Fusion model integrated |
| 9 | Camera group management | Fusion ablations & analysis | Cross-dataset event testing | Load testing (Locust) | System settings UI |  |
| 10 | Integration testing | Model distillation (optional) | End-to-end event testing | Security hardening | E2E test with Playwright | Feature freeze |
| 11–12 | Bug fixes, documentation | Final model packaging, ONNX export | Bug fixes, edge case handling | API documentation (OpenAPI) | UI polish, responsive design | Testing & stabilization |
| 13–14 | Deployment guide | Model evaluation report | Event detection accuracy report | System documentation | User guide | Final demo & report |

# **16\. Modularity & Extension Points**

## **16.1 Plugin Architecture**

The system is designed with explicit extension points to support future enhancements without modifying core services:

### **16.1.1 Model Plugins**

New detection models are registered in a model\_registry.yaml file that maps model names to their ONNX file path, input/output tensor specifications, preprocessing parameters, and class mappings. The AI engine loads models from this registry at startup. Adding a new model (e.g., a license plate reader) requires only: (1) export to ONNX, (2) add a registry entry, (3) configure which cameras use it.

### **16.1.2 Event Plugins**

New event types are implemented as Python classes inheriting from a BaseEventDetector abstract class with a process\_track(track, zones) method. The event processor dynamically loads all detector classes from an events/detectors/ directory. Adding a new event type (e.g., crowd density alert) requires creating a single Python file with the detector class.

### **16.1.3 Notification Plugins**

Notification channels (email, SMS, MQTT, webhook) are implemented as adapters behind a NotificationService interface. The configuration specifies which channels to activate per event severity level. Adding a new channel (e.g., Telegram bot) requires implementing a single send() method.

### **16.1.4 Camera Adapter Plugins**

Each camera type (RTSP/ONVIF, USB, thermal SDK, file replay) is implemented as a CameraAdapter class with start(), stop(), and get\_frame() methods. The gateway instantiates the appropriate adapter based on the camera’s registered type. This allows adding support for new camera SDKs without modifying the core gateway logic.

## **16.2 Future Extension Roadmap**

* Analytics extensions: heatmap generation, path analysis, dwell time analytics

* AI extensions: face recognition (opt-in), license plate recognition, action recognition (fight/fall detection)

* Infrastructure extensions: multi-site federation, cloud backup, edge-cloud split inference

* Integration extensions: MQTT for IoT/home automation, IFTTT/Zapier webhooks, alarm system integration

# **17\. Risk Management**

| Risk | Probability | Impact | Mitigation |
| :---- | :---- | :---- | :---- |
| No GPU available for students | Medium | High | Provide ONNX CPU fallback; use smaller models (YOLOv8n); offer shared GPU server or Google Colab for training |
| Thermal camera hardware unavailable | High | Medium | Use FLIR ADAS dataset replayed as mock RTSP streams; design thermal adapter interface against SDK docs |
| RGB-T alignment issues | Medium | Medium | Start with late fusion (misalignment-tolerant); document calibration procedure; provide pre-aligned datasets (KAIST, LLVIP) |
| Latency exceeds 500ms target | Medium | High | Profile each pipeline stage; use frame skipping; reduce model input resolution; deploy go2rtc for WebRTC |
| Database bottleneck at scale | Low | High | Enable TimescaleDB partitioning; batch inserts; configurable detection logging frequency (every Nth frame) |
| Team coordination failures | Medium | Medium | Define clear API contracts (OpenAPI specs) in week 1; weekly integration builds; shared Docker Compose |
| Scope creep from optional features | High | Medium | Strict phase gates; features beyond Phase 1 are explicitly deferred; backlog managed in GitHub Projects |

# **18\. Expected Deliverables**

1. Source code repository with Docker Compose deployment, CI/CD pipeline, and README with setup instructions

2. Working demo: live multi-camera dashboard with real-time detection and event alerts (minimum 2 cameras, mixed RGB \+ thermal replay)

3. Model evaluation report: mAP/LAMR tables for RGB-only, thermal-only, and fusion models with day/night breakdowns and qualitative failure analysis

4. API documentation: auto-generated OpenAPI spec with example requests/responses for all endpoints

5. System architecture document: updated diagrams reflecting actual implementation, data flow descriptions, deployment guide

6. User guide: operator-facing documentation covering camera setup, zone configuration, event monitoring, and system administration

7. Ethics and privacy assessment: documentation of data handling practices, retention policies, and privacy considerations

# **19\. Conclusion**

This report provides a comprehensive blueprint for building a production-grade, multi-modal AI video surveillance platform within a 14-week student project timeline. By leveraging a microservice architecture, containerized deployment, and a phased AI model development approach, the project is structured for parallel team execution while maintaining system coherence.

The key engineering decisions — Redis Streams for inter-service messaging, ONNX Runtime for portable model serving, WebRTC via go2rtc for low-latency display, PostgreSQL with TimescaleDB for scalable data historization, and a plugin architecture for extensibility — are all battle-tested patterns drawn from successful open-source projects like Frigate, Kerberos.io, and DeepCamera.

The thermal/IR fusion component builds directly on the PFE plan, providing students with a clear progression from pre-trained RGB baselines through thermal fine-tuning to illumination-aware fusion, each step producing publishable benchmark results. The modular design ensures that the thermal and fusion components enhance rather than complicate the core platform.

Students are encouraged to study the reference projects listed in Section 3, follow the phased schedule in Section 15, and use the extension points in Section 16 to explore advanced features within their areas of interest. The combination of practical engineering (building a real surveillance system) and research (for master projects, RGB-T fusion, model distillation) makes this project an excellent capstone experience bridging software engineering and computer vision.