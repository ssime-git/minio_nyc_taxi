# NYC Taxi MLOps Pipeline

A comprehensive MLOps pipeline for processing, analyzing, and modeling NYC Taxi trip data using MinIO as the central storage hub.

## Project Overview

This project implements a complete MLOps pipeline for NYC Taxi data, featuring:

- Centralized object storage with MinIO
- Automated data ingestion and processing
- Feature engineering and dataset versioning
- Model training and experiment tracking with MLflow
- Pipeline orchestration and monitoring
- GDPR compliance and data anonymization

## Architecture

The system is built with a microservices architecture, with each component running as a separate containerized service:

### Architecture Diagram

```
+-----------------------------------------------------------+
|                                                           |
|  +-------------+      +--------------+     +----------+   |
|  |             |      |              |     |          |   |
|  |  Data       |----->|  Storage     |<--->|  MinIO   |   |
|  |  Service    |      |  Manager     |     |  Server  |   |
|  |             |      |              |     |          |   |
|  +-------------+      +--------------+     +----------+   |
|         |                    ^                  ^         |
|         v                    |                  |         |
|  +-------------+      +-------------+           |         |
|  |             |      |             |           |         |
|  | Feature     |----->| Training    |           |         |
|  | Engineering |      | Service     |-----------|         |
|  |             |      |             |                     |
|  +-------------+      +-------------+                     |
|         ^                    ^                            |
|         |                    |                            |
|         |              +----------+                       |
|         |              |          |                       |
|         |------------->| MLflow   |<------------------+   |
|                        | Server   |                   |   |
|                        |          |                   |   |
|                        +----------+                   |   |
|                              ^                        |   |
|                              |                        |   |
|  +-------------+      +-------------+      +----------+   |
|  |             |      |             |      |          |   |
|  | Monitoring  |<---->| Orchestrator|----->| Audit    |   |
|  | Service     |      |             |      | Logs     |   |
|  |             |      |             |      |          |   |
|  +-------------+      +-------------+      +----------+   |
|                                                           |
+-----------------------------------------------------------+
```

### Core Components

1. **MinIO Storage Manager**
   - Central storage hub for all data and artifacts
   - Bucket policy management and versioning
   - Lifecycle policies and audit logging
   - REST API for file operations

2. **Data Service**
   - Data ingestion from external sources
   - Data transformation and feature engineering
   - Dataset versioning and quality validation
   - GDPR compliance features

3. **Training Service**
   - Model training with versioned datasets
   - Read-only data access
   - MLflow integration for experiment tracking

4. **MLflow Tracking Server**
   - Experiment tracking and metrics
   - Model registry
   - MinIO artifact storage

5. **Orchestrator**
   - Pipeline coordination and job scheduling
   - Health checks and service monitoring
   - Error handling and retry mechanisms
   - Status tracking and reporting

6. **Monitoring System**
   - Pipeline stage tracking
   - Error logging and reporting
   - Performance metrics
   - Compliance checks
   - Audit trail generation

## Configuration

The project uses a centralized configuration approach with all settings defined in a global `config.py` file. This ensures consistency across services and simplifies maintenance.

Key configuration areas include:

- MinIO connection settings
- Service URLs and endpoints
- Shared volume paths
- Health check settings
- Data directories and bucket names

## Data Flow

1. **Data Ingestion**
   - Raw NYC Taxi data is downloaded from the official source
   - Files are stored in MinIO raw data bucket
   - Data quality checks are performed

2. **Feature Engineering**
   - Raw data is processed to create features
   - Engineered features include time-based features, distance calculations, and fare metrics
   - Processed data is stored in MinIO processed data bucket

3. **Train/Test Split**
   - Data is split into training and testing sets
   - Splits are stored in separate MinIO buckets

4. **Model Training**
   - Models are trained using the training dataset
   - Experiments are tracked in MLflow
   - Models are registered in the MLflow model registry

5. **Model Evaluation**
   - Models are evaluated using the test dataset
   - Performance metrics are logged to MLflow

## Security Features

- Service accounts with specific permissions
- RBAC implementation
- API authentication
- Audit logging for compliance

## Data Lifecycle Management

- Retention policies per bucket
- GDPR compliance features
- Data anonymization capabilities
- Comprehensive audit trails

## Getting Started

### Prerequisites

- Docker and Docker Compose
- MinIO client (mc) for manual storage operations
- Git for version control

