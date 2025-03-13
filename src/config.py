"""
Global configuration for the NYC Taxi MLOps Pipeline.
This file contains configuration settings used across all services.
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# MinIO configuration
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ROOT_USER = os.getenv("MINIO_ROOT_USER", "user")
MINIO_ROOT_PASSWORD = os.getenv("MINIO_ROOT_PASSWORD", "password123")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "nyc-taxi-data")

# Service URLs
STORAGE_MANAGER_URL = os.getenv("STORAGE_MANAGER_URL", "http://storage-manager:8001")
DATA_SERVICE_URL = os.getenv("DATA_SERVICE_URL", "http://data-service:8000")
TRAINING_SERVICE_URL = os.getenv("TRAINING_SERVICE_URL", "http://training-service:8002")
MONITORING_SERVICE_URL = os.getenv("MONITORING_SERVICE_URL", "http://monitoring:8003")
MLFLOW_URL = os.getenv("MLFLOW_URL", "http://mlflow:8080")

# Shared volume paths
SHARED_DATA_DIR = "/app/data/temp"
RAW_DATA_DIR = os.getenv("RAW_DATA_DIR", "/app/data/raw")
PROCESSED_DATA_DIR = os.getenv("PROCESSED_DATA_DIR", "/app/data/processed")

# NYC Taxi data source
BASE_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_{year}-{month:02d}.parquet"

# MLFlow configuration
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:8080")

# Storage settings
VERSIONING_ENABLED = True
DATA_RETENTION_DAYS = 30  # For lifecycle policies

# Health check settings
HEALTH_CHECK_RETRIES = 30
HEALTH_CHECK_INTERVAL = 10  # seconds
HEALTH_CHECK_DELAY = 5  # seconds

# Data pipeline settings
DEFAULT_YEAR = os.getenv("DATA_YEAR", "2023")
DEFAULT_MONTH = os.getenv("DATA_MONTH", "01")
CONSOLIDATED_FILE_NAME = "consolidated_nyc_taxi_data.parquet"
