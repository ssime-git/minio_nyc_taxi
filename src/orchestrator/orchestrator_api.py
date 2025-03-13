#!/usr/bin/env python
"""
FastAPI implementation of the MLOps Orchestrator.
Provides API endpoints for orchestrating the MLOps pipeline and manually triggering processes.
"""

import os
import sys
import logging
import time
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, HTTPException, BackgroundTasks
import uvicorn
from pydantic import BaseModel

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    DATA_SERVICE_URL,
    TRAINING_SERVICE_URL,
    STORAGE_MANAGER_URL,
    MONITORING_SERVICE_URL,
    MLFLOW_URL,
    DEFAULT_YEAR,
    DEFAULT_MONTH,
    HEALTH_CHECK_RETRIES,
    HEALTH_CHECK_INTERVAL
)

# Import the existing MLOpsOrchestrator
from main import MLOpsOrchestrator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="NYC Taxi MLOps Orchestrator",
    description="API for orchestrating the MLOps pipeline for NYC Taxi data",
    version="1.0.0"
)

# Initialize orchestrator
orchestrator = MLOpsOrchestrator()

# Define request and response models
class ProcessDataRequest(BaseModel):
    year: Optional[str] = None
    month: Optional[str] = None

class ServiceHealthResponse(BaseModel):
    status: str
    healthy_services: List[str]
    unhealthy_services: List[str]

class PipelineResponse(BaseModel):
    status: str
    message: str
    details: Optional[Dict[str, Any]] = None

# API endpoints
@app.get("/")
async def root():
    """Root endpoint for health check"""
    return {"status": "healthy", "service": "orchestrator"}

@app.get("/health", response_model=ServiceHealthResponse)
async def check_health():
    """Check the health of all services in the MLOps pipeline"""
    healthy_services = []
    unhealthy_services = []
    
    # Check MinIO health
    if orchestrator.check_minio_health():
        healthy_services.append("minio")
    else:
        unhealthy_services.append("minio")
    
    # Check MLflow health
    if orchestrator.check_mlflow_health():
        healthy_services.append("mlflow")
    else:
        unhealthy_services.append("mlflow")
    
    # Check data service health
    if orchestrator.check_data_service_health():
        healthy_services.append("data-service")
    else:
        unhealthy_services.append("data-service")
    
    # Check storage manager health
    if orchestrator.check_storage_manager_health():
        healthy_services.append("storage-manager")
    else:
        unhealthy_services.append("storage-manager")
    
    # Check monitoring service health
    if orchestrator.check_monitoring_service_health():
        healthy_services.append("monitoring-service")
    else:
        unhealthy_services.append("monitoring-service")
    
    # Check training service health
    if orchestrator.check_training_service_health():
        healthy_services.append("training-service")
    else:
        unhealthy_services.append("training-service")
    
    status = "healthy" if not unhealthy_services else "unhealthy"
    
    return {
        "status": status,
        "healthy_services": healthy_services,
        "unhealthy_services": unhealthy_services
    }

@app.post("/process-data", response_model=PipelineResponse)
async def process_data(
    background_tasks: BackgroundTasks,
    request: Optional[ProcessDataRequest] = None
):
    """
    Manually trigger data processing for a specific year and month.
    If no year/month provided, uses values from environment variables or defaults.
    """
    # Use request parameters, environment variables, or defaults
    year = request.year if request and request.year else DEFAULT_YEAR
    month = request.month if request and request.month else DEFAULT_MONTH
    
    # Initialize services if needed
    if not orchestrator.storage_manager:
        orchestrator.initialize_services()
    
    try:
        # Make a request to the data service with the specified year and month
        import requests
        
        response = requests.post(
            f"{DATA_SERVICE_URL}/process-data",
            json={"year": year, "month": month},
            timeout=300
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=500, 
                detail=f"Data processing failed with status code {response.status_code}: {response.text}"
            )
        
        data_response = response.json()
        logger.info(f"Data processing completed with response: {data_response}")
        
        return {
            "status": "success",
            "message": f"Successfully processed data for {year}-{month}",
            "details": data_response
        }
    except Exception as e:
        logger.error(f"Error processing data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/run-training", response_model=PipelineResponse)
async def run_training(
    background_tasks: BackgroundTasks,
    train_file: Optional[str] = None,
    test_file: Optional[str] = None
):
    """
    Manually trigger model training with optional train and test file names.
    If no files provided, the training service will use the latest available files.
    """
    # Initialize services if needed
    if not orchestrator.storage_manager:
        orchestrator.initialize_services()
    
    try:
        # Run the training pipeline
        success, metrics = orchestrator.run_training_pipeline(train_file, test_file)
        
        if not success:
            raise HTTPException(status_code=500, detail="Training pipeline failed")
        
        return {
            "status": "success",
            "message": "Successfully ran training pipeline",
            "details": {"metrics": metrics}
        }
    except Exception as e:
        logger.error(f"Error running training pipeline: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/run-pipeline", response_model=PipelineResponse)
async def run_pipeline(
    background_tasks: BackgroundTasks,
    request: Optional[ProcessDataRequest] = None
):
    """
    Run the complete MLOps pipeline from data ingestion to model training
    with optional year and month parameters.
    """
    # Use request parameters, environment variables, or defaults
    year = request.year if request and request.year else DEFAULT_YEAR
    month = request.month if request and request.month else DEFAULT_MONTH
    
    # Set environment variables for the pipeline run
    os.environ["DATA_YEAR"] = year
    os.environ["DATA_MONTH"] = month
    
    # Run in background to avoid timeout
    background_tasks.add_task(orchestrator.run_pipeline)
    
    return {
        "status": "started",
        "message": f"Pipeline started for {year}-{month}. Check logs for progress.",
        "details": {"year": year, "month": month}
    }

@app.get("/generate-reports", response_model=PipelineResponse)
async def generate_reports():
    """Generate monitoring and compliance reports"""
    # Initialize services if needed
    if not orchestrator.storage_manager:
        orchestrator.initialize_services()
    
    try:
        # Generate reports
        orchestrator.generate_reports()
        
        return {
            "status": "success",
            "message": "Successfully generated reports"
        }
    except Exception as e:
        logger.error(f"Error generating reports: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    try:
        # Start the FastAPI server
        uvicorn.run(app, host="0.0.0.0", port=8080)
    except KeyboardInterrupt:
        logger.info("Orchestrator API stopped")
    except Exception as e:
        logger.error(f"Error starting orchestrator API: {str(e)}")