### Reproducing the Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/minio_nyc_taxi.git
   cd minio_nyc_taxi
   ```

2. **Set up environment variables**:
   Create a `.env` file in the project root with the following variables:
   ```
   MINIO_ROOT_USER=minioadmin
   MINIO_ROOT_PASSWORD=minioadmin
   MINIO_BUCKET=nyc-taxi-data
   ```

3. **Build and start all services**:
   ```bash
   docker compose build
   docker compose up -d
   ```

4. **Verify all services are running**:
   ```bash
   docker compose ps
   ```
   
   You should see all services in the "Up" state:
   - minio_server
   - mlflow_server
   - storage_manager
   - monitoring
   - data_service
   - training_service
   - orchestrator

5. **Monitor the pipeline execution**:
   ```bash
   docker logs orchestrator -f
   ```

6. **Access service UIs**:
   - MinIO Console: http://localhost:9001 (login with MINIO_ROOT_USER/MINIO_ROOT_PASSWORD)
   - MLflow UI: http://localhost:5002

### Troubleshooting Common Issues

1. **Service health check failures**:
   - Check if all services are running: `docker compose ps`
   - Inspect service logs: `docker logs <service_name>`
   - Ensure correct hostnames in `config.py` (use container names with underscores, not hyphens)

2. **MinIO bucket creation issues**:
   - Verify MinIO credentials in `.env` file
   - Check MinIO logs: `docker logs minio_server`
   - Manually create buckets using MinIO console if needed

3. **Training service errors**:
   - Ensure DataAuditor initialization is correct in `train_model.py`
   - Verify training service URL in `config.py` matches container name in Docker Compose
   - Check training service logs: `docker logs training_service`

4. **Data download issues**:
   - Verify internet connectivity for downloading NYC Taxi data
   - Check data service logs: `docker logs data_service`
   - Manually download and place data files in MinIO if needed

## Service Endpoints

- **MinIO**: http://localhost:9000 (API), http://localhost:9001 (Console)
- **Data Service**: http://localhost:8000
- **Storage Manager**: http://localhost:8001
- **Training Service**: http://localhost:8002
- **MLflow**: http://localhost:5002
- **Monitoring**: http://localhost:8003

## Development

### Project Structure

```
minio_nyc_taxi/
├── src/
│   ├── config.py                  # Global configuration
│   ├── data/                      # Data service
│   │   └── data_service.py        # Data ingestion and processing
│   ├── storage_manager/           # Storage manager service
│   │   ├── manager.py             # MinIO operations
│   │   └── server.py              # REST API server
│   ├── models/                    # Training service
│   │   └── train_model.py         # Model training
│   ├── orchestrator/              # Pipeline orchestrator
│   │   └── main.py                # Main orchestration logic
│   └── monitoring/                # Monitoring system
│       └── audit.py               # Audit logging
├── tests/                         # Test suite
├── docker-compose.yml             # Service definitions
├── Dockerfile                     # Container build instructions
├── requirements/                  # Service-specific requirements
│   ├── data-service-requirements.txt
│   ├── monitoring-requirements.txt
│   ├── orchestrator-requirements.txt
│   ├── storage-manager-requirements.txt
│   └── training-service-requirements.txt
└── setup.py                       # Package setup
```

### Adding New Features

When adding new features:

1. Update the global configuration in `src/config.py` if needed
2. Implement the feature in the appropriate service
3. Update tests to cover the new functionality
4. Document the changes in this README

## Current Status and Next Steps

The pipeline is currently operational with the following features:

- Centralized configuration for all services
- Data ingestion and processing for NYC Taxi data
- Feature engineering and train/test splitting
- Basic model training with MLflow tracking
- Pipeline orchestration with health checks
- Monitoring and audit logging

Next steps for development:

1. Enhance model evaluation metrics
2. Implement automated retraining triggers
3. Add more sophisticated feature engineering
4. Expand GDPR compliance features
5. Implement CI/CD pipeline for automated testing and deployment

## Troubleshooting

Common issues and solutions:

- **Service health check failures**: Ensure all services are running with `docker-compose ps`
- **MinIO connection issues**: Verify MinIO credentials in the configuration
- **Data pipeline failures**: Check data service logs for detailed error messages
- **Storage errors**: Ensure shared volumes are properly mounted

## Next prompt : delagating audit and monitoring to monitoring service

@train_model.py#L71-72this shouldn't be delegated to storage manager instead ? same for this @train_model.py#L106-111 @train_model.py#L106-111 ?

* Par ailleurs, il faut que chaque service ait son propre utilisation du storage manager.
* move the sample to the config