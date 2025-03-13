# NYC Taxi MLOps Pipeline

A comprehensive MLOps pipeline for processing, analyzing, and modeling NYC Taxi trip data using MinIO as the central storage hub.

## Project Overview

This project implements a complete MLOps pipeline for NYC Taxi data, featuring:

- Centralized object storage with MinIO
- Automated data ingestion and processing for any month/year
- Feature engineering and dataset versioning
- Model training and experiment tracking with MLflow
- Pipeline orchestration and monitoring
- GDPR compliance and data anonymization
- FastAPI REST interfaces for all services
- Environment variable configuration for dynamic data processing

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
   - Data ingestion from external sources for any specified year/month
   - Data transformation and feature engineering
   - Dataset versioning and quality validation
   - GDPR compliance features

3. **Training Service**
   - Model training with versioned datasets
   - Read-only data access
   - MLflow integration for experiment tracking
   - Support for training from specific data files

4. **MLflow Tracking Server**
   - Experiment tracking and metrics
   - Model registry
   - MinIO artifact storage

5. **Orchestrator**
   - Pipeline coordination and job scheduling
   - Health checks and service monitoring
   - Error handling and retry mechanisms
   - Status tracking and reporting
   - Support for custom year/month parameters in pipeline runs

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
- Default year and month for data processing (can be overridden via API)

## Data Flow

1. **Data Ingestion**
   - Raw NYC Taxi data is downloaded from the official source for the specified year/month
   - Files are stored in MinIO raw data bucket
   - Data quality checks are performed

2. **Feature Engineering**
   - Raw data is processed to create features
   - Engineered features include time-based features, distance calculations, and fare metrics
   - Processed data is stored in MinIO processed data bucket

3. **Train/Test Split**
   - Data is split into training and testing sets
   - Splits are stored in separate MinIO buckets with appropriate naming conventions

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
   MINIO_PORT=9000
   MINIO_CONSOLE_PORT=9001
   
   # Data Pipeline Configuration - Change these to set default month/year
   DATA_YEAR=2023
   DATA_MONTH=01
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

## Using the Pipeline

### Running the Pipeline

You can trigger the pipeline in two ways:

1. **Using default year/month** (from environment variables):
   ```bash
   curl -X POST http://localhost:8080/run-pipeline
   ```

2. **Specifying custom year/month**:
   ```bash
   curl -X POST -H "Content-Type: application/json" \
     http://localhost:8080/run-pipeline \
     -d '{"year": "2023", "month": "04"}'
   ```

### Checking Pipeline Status

```bash
curl http://localhost:8080/pipeline-status
```

### Accessing MinIO Console

Open your browser and navigate to:
```
http://localhost:9001
```
Login with the credentials specified in your `.env` file.

### Accessing MLflow UI

Open your browser and navigate to:
```
http://localhost:5000
```

## Potential Improvements

1. **Enhanced Orchestration**:
   - Implement DAG-based workflow management
   - Add support for parallel processing of multiple months
   - Implement more sophisticated retry mechanisms

2. **Data Quality Monitoring**:
   - Add data drift detection
   - Implement automated data quality alerts
   - Create data quality dashboards

3. **Model Monitoring**:
   - Add model performance monitoring over time
   - Implement automated retraining triggers based on performance degradation
   - Add model explainability features

4. **Security Enhancements**:
   - Implement OAuth2 authentication for all services
   - Add role-based access control for different user types
   - Enhance audit logging for security events

5. **Scalability Improvements**:
   - Implement Kubernetes deployment for better scaling
   - Add support for distributed training
   - Optimize storage usage for large datasets

6. **User Interface**:
   - Develop a web-based dashboard for pipeline monitoring
   - Add visualization tools for data and model metrics
   - Create a user-friendly interface for triggering pipeline runs

7. **CI/CD Integration**:
   - Add automated testing for all components
   - Implement CI/CD pipelines for continuous deployment
   - Add code quality checks and security scanning

## Project Structure

```
minio_nyc_taxi/
├── docker-compose.yml          # Docker Compose configuration
├── .env                        # Environment variables
├── README.md                   # Project documentation
├── src/                        # Source code
│   ├── config.py               # Global configuration
│   ├── data/                   # Data service
│   │   ├── data_service_fastapi.py  # FastAPI implementation
│   │   └── data_service.py     # Data ingestion and processing
│   ├── storage_manager/        # Storage manager service
│   │   ├── manager.py          # MinIO operations
│   │   └── server.py           # REST API server
│   ├── models/                 # Training service
│   │   ├── train_model_fastapi.py  # FastAPI implementation
│   │   └── train_model.py      # Model training logic
│   ├── orchestrator/           # Orchestrator service
│   │   ├── main.py             # Orchestration logic
│   │   └── orchestrator_api.py # FastAPI implementation
│   └── monitoring/             # Monitoring service
│       ├── audit.py            # Audit logging
│       └── monitoring.py       # Monitoring logic
└── data/                       # Mounted data volume
    ├── raw/                    # Raw data
    ├── processed/              # Processed data
    ├── train/                  # Training data
    └── test/                   # Test data
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- NYC Taxi & Limousine Commission for providing the dataset
- MinIO team for the object storage solution
- MLflow team for the experiment tracking framework