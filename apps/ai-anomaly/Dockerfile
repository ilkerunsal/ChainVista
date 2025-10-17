# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /app
# Install minimal deps (FastAPI, Uvicorn)
RUN pip install --no-cache-dir fastapi uvicorn pydantic

# Copy service code
COPY main.py /app/main.py

EXPOSE 8011
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8011"]
