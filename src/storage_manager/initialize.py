from storage_manager.manager import StorageManager
from storage_manager.config import MINIO_ENDPOINT, MINIO_ROOT_USER, MINIO_ROOT_PASSWORD, MINIO_BUCKET
import os
import logging
import time

def setup_logging() -> logging.Logger:
    """Set up logging for initialization."""
    logger = logging.getLogger("storage_init")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

def initialize_storage() -> None:
    """Initialize the storage system with buckets."""
    logger = setup_logging()
    
    # Get configuration from environment variables
    minio_endpoint = os.getenv("MINIO_ENDPOINT", MINIO_ENDPOINT)
    minio_access_key = os.getenv("MINIO_ROOT_USER", MINIO_ROOT_USER)
    minio_secret_key = os.getenv("MINIO_ROOT_PASSWORD", MINIO_ROOT_PASSWORD)
    bucket_name = os.getenv("MINIO_BUCKET", MINIO_BUCKET)
    
    # Wait for MinIO to be ready
    logger.info("Waiting for MinIO server to be ready...")
    time.sleep(5)  # Give MinIO time to start
    
    # Initialize storage manager
    try:
        storage = StorageManager(
            endpoint=minio_endpoint,
            access_key=minio_access_key,
            secret_key=minio_secret_key
        )
        
        # Check connection
        if not storage.check_connection():
            logger.error("Failed to connect to MinIO server")
            return
            
        logger.info(f"Successfully connected to MinIO at {minio_endpoint}")
        
        # Create default buckets
        buckets = [bucket_name, f"{bucket_name}-models", f"{bucket_name}-logs"]
        for bucket in buckets:
            if storage.create_bucket(bucket):
                logger.info(f"Created or verified bucket: {bucket}")
            else:
                logger.error(f"Failed to create bucket: {bucket}")
                
        logger.info("Storage initialization completed successfully")
        
    except Exception as e:
        logger.error(f"Storage initialization failed: {str(e)}")

if __name__ == "__main__":
    initialize_storage()
