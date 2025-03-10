"""
Storage manager for MinIO operations.
Handles bucket management, file operations, and versioning.
"""
import os
import sys
import logging
from minio import Minio
from minio.error import S3Error
from datetime import datetime, timezone

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    MINIO_ENDPOINT,
    MINIO_ROOT_USER,
    MINIO_ROOT_PASSWORD,
    MINIO_BUCKET,
    SHARED_DATA_DIR
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class StorageManager:
    """Manages MinIO storage operations with versioning and audit support."""
    
    def __init__(
        self,
        endpoint: str = MINIO_ENDPOINT,
        access_key: str = MINIO_ROOT_USER,
        secret_key: str = MINIO_ROOT_PASSWORD,
        bucket_name: str = MINIO_BUCKET,
        secure: bool = False
    ):
        """Initialize MinIO client with credentials."""
        # Strip http:// or https:// from endpoint
        if endpoint.startswith("http://"):
            endpoint = endpoint[7:]
        elif endpoint.startswith("https://"):
            endpoint = endpoint[8:]
            secure = True
            
        self.endpoint = endpoint
        self.bucket_name = bucket_name
        
        try:
            self.client = Minio(
                endpoint,
                access_key=access_key,
                secret_key=secret_key,
                secure=secure
            )
            logger.info(f"Initialized MinIO client for endpoint: {endpoint}")
        except Exception as e:
            logger.error(f"Failed to initialize MinIO client: {str(e)}")
            raise

    def check_connection(self) -> bool:
        """Check if MinIO connection is working."""
        try:
            self.client.list_buckets()
            logger.info("MinIO connection check successful")
            return True
        except Exception as e:
            logger.error(f"MinIO connection check failed: {str(e)}")
            return False

    def create_bucket(self, bucket_name: str = None, versioning: bool = True) -> bool:
        """Create a bucket with optional versioning."""
        try:
            bucket = bucket_name or self.bucket_name
            if not self.client.bucket_exists(bucket):
                self.client.make_bucket(bucket)
                logger.info(f"Created bucket: {bucket}")
                
                if versioning:
                    # Updated versioning API call to match current MinIO Python client
                    config = {"Status": "Enabled" if versioning else "Suspended"}
                    self.client.set_bucket_versioning(bucket, config)
                    logger.info(f"Enabled versioning for bucket: {bucket}")
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to create bucket {bucket_name}: {str(e)}")
            return False

    def upload_file(
        self,
        local_path: str,
        object_name: str = None,
        bucket_name: str = None
    ) -> bool:
        """Upload a file to MinIO."""
        try:
            bucket = bucket_name or self.bucket_name
            
            # Create bucket if it doesn't exist
            if not self.client.bucket_exists(bucket):
                self.create_bucket(bucket)
            
            # If object_name not provided, use filename from local_path
            if not object_name:
                object_name = os.path.basename(local_path)
            
            # Upload file
            self.client.fput_object(bucket, object_name, local_path)
            logger.info(f"Uploaded {local_path} to {bucket}/{object_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to upload {local_path}: {str(e)}")
            return False

    def download_file(
        self,
        object_name: str,
        local_path: str = None,
        bucket_name: str = None,
        version_id: str = None
    ) -> bool:
        """Download a file from MinIO."""
        try:
            bucket = bucket_name or self.bucket_name
            
            # If local_path not provided, use object_name
            if not local_path:
                local_path = object_name
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            # Download file
            if version_id:
                self.client.fget_object(
                    bucket,
                    object_name,
                    local_path,
                    version_id=version_id
                )
            else:
                self.client.fget_object(bucket, object_name, local_path)
                
            logger.info(f"Downloaded {bucket}/{object_name} to {local_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to download {object_name}: {str(e)}")
            return False

    def list_objects(
        self,
        prefix: str = "",
        recursive: bool = True,
        bucket_name: str = None
    ) -> list:
        """List objects in a bucket with optional prefix filter."""
        try:
            bucket = bucket_name or self.bucket_name
            objects = self.client.list_objects(
                bucket,
                prefix=prefix,
                recursive=recursive
            )
            return [obj.object_name for obj in objects]
            
        except Exception as e:
            logger.error(f"Failed to list objects: {str(e)}")
            return []

    def get_object_stats(
        self,
        object_name: str,
        bucket_name: str = None,
        version_id: str = None
    ) -> dict:
        """Get object statistics including size and last modified time."""
        try:
            bucket = bucket_name or self.bucket_name
            
            if version_id:
                obj = self.client.stat_object(
                    bucket,
                    object_name,
                    version_id=version_id
                )
            else:
                obj = self.client.stat_object(bucket, object_name)
                
            return {
                "size": obj.size,
                "last_modified": obj.last_modified,
                "version_id": obj.version_id,
                "etag": obj.etag
            }
            
        except Exception as e:
            logger.error(f"Failed to get stats for {object_name}: {str(e)}")
            return None

    def delete_object(
        self,
        object_name: str,
        bucket_name: str = None,
        version_id: str = None
    ) -> bool:
        """Delete an object from MinIO."""
        try:
            bucket = bucket_name or self.bucket_name
            
            if version_id:
                self.client.remove_object(
                    bucket,
                    object_name,
                    version_id=version_id
                )
            else:
                self.client.remove_object(bucket, object_name)
                
            logger.info(f"Deleted {bucket}/{object_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete {object_name}: {str(e)}")
            return False

    def get_object_versions(
        self,
        object_name: str,
        bucket_name: str = None
    ) -> list:
        """Get all versions of an object."""
        try:
            bucket = bucket_name or self.bucket_name
            versions = []
            
            for version in self.client.list_objects(bucket, prefix=object_name):
                version_info = self.get_object_stats(
                    object_name,
                    version_id=version.version_id
                )
                if version_info:
                    versions.append(version_info)
                    
            return versions
            
        except Exception as e:
            logger.error(f"Failed to get versions for {object_name}: {str(e)}")
            return []

    def download_from_url(
        self,
        url: str,
        object_name: str = None,
        bucket_name: str = None
    ) -> str:
        """
        Download a file from an external URL and store it in MinIO.
        
        Args:
            url (str): URL to download the file from
            object_name (str, optional): Name to store the object as in MinIO
            bucket_name (str, optional): Bucket to store the object in
            
        Returns:
            str: Object name in MinIO if successful, None otherwise
        """
        try:
            import requests
            from pathlib import Path
            
            bucket = bucket_name or self.bucket_name
            
            # Create bucket if it doesn't exist
            if not self.client.bucket_exists(bucket):
                self.create_bucket(bucket)
            
            # If object_name not provided, use filename from URL
            if not object_name:
                object_name = url.split('/')[-1]
            
            # Create a temporary directory
            temp_dir = "/tmp/storage_manager"
            os.makedirs(temp_dir, exist_ok=True)
            
            # Define the local file path
            local_file_path = f"{temp_dir}/{object_name}"
            
            # Download the file
            logger.info(f"Downloading data from {url} to {local_file_path}")
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            with open(local_file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Upload the file to MinIO
            self.upload_file(local_file_path, object_name, bucket)
            
            # Clean up the temporary file
            os.remove(local_file_path)
            
            logger.info(f"Downloaded from {url} and stored in {bucket}/{object_name}")
            return object_name
            
        except Exception as e:
            logger.error(f"Failed to download from URL {url}: {str(e)}")
            return None

    def integrate_data(
        self,
        new_data_object: str,
        consolidated_object: str,
        sample_fraction: float = 0.01,
        months_to_keep: int = 6,
        bucket_name: str = None
    ) -> bool:
        """
        Integrate new data with existing consolidated data, keeping only recent months.
        
        Args:
            new_data_object (str): Object name of the new data in MinIO
            consolidated_object (str): Object name of the consolidated data in MinIO
            sample_fraction (float): Fraction of new data to sample
            months_to_keep (int): Number of months of data to keep
            bucket_name (str, optional): Bucket name
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            import pandas as pd
            from datetime import datetime
            
            bucket = bucket_name or self.bucket_name
            
            # Create temporary directory
            temp_dir = "/tmp/storage_manager"
            os.makedirs(temp_dir, exist_ok=True)
            
            # Define local paths
            new_data_path = f"{temp_dir}/{new_data_object}"
            consolidated_path = f"{temp_dir}/{consolidated_object}"
            
            # Download new data
            if not self.download_file(new_data_object, new_data_path, bucket):
                logger.error(f"Failed to download new data: {new_data_object}")
                return False
            
            # Try to load existing consolidated dataset
            df_existing = pd.DataFrame()
            if self.object_exists(consolidated_object, bucket):
                if not self.download_file(consolidated_object, consolidated_path, bucket):
                    logger.error(f"Failed to download consolidated data: {consolidated_object}")
                else:
                    try:
                        # Determine file type and load accordingly
                        if consolidated_object.endswith('.csv'):
                            df_existing = pd.read_csv(consolidated_path)
                        elif consolidated_object.endswith('.parquet'):
                            df_existing = pd.read_parquet(consolidated_path)
                        else:
                            logger.error(f"Unsupported file format for {consolidated_object}")
                            return False
                        
                        logger.info(f"Loaded existing dataset from MinIO: {consolidated_object}")
                    except Exception as e:
                        logger.error(f"Error loading consolidated data: {str(e)}")
                        return False
            else:
                logger.info(f"No existing dataset found in MinIO. Creating a new dataset.")
            
            # Convert datetime column if it exists
            if "tpep_pickup_datetime" in df_existing.columns and not pd.api.types.is_datetime64_any_dtype(df_existing["tpep_pickup_datetime"]):
                df_existing["tpep_pickup_datetime"] = pd.to_datetime(df_existing["tpep_pickup_datetime"], errors='coerce')
            
            # Load new data and sample
            if new_data_object.endswith('.csv'):
                df_new = pd.read_csv(new_data_path)
            elif new_data_object.endswith('.parquet'):
                df_new = pd.read_parquet(new_data_path)
            else:
                logger.error(f"Unsupported file format for {new_data_object}")
                return False
            
            df_new_sampled = df_new.sample(frac=sample_fraction, random_state=42)
            if "tpep_pickup_datetime" in df_new_sampled.columns:
                df_new_sampled["tpep_pickup_datetime"] = pd.to_datetime(df_new_sampled["tpep_pickup_datetime"], errors='coerce')
            
            # Merge new sampled data with existing dataset
            df_combined = pd.concat([df_existing, df_new_sampled], ignore_index=True)
            
            # Apply rolling window: keep only the last N months of data
            if "tpep_pickup_datetime" in df_combined.columns:
                latest_date = df_combined["tpep_pickup_datetime"].max()
                df_combined = df_combined[df_combined["tpep_pickup_datetime"] >= latest_date - pd.DateOffset(months=months_to_keep)]
            
            # Save the new dataset
            if consolidated_object.endswith('.csv'):
                df_combined.to_csv(consolidated_path, index=False)
            elif consolidated_object.endswith('.parquet'):
                df_combined.to_parquet(consolidated_path)
            
            # Upload the consolidated dataset
            if not self.upload_file(consolidated_path, consolidated_object, bucket):
                logger.error(f"Failed to upload consolidated data: {consolidated_object}")
                return False
            
            # Clean up temporary files
            os.remove(new_data_path)
            os.remove(consolidated_path)
            
            logger.info(f"Successfully integrated new data into consolidated dataset")
            return True
            
        except Exception as e:
            logger.error(f"Error integrating data: {str(e)}")
            return False
            
    def object_exists(self, object_name: str, bucket_name: str = None) -> bool:
        """Check if an object exists in MinIO."""
        try:
            bucket = bucket_name or self.bucket_name
            self.client.stat_object(bucket, object_name)
            return True
        except Exception:
            return False
