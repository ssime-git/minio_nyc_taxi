# Testing Guide for NYC Taxi MLOps Pipeline

This guide provides step-by-step instructions for testing the MLOps pipeline after migrating to FastAPI and implementing environment variable configuration.

## Prerequisites

- Docker and Docker Compose installed
- `.env` file configured with appropriate values
- All code changes committed

## 1. Build and Start the Services

```bash
# Build all services with the latest changes
docker-compose build

# Start all services in detached mode
docker-compose up -d
```

## 2. Verify Services are Running

```bash
# Check the status of all services
docker-compose ps

# Check logs for the data service
docker logs data_service

# Check logs for the storage manager
docker logs storage_manager

# Check logs for the training service
docker logs training_service

# Check logs for the orchestrator
docker logs orchestrator
```

## 3. Test FastAPI Documentation

1. **Data Service API Documentation**:
   - Open a browser and navigate to: http://localhost:8000/docs
   - Verify that the Swagger UI loads correctly
   - Check that all endpoints are documented

2. **Storage Manager API Documentation**:
   - Open a browser and navigate to: http://localhost:8001/docs
   - Verify that the Swagger UI loads correctly
   - Check that all endpoints are documented

3. **Training Service API Documentation**:
   - Open a browser and navigate to: http://localhost:8002/docs
   - Verify that the Swagger UI loads correctly
   - Check that all endpoints are documented

4. **Orchestrator API Documentation**:
   - Open a browser and navigate to: http://localhost:8080/docs
   - Verify that the Swagger UI loads correctly
   - Check that all endpoints are documented

## 4. Test Health Endpoints

```bash
# Test data service health endpoint
curl http://localhost:8000/health

# Test storage manager health endpoint
curl http://localhost:8001/health

# Test training service health endpoint
curl http://localhost:8002/health

# Test orchestrator health endpoint
curl http://localhost:8080/health
```

## 5. Test Manual Data Processing

### Test with Default Month/Year

```bash
# Trigger data processing with default values
curl -X POST http://localhost:8080/process-data
```

### Test with Specific Month/Year

```bash
# Trigger data processing for February 2023
curl -X POST http://localhost:8080/process-data \
  -H "Content-Type: application/json" \
  -d '{"year": "2023", "month": "02"}'
```

## 6. Test Storage Manager API

### Test Bucket Operations

```bash
# List all buckets
curl http://localhost:8001/buckets

# Create a new test bucket
curl -X POST http://localhost:8001/buckets/test-bucket

# List objects in a bucket
curl http://localhost:8001/buckets/nyc-taxi-data/objects
```

### Test Object Operations

```bash
# Create a test file
echo "Test data" > test.txt

# Upload a file to MinIO (using form data)
curl -X POST http://localhost:8001/buckets/test-bucket/upload \
  -F "object_name=test.txt" \
  -F "file=@test.txt"

# Get object versions
curl http://localhost:8001/buckets/test-bucket/versions/test.txt

# Download a file (specify a local path)
curl "http://localhost:8001/buckets/test-bucket/download/test.txt?local_path=/tmp/downloaded_test.txt"
```

## 7. Test Training Service API

### Test Model Training

```bash
# Start model training with default parameters
curl -X POST http://localhost:8002/train \
  -H "Content-Type: application/json" \
  -d '{}'

# Start model training with specific parameters
curl -X POST http://localhost:8002/train \
  -H "Content-Type: application/json" \
  -d '{
    "train_file": "train_data_2023_02.parquet",
    "test_file": "test_data_2023_02.parquet",
    "sample_size": 50000,
    "experiment_name": "nyc-taxi-feb-2023"
  }'
```

### Test Model Listing and Experiments

```bash
# List all trained models
curl http://localhost:8002/models

# List all MLflow experiments
curl http://localhost:8002/experiments
```

## 8. Test Complete Pipeline

```bash
# Run the complete pipeline with default values
curl -X POST http://localhost:8080/run-pipeline

# Run the complete pipeline with specific month/year
curl -X POST http://localhost:8080/run-pipeline \
  -H "Content-Type: application/json" \
  -d '{"year": "2023", "month": "03"}'
```

## 9. Verify Data Processing Results

1. **Check MinIO for Processed Data**:
   - Open MinIO Console: http://localhost:9001
   - Login with credentials from `.env` file
   - Navigate to the bucket specified in `.env`
   - Verify that data files for the specified month/year exist

2. **Check MLflow for Training Results**:
   - Open MLflow UI: http://localhost:5002
   - Verify that experiments for the processed data exist
   - Check metrics and artifacts

## 10. Test Environment Variable Override

1. **Modify Environment Variables**:
   ```bash
   # Stop the containers
   docker-compose down
   
   # Edit .env file to change month/year
   # DATA_YEAR=2023
   # DATA_MONTH=04
   
   # Restart containers
   docker-compose up -d
   ```

2. **Trigger Pipeline**:
   ```bash
   # Run the pipeline with default values (should use values from .env)
   curl -X POST http://localhost:8080/run-pipeline
   ```

3. **Verify Results**:
   - Check logs to confirm the correct month/year was processed
   - Check MinIO for the new data files

## 11. Test Error Handling

```bash
# Test with invalid month
curl -X POST http://localhost:8080/process-data \
  -H "Content-Type: application/json" \
  -d '{"year": "2023", "month": "13"}'

# Test with invalid year
curl -X POST http://localhost:8080/process-data \
  -H "Content-Type: application/json" \
  -d '{"year": "2030", "month": "01"}'
```

## 12. Clean Up

```bash
# Stop all containers when testing is complete
docker-compose down
```

## Troubleshooting

If you encounter issues during testing:

1. **Check Container Logs**:
   ```bash
   docker logs data_service
   docker logs storage_manager
   docker logs training_service
   docker logs orchestrator
   ```

2. **Verify Network Connectivity**:
   ```bash
   # Check if services can communicate
   docker exec orchestrator ping data_service
   ```

3. **Restart Specific Service**:
   ```bash
   docker-compose restart data_service
   ```

4. **Check Environment Variables**:
   ```bash
   docker exec orchestrator env | grep DATA_
   ```
