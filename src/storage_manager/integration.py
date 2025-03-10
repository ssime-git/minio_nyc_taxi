"""Integration layer between StorageManager and existing minio_setup functionality."""
from .manager import StorageManager
from .config import (
    MINIO_ENDPOINT,
    MINIO_ROOT_USER as MINIO_ACCESS_KEY,
    MINIO_ROOT_PASSWORD as MINIO_SECRET_KEY,
    MINIO_BUCKET as BUCKET_NAME
)
import os
import logging
from typing import Optional

# Configure logging
logger = logging.getLogger(__name__)

# Initialize global storage manager instance
_storage_manager = StorageManager(
    endpoint=MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY
)

def ensure_bucket_exists(bucket_name: str) -> None:
    """Ensure bucket exists with versioning enabled (compatible with minio_setup)."""
    _storage_manager.create_bucket(bucket_name, versioning=True)

def upload_to_minio(local_path: str, bucket: str, object_name: str) -> dict:
    """Enhanced version of minio_setup.upload_to_minio with versioning support."""
    ensure_bucket_exists(bucket)
    # Remove the metadata parameter as it's not supported by the upload_file method
    return _storage_manager.upload_file(
        bucket_name=bucket,
        object_name=object_name,
        local_path=local_path
    )

def download_from_minio(bucket: str, object_name: str, local_path: str, version_id: Optional[str] = None) -> bool:
    """Enhanced version of minio_setup.download_from_minio with versioning support."""
    try:
        # Use download_file method instead of get_object
        return _storage_manager.download_file(
            bucket_name=bucket,
            object_name=object_name,
            local_path=local_path,
            version_id=version_id
        )
    except Exception as e:
        logger.error(f"Error downloading {object_name}: {str(e)}")
        return False

def get_object_versions(bucket: str, object_name: str) -> list:
    """Get all versions of an object."""
    return _storage_manager.get_object_versions(bucket, object_name)

def list_bucket_contents(bucket: str, prefix: str = "") -> list:
    """List contents of a bucket with optional prefix filtering."""
    return _storage_manager.list_objects(bucket, prefix=prefix)
