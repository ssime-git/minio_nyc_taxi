FROM python:3.9-slim AS base

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster package installation
RUN pip install --no-cache-dir uv

# Copy setup.py for local package installation
COPY setup.py /app/

# Copy source code
COPY src/ /app/src/

# Set Python path
ENV PYTHONPATH=/app

# Storage Manager Stage
FROM base AS storage-manager
COPY requirements/storage-manager-requirements.txt /app/requirements.txt
RUN uv pip install --system --no-cache-dir -r requirements.txt && uv pip install --system -e .
CMD ["python", "/app/src/storage_manager/storage_manager_fastapi.py"]

# Monitoring Stage
FROM base AS monitoring
COPY requirements/monitoring-requirements.txt /app/requirements.txt
RUN uv pip install --system --no-cache-dir -r requirements.txt && uv pip install --system -e .
RUN mkdir -p /app/monitoring/logs
CMD ["python", "-u", "/app/src/monitoring/audit.py"]

# Data Service Stage
FROM base AS data-service
COPY requirements/data-service-requirements.txt /app/requirements.txt
RUN uv pip install --system --no-cache-dir -r requirements.txt && uv pip install --system -e .
CMD ["python", "/app/src/data/data_service_fastapi.py"]

# Training Service Stage
FROM base AS training-service
COPY requirements/training-service-requirements.txt /app/requirements.txt
RUN uv pip install --system --no-cache-dir -r requirements.txt && uv pip install --system -e .
CMD ["python", "/app/src/models/train_model_fastapi.py"]

# Orchestrator Stage
FROM base AS orchestrator
COPY requirements/orchestrator-requirements.txt /app/requirements.txt
RUN uv pip install --system --no-cache-dir -r requirements.txt && uv pip install --system -e .
CMD ["python", "/app/src/orchestrator/orchestrator_api.py"]
