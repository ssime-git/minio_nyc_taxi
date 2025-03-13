#!/usr/bin/env python
"""
FastAPI implementation of the Data Service for handling both data ingestion and feature engineering.
This service provides a REST API for all data-related operations.
"""

import os
import sys
import json
import logging
import datetime
import pandas as pd
import numpy as np
from typing import Optional, List, Dict, Any, Tuple
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
import uvicorn
from pydantic import BaseModel

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    MINIO_BUCKET, 
    SHARED_DATA_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR,
    DEFAULT_YEAR, DEFAULT_MONTH
)

# Import the existing DataService and DataAuditor classes
from data_service import DataService, DataAuditor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="NYC Taxi Data Service",
    description="Service for data ingestion and feature engineering for NYC Taxi data",
    version="1.0.0"
)

# Initialize data service
data_service = DataService()
auditor = DataAuditor()

# Define request and response models
class ProcessDataRequest(BaseModel):
    year: Optional[str] = None
    month: Optional[str] = None

class ProcessDataResponse(BaseModel):
    status: str
    message: str
    processed_files: Optional[List[str]] = None
    train_data: Optional[str] = None
    test_data: Optional[str] = None

class QualityCheckResponse(BaseModel):
    status: str
    missing_values: Dict[str, int]
    data_types: Dict[str, str]
    row_count: int
    column_count: int

# Background task for processing data
def process_data_task(year: str, month: str):
    try:
        logger.info(f"Processing data for {year}-{month}")
        
        # Step 1: Download raw data
        local_file_path = data_service.download_parquet_file(year, month)
        logger.info(f"Downloaded data to {local_file_path}")
        
        # Step 2: Build features
        processed_files = data_service.build_features(year, month)
        if not processed_files:
            logger.error("No files were processed")
            return None
        logger.info(f"Processed {len(processed_files)} files")
        
        return processed_files
    except Exception as e:
        logger.error(f"Error in background processing: {str(e)}")
        return None

# API endpoints
@app.get("/")
async def root():
    """Root endpoint for health check"""
    return {"status": "healthy", "service": "data-service"}

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "data-service"}

@app.post("/process-data", response_model=ProcessDataResponse)
async def process_data(
    background_tasks: BackgroundTasks,
    request: Optional[ProcessDataRequest] = None
):
    """
    Process NYC Taxi data for a specific year and month.
    If no year/month provided, uses values from environment variables or defaults.
    """
    # Use request parameters, environment variables, or defaults
    year = request.year if request and request.year else DEFAULT_YEAR
    month = request.month if request and request.month else DEFAULT_MONTH
    
    try:
        # Log data access
        auditor.log_data_access(
            "data_processing_start",
            "nyc_taxi_data",
            "data_service",
            {"year": year, "month": month}
        )
        
        # Process data synchronously for now (can be made async with background_tasks if needed)
        processed_files = process_data_task(year, month)
        
        if not processed_files:
            raise HTTPException(status_code=500, detail="Failed to process data")
        
        # Get train and test file names from the processed files
        train_file = next((f for f in processed_files if "train" in f), None)
        test_file = next((f for f in processed_files if "test" in f), None)
        
        return {
            "status": "success",
            "message": f"Successfully processed data for {year}-{month}",
            "processed_files": processed_files,
            "train_data": train_file,
            "test_data": test_file
        }
    except Exception as e:
        logger.error(f"Error processing data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/quality-check/{object_name}", response_model=QualityCheckResponse)
async def quality_check(object_name: str, bucket_name: Optional[str] = None):
    """Run quality checks on a dataset in MinIO"""
    try:
        result = data_service.run_quality_check(object_name, bucket_name)
        return {
            "status": "success",
            **result
        }
    except Exception as e:
        logger.error(f"Error running quality check: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/anonymize/{object_name}")
async def anonymize_data(object_name: str, bucket_name: Optional[str] = None):
    """Anonymize data for GDPR compliance"""
    try:
        result = data_service.anonymize_data(object_name, bucket_name)
        if result:
            return {
                "status": "success",
                "message": "Data anonymized successfully",
                "anonymized_object": result,
                "anonymized_bucket": f"{bucket_name or data_service.raw_data_bucket}-anonymized"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to anonymize data")
    except Exception as e:
        logger.error(f"Error anonymizing data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/create-dataset-version/{object_name}")
async def create_dataset_version(
    object_name: str, 
    bucket_name: Optional[str] = None,
    version_tag: Optional[str] = None
):
    """Create a versioned copy of a dataset"""
    try:
        result = data_service.create_dataset_version(object_name, bucket_name, version_tag)
        if result:
            return {
                "status": "success",
                "message": "Dataset version created successfully",
                "versioned_object": result
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to create dataset version")
    except Exception as e:
        logger.error(f"Error creating dataset version: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/set-data-retention-policy")
async def set_data_retention_policy(
    bucket_name: str,
    prefix: str = "",
    days: int = 30
):
    """Set a data retention policy for a bucket"""
    try:
        result = data_service.set_data_retention_policy(bucket_name, prefix, days)
        if result:
            return {
                "status": "success",
                "message": f"Data retention policy set for {bucket_name} with {days} days retention"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to set data retention policy")
    except Exception as e:
        logger.error(f"Error setting data retention policy: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get-data-retention-policy/{bucket_name}")
async def get_data_retention_policy(bucket_name: str):
    """Get the current data retention policy for a bucket"""
    try:
        result = data_service.get_data_retention_policy(bucket_name)
        if result:
            return {
                "status": "success",
                "policy": result
            }
        else:
            raise HTTPException(status_code=404, detail="No retention policy found")
    except Exception as e:
        logger.error(f"Error getting data retention policy: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    try:
        # Start the FastAPI server
        uvicorn.run(app, host="0.0.0.0", port=8000)
    except KeyboardInterrupt:
        logger.info("Data service stopped")
    except Exception as e:
        logger.error(f"Error starting data service: {str(e)}")
