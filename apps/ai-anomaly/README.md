# AI Anomaly Service

This directory contains a placeholder FastAPI service meant for anomaly detection and summarisation.

- **Health endpoint**: `/health` – returns a basic status.
- **Anomaly endpoint**: `/anomaly` – accepts a JSON payload and should return a detection score and optional explanation.

To run locally, install FastAPI and uvicorn:

```bash
pip install fastapi uvicorn
uvicorn main:app --reload --port 8001
```
