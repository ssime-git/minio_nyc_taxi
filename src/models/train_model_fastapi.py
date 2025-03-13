"""
FastAPI implementation for the Model Training service.
Provides RESTful API endpoints for model training operations.
"""
import os
import sys
import json
import logging
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn
from datetime import datetime
from pathlib import Path

# Add parent directory to path to import config
sys.path.append(str(Path(__file__).resolve().parent.parent))

from storage_manager.manager import StorageManager
from config import (
    MINIO_ENDPOINT,
    MINIO_ROOT_USER,
    MINIO_ROOT_PASSWORD,
    MINIO_BUCKET,
    PROCESSED_DATA_DIR,
    MLFLOW_TRACKING_URI
)
from monitoring.audit import DataAuditor
from models.train_model import ModelTrainer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Model Training API",
    description="API for training ML models on NYC Taxi data",
    version="1.0.0"
)

# Initialize global model trainer instance
model_trainer = ModelTrainer()

# Define request models
class TrainingRequest(BaseModel):
    """Model for training request data."""
    train_file: Optional[str] = None
    test_file: Optional[str] = None
    sample_size: Optional[int] = 100000
    experiment_name: Optional[str] = "nyc-taxi-fare-prediction"
    model_params: Optional[Dict[str, Any]] = None

@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "training-service"}

@app.post("/train")
async def train_model(request: TrainingRequest, background_tasks: BackgroundTasks):
    """Train a model with the specified parameters."""
    try:
        # Start training in the background
        background_tasks.add_task(
            model_trainer.train_model_from_files,
            train_file=request.train_file,
            test_file=request.test_file,
            sample_size=request.sample_size,
            experiment_name=request.experiment_name,
            model_params=request.model_params
        )
        
        return {
            "status": "success", 
            "message": "Model training started in the background",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error starting model training: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error starting model training: {str(e)}")

@app.get("/models")
def list_models():
    """List all trained models."""
    try:
        models = model_trainer.list_models()
        return {"models": models}
    except Exception as e:
        logger.error(f"Error listing models: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing models: {str(e)}")

@app.get("/experiments")
def list_experiments():
    """List all MLflow experiments."""
    try:
        experiments = model_trainer.list_experiments()
        return {"experiments": experiments}
    except Exception as e:
        logger.error(f"Error listing experiments: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing experiments: {str(e)}")

@app.get("/runs/{experiment_id}")
def list_runs(experiment_id: str):
    """List all runs for a specific experiment."""
    try:
        runs = model_trainer.list_runs(experiment_id)
        return {"runs": runs}
    except Exception as e:
        logger.error(f"Error listing runs for experiment {experiment_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing runs: {str(e)}")

@app.get("/metrics/{run_id}")
def get_metrics(run_id: str):
    """Get metrics for a specific run."""
    try:
        metrics = model_trainer.get_run_metrics(run_id)
        return {"metrics": metrics}
    except Exception as e:
        logger.error(f"Error getting metrics for run {run_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting metrics: {str(e)}")

@app.post("/register-model")
def register_model(run_id: str, model_name: str):
    """Register a model in the MLflow model registry."""
    try:
        model_version = model_trainer.register_model(run_id, model_name)
        return {
            "status": "success",
            "message": f"Model registered successfully",
            "model_name": model_name,
            "model_version": model_version
        }
    except Exception as e:
        logger.error(f"Error registering model: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error registering model: {str(e)}")

if __name__ == "__main__":
    uvicorn.run("train_model_fastapi:app", host="0.0.0.0", port=8002, reload=True)
