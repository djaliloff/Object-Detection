# Multi-Modal Video Surveillance Platform - Development Guide

## Overview

This is a comprehensive AI-powered video surveillance platform supporting RGB, thermal, and RGB-T fusion cameras. The system is built with a microservice architecture for scalability and maintainability.

## Architecture

### Backend Services (Python)

1. **Backend API** (`backend-api/`) - FastAPI-based REST API and WebSocket server
2. **Camera Gateway** (`camera-gateway/`) - RTSP ingestion and camera management
3. **AI Inference Engine** (`ai-engine/`) - YOLO-based object detection and fusion
4. **Event Processor** (`event-processor/`) - Object tracking and event detection

### Frontend (React)

- **Frontend Dashboard** (`frontend/`) - React-based monitoring interface

### Infrastructure

- **PostgreSQL** - Primary database with TimescaleDB extension
- **Redis** - Message broker and caching
- **ONNX Runtime** - AI model inference

## Quick Start (Native Development)

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 16+ with TimescaleDB
- Redis 7+
- (Optional) NVIDIA GPU with CUDA 11.8+

### 1. Setup Environment

```bash
# Copy environment configuration
cp .env.example .env

# Edit .env with your settings
# - Database credentials
# - Redis connection
# - JWT secret key
# - Camera RTSP URLs
```

### 2. Setup Python Environment

```bash
# Activate virtual environment (if you have one)
# venv\Scripts\activate

# Install dependencies for each service
pip install -r backend-api/requirements.txt
pip install -r camera-gateway/requirements.txt
pip install -r ai-engine/requirements.txt
pip install -r event-processor/requirements.txt
```

### 3. Setup Database

```bash
# Start PostgreSQL and Redis services
# On Windows with chocolatey:
# postgresql-16 service start
# redis service start

# Create database
createdb surveillance

# Run database migrations (if using Alembic)
# cd backend-api
# alembic upgrade head
```

### 4. Setup Frontend

```bash
cd frontend
npm install
npm start
```

### 5. Start Services

Open separate terminals for each service:

```bash
# Terminal 1: Backend API
cd backend-api
python main.py

# Terminal 2: Camera Gateway
cd camera-gateway
python gateway.py

# Terminal 3: AI Inference Engine
cd ai-engine
python inference.py

# Terminal 4: Event Processor
cd event-processor
python processor.py
```

### 6. Access the Platform

- Frontend Dashboard: http://localhost:3000
- Backend API Docs: http://localhost:8000/docs
- WebSocket: ws://localhost:8080/ws/live

## Development Workflow

### Adding Cameras

1. **Via API:**
```bash
curl -X POST http://localhost:8000/api/v1/cameras \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Front Door",
    "ip": "192.168.1.100",
    "port": 554,
    "rtsp_url": "rtsp://192.168.1.100:554/stream",
    "username": "admin",
    "password": "password",
    "modality": "rgb"
  }'
```

2. **Via Frontend:** Navigate to Cameras page and add camera through UI

### Model Management

Models are configured in `ai-engine/model_registry.yaml`:

```yaml
models:
  rgb_yolov8n:
    name: "YOLOv8 Nano (RGB)"
    modality: "rgb"
    model_path: "../yolov8n.onnx"
    # ... configuration
```

### Zone Configuration

Create detection zones through the frontend:

1. Navigate to Cameras page
2. Select a camera
3. Click "Edit Zones"
4. Draw polygons on the camera view
5. Configure zone type (exclusion, alert, counting)

## Testing

### Unit Tests

```bash
# Backend tests
cd backend-api
pytest

# Frontend tests
cd frontend
npm test
```

### Integration Tests

```bash
# Test camera connection
curl http://localhost:8000/api/v1/cameras

# Test AI inference
# Send frame to Redis frame_queue and check detection_queue
```

### Mock Camera Testing

Enable mock cameras in `.env`:
```env
MOCK_CAMERAS=true
```

## Troubleshooting

### Common Issues

1. **Camera Connection Failed**
   - Check RTSP URL format
   - Verify camera credentials
   - Check network connectivity
   - Ensure camera supports RTSP

2. **AI Inference Not Working**
   - Verify ONNX model files exist
   - Check GPU/CPU configuration
   - Review model registry configuration

3. **WebSocket Connection Issues**
   - Check firewall settings
   - Verify WebSocket port (8080)
   - Check CORS configuration

4. **Database Connection Errors**
   - Verify PostgreSQL is running
   - Check database URL in .env
   - Ensure database exists

### Debug Mode

Enable debug logging in `.env`:
```env
DEBUG=true
LOG_LEVEL=DEBUG
```

### Performance Monitoring

- Access Prometheus metrics: http://localhost:9090
- Grafana dashboard: http://localhost:3000
- API health check: http://localhost:8000/health

## Model Training

### RGB Models

```bash
# Train YOLOv8 on COCO
yolo train model=yolov8n.pt data=coco.yaml epochs=100

# Export to ONNX
yolo export model=yolov8n.pt format=onnx
```

### Thermal Models

```bash
# Fine-tune on FLIR ADAS dataset
yolo train model=yolov8n.pt data=thermal.yaml epochs=100

# Export to ONNX
yolo export model=thermal_model.pt format=onnx
```

## Deployment

### Production Setup

1. **Environment Variables:**
   - Set strong JWT secret
   - Configure HTTPS
   - Set up proper database credentials

2. **Security:**
   - Enable HTTPS
   - Configure firewall
   - Use strong passwords
   - Enable audit logging

3. **Performance:**
   - Configure GPU acceleration
   - Optimize database indexes
   - Set up monitoring

### Scaling

- **Horizontal Scaling:** Deploy multiple instances of each service
- **Load Balancing:** Use nginx or cloud load balancer
- **Database:** Consider read replicas for analytics queries

## Contributing

### Code Style

- Python: Follow PEP 8, use Black formatter
- JavaScript: Use ESLint and Prettier
- React: Follow hooks patterns, use TypeScript for new components

### Git Workflow

1. Create feature branch from `develop`
2. Make changes with descriptive commits
3. Run tests
4. Submit pull request to `develop`
5. Merge to `main` for releases

### Development Tips

- Use the mock camera service for frontend development
- Test with different camera modalities
- Monitor Redis queue depths for performance
- Check WebSocket connection status in browser dev tools

## Support

For issues and questions:

1. Check this development guide
2. Review logs in each service
3. Check API documentation at `/docs`
4. Monitor system health via `/health` endpoint

## Architecture Diagram

```
Frontend (React) ←→ Backend API (FastAPI) ←→ PostgreSQL
                      ↓ WebSocket                    ↑
                      ↓                              ↑
                Event Processor ←→ AI Engine ←→ Camera Gateway
                      ↓                              ↓
                    Redis ←→ RTSP Cameras
```
