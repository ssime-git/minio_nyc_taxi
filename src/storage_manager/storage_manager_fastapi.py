"""
FastAPI implementation for the Storage Manager service.
Provides RESTful API endpoints for storage operations.
"""
import os
import sys
import json
import logging
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks, Query, Body
from fastapi.responses import JSONResponse
import uvicorn
import requests
from datetime import datetime

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import SHARED_DATA_DIR

# Use absolute import instead of relative import
from storage_manager.manager import StorageManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Storage Manager API",
    description="API for managing storage operations with MinIO",
    version="1.0.0"
)

# Initialize storage manager
storage_manager = StorageManager()

@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "storage-manager"}

@app.get("/buckets")
def list_buckets():
    """List all buckets."""
    try:
        buckets = storage_manager.list_buckets()
        return {"buckets": buckets}
    except Exception as e:
        logger.error(f"Error listing buckets: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing buckets: {str(e)}")

@app.post("/buckets/{bucket_name}")
def create_bucket(bucket_name: str, versioning: bool = True):
    """Create a new bucket with optional versioning."""
    try:
        storage_manager.create_bucket(bucket_name, versioning=versioning)
        return {"status": "success", "message": f"Bucket {bucket_name} created successfully"}
    except Exception as e:
        logger.error(f"Error creating bucket {bucket_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating bucket: {str(e)}")

@app.get("/buckets/{bucket_name}/objects")
def list_objects(bucket_name: str, prefix: str = ""):
    """List objects in a bucket with optional prefix filtering."""
    try:
        objects = storage_manager.list_objects(bucket_name, prefix=prefix)
        return {"objects": objects}
    except Exception as e:
        logger.error(f"Error listing objects in bucket {bucket_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing objects: {str(e)}")

@app.post("/buckets/{bucket_name}/upload")
async def upload_file(
    bucket_name: str, 
    object_name: str = Form(...), 
    file: UploadFile = File(...),
    metadata: Optional[Dict[str, str]] = None
):
    """Upload a file to a bucket."""
    try:
        # Save uploaded file to temporary location
        temp_file_path = f"/tmp/{object_name}"
        with open(temp_file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Upload file to MinIO
        result = storage_manager.upload_file(
            bucket_name=bucket_name,
            object_name=object_name,
            local_path=temp_file_path,
            metadata=metadata
        )
        
        # Clean up temporary file
        os.remove(temp_file_path)
        
        return {
            "status": "success", 
            "message": f"File {object_name} uploaded successfully",
            "etag": result.get("etag", ""),
            "version_id": result.get("version_id", "")
        }
    except Exception as e:
        logger.error(f"Error uploading file to bucket {bucket_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}")

@app.get("/buckets/{bucket_name}/download/{object_name}")
def download_file(
    bucket_name: str, 
    object_name: str, 
    local_path: str,
    version_id: Optional[str] = None
):
    """Download a file from a bucket."""
    try:
        success = storage_manager.download_file(
            bucket_name=bucket_name,
            object_name=object_name,
            local_path=local_path,
            version_id=version_id
        )
        
        if success:
            return {
                "status": "success", 
                "message": f"File {object_name} downloaded successfully to {local_path}"
            }
        else:
            raise HTTPException(status_code=404, detail=f"File {object_name} not found or download failed")
    except Exception as e:
        logger.error(f"Error downloading file from bucket {bucket_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error downloading file: {str(e)}")

@app.post("/download-file")
def download_file_from_url(
    file_url: str = Body(...),
    object_name: str = Body(...),
    bucket_name: str = Body(...),
    local_file_path: str = Body(...)
):
    """Download a file from a URL and store it in MinIO."""
    try:
        # Download the file from the URL
        logger.info(f"Downloading file from URL: {file_url}")
        response = requests.get(file_url, stream=True)
        response.raise_for_status()
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
        
        # Save the file locally
        with open(local_file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # Upload to MinIO
        success = storage_manager.upload_file(
            bucket_name=bucket_name,
            object_name=object_name,
            local_path=local_file_path
        )
        
        if success:
            return {
                "status": "success",
                "message": f"File downloaded from {file_url} and stored in {bucket_name}/{object_name}",
                "local_path": local_file_path
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to upload file to MinIO")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error downloading file from URL {file_url}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error downloading file from URL: {str(e)}")
    except Exception as e:
        logger.error(f"Error in download_file_from_url: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload-file")
def upload_file_to_minio(
    bucket_name: str = Body(...),
    object_name: str = Body(...),
    local_file_path: str = Body(...)
):
    """Upload a file to MinIO."""
    try:
        logger.info(f"Uploading file {local_file_path} to {bucket_name}/{object_name}")
        
        # Check if file exists
        if not os.path.exists(local_file_path):
            raise HTTPException(status_code=404, detail=f"File {local_file_path} not found")
        
        # Upload to MinIO
        success = storage_manager.upload_file(
            bucket_name=bucket_name,
            object_name=object_name,
            local_path=local_file_path
        )
        
        if success:
            return {
                "status": "success",
                "message": f"File {local_file_path} uploaded to {bucket_name}/{object_name}"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to upload file to MinIO")
    except Exception as e:
        logger.error(f"Error in upload_file_to_minio: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/buckets/{bucket_name}/versions/{object_name}")
def get_object_versions(bucket_name: str, object_name: str):
    """Get all versions of an object."""
    try:
        versions = storage_manager.get_object_versions(bucket_name, object_name)
        return {"versions": versions}
    except Exception as e:
        logger.error(f"Error getting versions for {object_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting versions: {str(e)}")

@app.delete("/buckets/{bucket_name}/objects/{object_name}")
def delete_object(bucket_name: str, object_name: str, version_id: Optional[str] = None):
    """Delete an object from a bucket."""
    try:
        storage_manager.delete_object(bucket_name, object_name, version_id=version_id)
        return {
            "status": "success", 
            "message": f"Object {object_name} deleted successfully"
        }
    except Exception as e:
        logger.error(f"Error deleting object {object_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting object: {str(e)}")

@app.post("/buckets/{bucket_name}/copy")
def copy_object(
    bucket_name: str, 
    source_object: str = Body(..., embed=True), 
    target_object: str = Body(..., embed=True),
    source_version_id: Optional[str] = Body(None, embed=True)
):
    """Copy an object within the same bucket."""
    try:
        result = storage_manager.copy_object(
            bucket_name=bucket_name,
            source_object_name=source_object,
            target_object_name=target_object,
            source_version_id=source_version_id
        )
        
        return {
            "status": "success", 
            "message": f"Object {source_object} copied to {target_object} successfully",
            "etag": result.get("etag", ""),
            "version_id": result.get("version_id", "")
        }
    except Exception as e:
        logger.error(f"Error copying object {source_object}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error copying object: {str(e)}")

if __name__ == "__main__":
    uvicorn.run("storage_manager_fastapi:app", host="0.0.0.0", port=8001, reload=True)
