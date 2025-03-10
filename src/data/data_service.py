#!/usr/bin/env python
"""
Unified Data Service for handling both data ingestion and feature engineering.
This service provides a single HTTP interface for all data-related operations.
"""

import os
import sys
import json
import logging
import datetime
import requests
import pandas as pd
import numpy as np
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse
from sklearn.model_selection import train_test_split

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    MINIO_BUCKET, 
    SHARED_DATA_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DataAuditor:
    """Auditor for data access and operations."""
    
    def log_data_access(self, action, data_type, user, metadata=None):
        """
        Log data access for compliance tracking.
        
        Args:
            action (str): The action performed on the data
            data_type (str): The type of data accessed
            user (str): The user or service accessing the data
            metadata (dict, optional): Additional metadata about the access
        """
        try:
            log_entry = {
                'timestamp': datetime.datetime.now().isoformat(),
                'action': action,
                'data_type': data_type,
                'user': user,
                'metadata': metadata or {}
            }
            
            logger.info(f"Data Access Log: {json.dumps(log_entry)}")
            
            # In a production environment, this would write to a secure audit log
            # that complies with regulatory requirements
            
        except Exception as e:
            logger.error(f"Error logging data access: {str(e)}")

class DataService:
    """Service for data ingestion and feature engineering."""
    
    def __init__(self):
        """Initialize the data service."""
        self.raw_data_bucket = MINIO_BUCKET
        self.processed_data_bucket = f"{self.raw_data_bucket}-processed"
        self.raw_data_dir = RAW_DATA_DIR
        self.processed_data_dir = PROCESSED_DATA_DIR
        # Use the service name from docker-compose.yml
        self.storage_manager_url = "http://storage-manager:8001"
        self.auditor = DataAuditor()
        
        # Create directories if they don't exist
        os.makedirs(self.raw_data_dir, exist_ok=True)
        os.makedirs(self.processed_data_dir, exist_ok=True)
        os.makedirs(SHARED_DATA_DIR, exist_ok=True)
    
    def _storage_manager_request(self, endpoint, method='GET', data=None, params=None):
        """
        Make a request to the storage manager service.
        
        Args:
            endpoint (str): The endpoint to request
            method (str): The HTTP method to use
            data (dict, optional): The data to send in the request body
            params (dict, optional): The query parameters to include in the request
            
        Returns:
            dict: The response from the storage manager service
        """
        try:
            url = f"{self.storage_manager_url}{endpoint}"
            
            if method == 'GET':
                response = requests.get(url, params=params)
            elif method == 'POST':
                response = requests.post(url, json=data)
            else:
                logger.error(f"Unsupported HTTP method: {method}")
                return None
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error making request to storage manager: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error making request to storage manager: {str(e)}")
            return None
    
    def download_parquet_file(self, year, month):
        """
        Download NYC taxi data for a specific year and month.
        
        Args:
            year (str): Year to download data for
            month (str): Month to download data for
            
        Returns:
            str: Path to the downloaded file
        """
        try:
            # Format the URL and filename
            # Convert month to int if it's a string to properly format it
            month_int = int(month)
            url = f"https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_{year}-{month_int:02d}.parquet"
            filename = f"yellow_tripdata_{year}-{month_int:02d}.parquet"
            
            # Log data access
            self.auditor.log_data_access(
                "data_download",
                "raw_data",
                "data_service",
                {"year": year, "month": f"{month_int:02d}", "url": url}
            )
            
            # Create the local directory if it doesn't exist
            os.makedirs(SHARED_DATA_DIR, exist_ok=True)
            
            # Download the file to MinIO
            response = self._storage_manager_request('/download-file', method='POST', data={
                'file_url': url,
                'object_name': filename,
                'bucket_name': self.raw_data_bucket,
                'local_file_path': f"{SHARED_DATA_DIR}/{filename}"
            })
            
            if response and response.get('status') == 'success':
                logger.info(f"Data for {year}-{month_int:02d} downloaded and stored in MinIO bucket: {self.raw_data_bucket}")
                
                # Perform data quality checks
                try:
                    quality_result = self._perform_data_quality_checks(f"{SHARED_DATA_DIR}/{filename}")
                    
                    # Log quality check result
                    self.auditor.log_data_access(
                        "data_quality_check",
                        "quality_validation",
                        "data_service",
                        {"file": filename, "status": quality_result.get('status', 'fail'), "timestamp": str(datetime.datetime.now().isoformat())}
                    )
                    
                    logger.info(f"Data quality check completed for {SHARED_DATA_DIR}/{filename}: {quality_result.get('status', 'fail')}")
                except Exception as e:
                    logger.error(f"Error performing data quality checks: {str(e)}")
                
                # Return the path to the downloaded file
                local_file_path = f"{SHARED_DATA_DIR}/{filename}"
                logger.info(f"Downloaded data to {local_file_path}")
                return local_file_path
            else:
                logger.error(f"Failed to download data for {year}-{month_int:02d}")
                return None
        except Exception as e:
            logger.error(f"Error downloading parquet file: {str(e)}")
            return None
    
    def _perform_data_quality_checks(self, file_path):
        """
        Perform data quality checks on a dataset.
        
        Args:
            file_path (str): Path to the file to check
            
        Returns:
            dict: Quality check results
        """
        try:
            # Load the data
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
            elif file_path.endswith('.parquet'):
                df = pd.read_parquet(file_path)
            else:
                logger.error(f"Unsupported file format for {file_path}")
                return {'status': 'error', 'message': 'Unsupported file format'}
            
            # Initialize quality check results
            quality_results = {
                'status': 'pass',
                'file_name': os.path.basename(file_path),
                'row_count': len(df),
                'column_count': len(df.columns),
                'checks': [],
                'timestamp': datetime.datetime.now().isoformat()
            }
            
            # Check 1: Missing values
            missing_values = df.isnull().sum().to_dict()
            missing_pct = {col: (count / len(df)) * 100 for col, count in missing_values.items()}
            
            # Flag columns with high missing values
            high_missing_cols = {col: pct for col, pct in missing_pct.items() if pct > 20}
            
            check_result = {
                'check_name': 'missing_values',
                'status': 'fail' if high_missing_cols else 'pass',
                'details': {
                    'high_missing_columns': high_missing_cols,
                    'missing_percentages': missing_pct
                }
            }
            quality_results['checks'].append(check_result)
            
            # Check 2: Data types
            dtypes = df.dtypes.astype(str).to_dict()
            check_result = {
                'check_name': 'data_types',
                'status': 'info',
                'details': {
                    'column_types': dtypes
                }
            }
            quality_results['checks'].append(check_result)
            
            # Check 3: Duplicate rows
            duplicate_count = df.duplicated().sum()
            check_result = {
                'check_name': 'duplicate_rows',
                'status': 'fail' if duplicate_count > 0 else 'pass',
                'details': {
                    'duplicate_count': int(duplicate_count),
                    'duplicate_percentage': (duplicate_count / len(df)) * 100
                }
            }
            quality_results['checks'].append(check_result)
            
            # Check 4: Value ranges for numeric columns
            numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
            range_checks = {}
            
            for col in numeric_cols:
                stats = {
                    'min': float(df[col].min()),
                    'max': float(df[col].max()),
                    'mean': float(df[col].mean()),
                    'median': float(df[col].median()),
                    'std': float(df[col].std())
                }
                
                # Check for outliers (values more than 3 standard deviations from mean)
                if stats['std'] > 0:
                    lower_bound = stats['mean'] - 3 * stats['std']
                    upper_bound = stats['mean'] + 3 * stats['std']
                    outlier_count = ((df[col] < lower_bound) | (df[col] > upper_bound)).sum()
                    stats['outlier_count'] = int(outlier_count)
                    stats['outlier_percentage'] = (outlier_count / len(df)) * 100
                
                range_checks[col] = stats
            
            check_result = {
                'check_name': 'value_ranges',
                'status': 'info',
                'details': range_checks
            }
            quality_results['checks'].append(check_result)
            
            # Update overall status
            fail_checks = [check for check in quality_results['checks'] if check['status'] == 'fail']
            if fail_checks:
                quality_results['status'] = 'fail'
                quality_results['failed_checks'] = [check['check_name'] for check in fail_checks]
            
            # Log quality check results for audit purposes
            self.auditor.log_data_access(
                "data_quality_check",
                "quality_validation",
                "data_service",
                {"file": os.path.basename(file_path), "status": quality_results['status'], "timestamp": quality_results['timestamp']}
            )
            
            logger.info(f"Data quality check completed for {file_path}: {quality_results['status']}")
            return quality_results
            
        except Exception as e:
            logger.error(f"Error performing data quality checks: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def build_features(self, year=None, month=None):
        """
        Build features from raw data.
        
        Args:
            year (str, optional): Year to process data for
            month (str, optional): Month to process data for
        
        Returns:
            list: List of processed files
        """
        try:
            # If year and month are not provided, use default
            if not year or not month:
                year = "2023"
                month = "01"
                logger.info(f"No parameters provided, using default: {year}-{month}")
            
            logger.info(f"Processing data for {year}-{month}")
            
            # Download the data if not already available
            file_path = self.download_parquet_file(year, month)
            
            if not file_path or not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}")
                raise FileNotFoundError(f"File not found: {file_path}")
            
            logger.info(f"Downloaded data to {file_path}")
            logger.info(f"Processing file: {os.path.basename(file_path)}")
            
            # Read the data
            df = pd.read_parquet(file_path)
            
            # Engineer features
            processed_df = self._engineer_features(df)
            
            # Save processed data to MinIO
            processed_file_name = f"processed_{os.path.basename(file_path)}"
            processed_file_path = f"{SHARED_DATA_DIR}/{processed_file_name}"
            
            # Save to local file first
            processed_df.to_parquet(processed_file_path)
            
            # Upload to MinIO
            upload_response = self._storage_manager_request('/upload-file', method='POST', data={
                'local_file_path': processed_file_path,
                'object_name': processed_file_name,
                'bucket_name': self.processed_data_bucket
            })
            
            if not upload_response or upload_response.get('status') != 'success':
                logger.error("Failed to upload processed data to MinIO")
                return []
            
            logger.info(f"Processed data saved to MinIO bucket: {self.processed_data_bucket}")
            
            # Split data into train/test sets and save
            train_object, test_object = self._split_and_save_data(processed_df, processed_file_name)
            
            if not train_object or not test_object:
                logger.error("Failed to split and save train/test data")
                return []
            
            # Clean up local file
            os.remove(processed_file_path)
            
            # Return list of processed files
            return [processed_file_name]
        except Exception as e:
            logger.error(f"Error in build_features: {str(e)}")
            raise Exception(f"Error building features: {str(e)}")

    def _engineer_features(self, df):
        """
        Perform feature engineering on the dataset.
        
        Args:
            df (pandas.DataFrame): Raw data
            
        Returns:
            pandas.DataFrame: Processed data with engineered features
        """
        # Handle missing values
        df = df.fillna({
            'passenger_count': 0,
            'trip_distance': 0,
            'fare_amount': 0,
            'tip_amount': 0,
            'total_amount': 0
        })
        
        # Create time-based features
        if 'tpep_pickup_datetime' in df.columns:
            df['pickup_hour'] = df['tpep_pickup_datetime'].dt.hour
            df['pickup_day'] = df['tpep_pickup_datetime'].dt.day
            df['pickup_month'] = df['tpep_pickup_datetime'].dt.month
            df['pickup_weekday'] = df['tpep_pickup_datetime'].dt.weekday
            
            # Calculate trip duration in minutes
            if 'tpep_dropoff_datetime' in df.columns:
                df['trip_duration'] = (df['tpep_dropoff_datetime'] - df['tpep_pickup_datetime']).dt.total_seconds() / 60
                
                # Remove outliers (trips longer than 24 hours or negative duration)
                df = df[(df['trip_duration'] >= 0) & (df['trip_duration'] <= 24 * 60)]
        
        # Create fare features
        if 'fare_amount' in df.columns and 'trip_distance' in df.columns:
            # Fare per mile (avoid division by zero)
            df['fare_per_mile'] = df.apply(
                lambda row: row['fare_amount'] / row['trip_distance'] if row['trip_distance'] > 0 else 0, 
                axis=1
            )
        
        # Create tip features
        if 'tip_amount' in df.columns and 'fare_amount' in df.columns:
            # Tip percentage (avoid division by zero)
            df['tip_percentage'] = df.apply(
                lambda row: (row['tip_amount'] / row['fare_amount']) * 100 if row['fare_amount'] > 0 else 0,
                axis=1
            )
        
        return df
    
    def _split_and_save_data(self, df, file_name):
        """
        Split data into training and testing sets and save to MinIO.
        
        Args:
            df (DataFrame): Processed data
            file_name (str): Name of the original file
        
        Returns:
            tuple: (train_object_name, test_object_name) if successful, (None, None) otherwise
        """
        try:
            # Split data into train/test sets (80/20)
            train_df = df.sample(frac=0.8, random_state=42)
            test_df = df.drop(train_df.index)
            
            logger.info(f"Data split into train ({len(train_df)} rows) and test ({len(test_df)} rows) sets")
            
            # Save to local files
            train_file_name = f"train_{file_name}"
            test_file_name = f"test_{file_name}"
            
            train_file_path = f"{SHARED_DATA_DIR}/{train_file_name}"
            test_file_path = f"{SHARED_DATA_DIR}/{test_file_name}"
            
            train_df.to_parquet(train_file_path)
            test_df.to_parquet(test_file_path)
            
            # Upload train data to MinIO
            train_object_name = train_file_name
            train_success = self._storage_manager_request('/upload-file', method='POST', data={
                'local_file_path': train_file_path,
                'object_name': train_object_name,
                'bucket_name': f"{self.raw_data_bucket}-train"
            })
            
            # Upload test data to MinIO
            test_object_name = test_file_name
            test_success = self._storage_manager_request('/upload-file', method='POST', data={
                'local_file_path': test_file_path,
                'object_name': test_object_name,
                'bucket_name': f"{self.raw_data_bucket}-test"
            })
            
            # Clean up temporary files
            os.remove(train_file_path)
            os.remove(test_file_path)
            
            if train_success and test_success:
                logger.info(f"Data split and saved to train/test buckets")
                return (train_object_name, test_object_name)
            else:
                logger.error(f"Failed to upload train/test data to MinIO")
                return (None, None)
                
        except Exception as e:
            logger.error(f"Error in _split_and_save_data: {str(e)}")
            return (None, None)

    def anonymize_data(self, object_name, bucket_name=None):
        """
        Anonymize data for GDPR compliance.
        
        Args:
            object_name (str): Name of the object to anonymize
            bucket_name (str, optional): Bucket name containing the object
            
        Returns:
            str: Name of the anonymized object if successful, None otherwise
        """
        try:
            bucket = bucket_name or self.raw_data_bucket
            
            # Create a temporary directory for processing
            os.makedirs(SHARED_DATA_DIR, exist_ok=True)
            
            # Download the file from MinIO
            local_file_path = f"{SHARED_DATA_DIR}/{object_name}"
            
            # Check if we can download the file
            result = self._storage_manager_request('/download-file', method='POST', data={
                'object_name': object_name,
                'bucket_name': bucket,
                'local_file_path': local_file_path
            })
            
            if not result or result.get('status') != 'success':
                logger.error(f"Failed to download {object_name} from MinIO")
                return {'status': 'error', 'message': 'Failed to download file from MinIO'}
            
            # Load the data
            if object_name.endswith('.csv'):
                df = pd.read_csv(local_file_path)
            elif object_name.endswith('.parquet'):
                df = pd.read_parquet(local_file_path)
            else:
                logger.error(f"Unsupported file format for {object_name}")
                return None

            # Identify PII columns (for NYC taxi data example)
            pii_columns = []
            
            # Check for common PII column names
            potential_pii_columns = [
                'vendor_id', 'driver_id', 'passenger_id', 'medallion', 'hack_license',
                'vendor_name', 'rate_code_id', 'store_and_fwd_flag', 'payment_type',
                'name', 'email', 'phone', 'address', 'license'
            ]
            
            for col in potential_pii_columns:
                if col in df.columns:
                    pii_columns.append(col)
            
            # Log PII columns found
            self.auditor.log_data_access(
                "gdpr_anonymization",
                "data_anonymization",
                "data_service",
                {"object_name": object_name, "pii_columns": pii_columns}
            )
            
            # Anonymize PII columns
            for col in pii_columns:
                if col in df.columns:
                    # Different anonymization techniques based on data type
                    if df[col].dtype == 'object':  # String columns
                        # Hash the values
                        df[col] = df[col].apply(lambda x: f"ANONYMIZED_{hash(str(x)) % 10000}" if pd.notna(x) else x)
                    else:  # Numeric columns
                        # Add noise or binning for numeric columns
                        if df[col].nunique() > 10:  # Many unique values, add noise
                            mean = df[col].mean()
                            std = df[col].std() if df[col].std() > 0 else 1
                            df[col] = df[col] + np.random.normal(0, std * 0.1, size=len(df))
                        else:  # Few unique values, use binning
                            df[col] = pd.qcut(df[col], 5, labels=False, duplicates='drop')
            
            # Save anonymized data
            anonymized_object_name = f"anonymized_{object_name}"
            anonymized_file_path = f"{SHARED_DATA_DIR}/{anonymized_object_name}"
            
            if object_name.endswith('.csv'):
                df.to_csv(anonymized_file_path, index=False)
            elif object_name.endswith('.parquet'):
                df.to_parquet(anonymized_file_path)
            
            # Upload anonymized data to MinIO
            anonymized_bucket = f"{bucket}-anonymized"
            
            # Ensure anonymized bucket exists
            if not self._storage_manager_request('/bucket-exists', params={
                'bucket_name': anonymized_bucket
            }):
                self._storage_manager_request('/create-bucket', method='POST', data={
                    'bucket_name': anonymized_bucket
                })
            
            # Upload anonymized data
            if self._storage_manager_request('/upload-file', method='POST', data={
                'local_file_path': anonymized_file_path,
                'object_name': anonymized_object_name,
                'bucket_name': anonymized_bucket
            }):
                logger.info(f"Data anonymized successfully: {anonymized_object_name}")
                return anonymized_object_name
            else:
                logger.error(f"Failed to upload anonymized data to MinIO")
                return None
            
            # Clean up temporary files
            os.remove(local_file_path)
            os.remove(anonymized_file_path)
            
        except Exception as e:
            logger.error(f"Error anonymizing data: {str(e)}")
            return None
    
    def create_dataset_version(self, object_name, bucket_name=None, version_tag=None):
        """
        Create a versioned copy of a dataset.
        
        Args:
            object_name (str): Name of the object to version
            bucket_name (str, optional): Bucket name containing the object
            version_tag (str, optional): Tag to use for the version. If None, a timestamp will be used.
            
        Returns:
            str: Name of the versioned object if successful, None otherwise
        """
        try:
            bucket = bucket_name or self.raw_data_bucket
            
            # Log version creation for audit purposes
            self.auditor.log_data_access(
                "dataset_versioning",
                "create_version",
                "data_service",
                {"object_name": object_name, "bucket": bucket, "version_tag": version_tag}
            )
            
            # Create version via storage manager
            result = self._storage_manager_request('/create-version', method='POST', data={
                'object_name': object_name,
                'bucket_name': bucket,
                'version_tag': version_tag
            })
            
            if result and result.get('status') == 'success':
                versioned_object = result.get('versioned_object_name')
                logger.info(f"Created version of {object_name}: {versioned_object}")
                return versioned_object
            else:
                logger.error(f"Failed to create version of {object_name}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating dataset version: {str(e)}")
            return None
    
    def process_monthly_data(self, years_months=None):
        """
        Process monthly NYC taxi data, integrating it into a consolidated dataset.
        
        Args:
            years_months (list, optional): List of (year, month) tuples to process.
                                          If None, processes the last two available months.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # If no specific months provided, determine the last two full months
            if not years_months:
                from datetime import datetime
                today = datetime.today()
                current_month = today.month
                current_year = today.year - 1  # Using previous year to ensure data availability
                
                # Determine the last two full months
                if current_month in [1, 2]:
                    year1, month1 = current_year - 1, 12 if current_month == 1 else 11
                    year2, month2 = current_year - 1, 11 if current_month == 1 else 10
                else:
                    year1, month1 = current_year, current_month - 1
                    year2, month2 = current_year, current_month - 2
                
                years_months = [(str(year1), str(month1).zfill(2)), (str(year2), str(month2).zfill(2))]
            
            logger.info(f"Processing data for months: {years_months}")
            
            # Process each month
            consolidated_object = "nyc_taxi_consolidated.parquet"
            success_count = 0
            
            for year, month in years_months:
                try:
                    # Download the data from external source to MinIO
                    object_name = f"yellow_tripdata_{year}-{month}.parquet"
                    
                    # Check if the object already exists in MinIO
                    if not self._storage_manager_request('/object-exists', params={
                        'object_name': object_name,
                        'bucket_name': self.raw_data_bucket
                    }):
                        # Download from external source
                        logger.info(f"Downloading data for {year}-{month} from external source")
                        result = self.download_parquet_file(year, month)
                        if not result:
                            logger.error(f"Failed to download data for {year}-{month}")
                            continue
                    else:
                        logger.info(f"Data for {year}-{month} already exists in MinIO")
                    
                    # Integrate the data
                    logger.info(f"Integrating data for {year}-{month} into consolidated dataset")
                    result = self._storage_manager_request('/integrate-data', method='POST', data={
                        'new_data_object': object_name,
                        'consolidated_object': consolidated_object,
                        'sample_fraction': 0.01,
                        'months_to_keep': 6,
                        'bucket_name': self.raw_data_bucket
                    })
                    
                    if result and result.get('status') == 'success':
                        logger.info(f"Successfully integrated data for {year}-{month}")
                        success_count += 1
                    else:
                        logger.error(f"Failed to integrate data for {year}-{month}")
                
                except Exception as e:
                    logger.error(f"Error processing data for {year}-{month}: {str(e)}")
            
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Error in process_monthly_data: {str(e)}")
            return False
    
    def run_quality_check(self, object_name, bucket_name=None):
        """
        Run quality checks on a dataset in MinIO.
        
        Args:
            object_name (str): Name of the object to check
            bucket_name (str, optional): Bucket name containing the object
            
        Returns:
            dict: Quality check results
        """
        try:
            bucket = bucket_name or self.raw_data_bucket
            
            # Create a temporary directory for processing
            os.makedirs(SHARED_DATA_DIR, exist_ok=True)
            
            # Download the file from MinIO
            local_file_path = f"{SHARED_DATA_DIR}/{object_name}"
            
            # Check if we can download the file
            result = self._storage_manager_request('/download-file', method='POST', data={
                'object_name': object_name,
                'bucket_name': bucket,
                'local_file_path': local_file_path
            })
            
            if not result or result.get('status') != 'success':
                logger.error(f"Failed to download {object_name} from MinIO")
                return {'status': 'error', 'message': 'Failed to download file from MinIO'}
            
            # Run quality checks
            quality_results = self._perform_data_quality_checks(local_file_path)
            
            # Clean up
            os.remove(local_file_path)
            
            return quality_results
            
        except Exception as e:
            logger.error(f"Error running quality check: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    def set_data_retention_policy(self, bucket_name, prefix='', days=30):
        """
        Set a data retention policy for a bucket.
        
        Args:
            bucket_name (str): The bucket to set the policy for
            prefix (str, optional): Prefix filter for the policy
            days (int, optional): Number of days to retain data
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Log policy creation for audit purposes
            self.auditor.log_data_access(
                "retention_policy",
                "lifecycle_management",
                "data_service",
                {"bucket": bucket_name, "prefix": prefix, "days": days}
            )
            
            # Set policy via storage manager
            result = self._storage_manager_request('/set-lifecycle-policy', method='POST', data={
                'bucket_name': bucket_name,
                'prefix': prefix,
                'days': days
            })
            
            if result and result.get('status') == 'success':
                logger.info(f"Set retention policy for bucket {bucket_name}: {days} days")
                return True
            else:
                logger.error(f"Failed to set retention policy for bucket {bucket_name}")
                return False
                
        except Exception as e:
            logger.error(f"Error setting data retention policy: {str(e)}")
            return False
    
    def get_data_retention_policy(self, bucket_name):
        """
        Get the current data retention policy for a bucket.
        
        Args:
            bucket_name (str): The bucket to get the policy for
            
        Returns:
            dict: The policy if successful, None otherwise
        """
        try:
            # Log policy retrieval for audit purposes
            self.auditor.log_data_access(
                "retention_policy",
                "lifecycle_management",
                "data_service",
                {"bucket": bucket_name, "action": "get"}
            )
            
            # Get policy via storage manager
            result = self._storage_manager_request('/get-lifecycle-policy', params={
                'bucket': bucket_name
            })
            
            if result and result.get('status') == 'success':
                logger.info(f"Retrieved retention policy for bucket {bucket_name}")
                return result.get('policy')
            else:
                logger.error(f"Failed to get retention policy for bucket {bucket_name}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting data retention policy: {str(e)}")
            return None

class DataServiceHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the unified data service."""
    
    # Class-level attribute for the data service
    data_service = DataService()
    
    def _set_headers(self, status_code=200):
        """Set response headers."""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
    
    def do_GET(self):
        """Handle GET requests."""
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        
        if path == "/health":
            # Health check endpoint
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            response = {
                'status': 'healthy',
                'service': 'data-service',
                'timestamp': datetime.datetime.now().isoformat()
            }
            
            self.wfile.write(json.dumps(response).encode())
        elif self.path == '/features/health':
            # Feature engineering health check endpoint (for backward compatibility)
            self._set_headers()
            self.wfile.write(json.dumps({'status': 'healthy'}).encode())
        elif self.path == "/process-monthly-data":
            try:
                # Process monthly data
                result = self.data_service.process_monthly_data()
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                
                response = {
                    'status': 'success' if result else 'error',
                    'message': 'Monthly data processed successfully' if result else 'Failed to process monthly data'
                }
                
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                logger.error(f"Error processing monthly data: {str(e)}")
                self.send_error(500, f"Error processing monthly data: {str(e)}")
        elif self.path.startswith("/anonymize-data"):
            try:
                # Parse query parameters
                query_params = parse_qs(parsed_url.query)
                object_name = query_params.get('object', [''])[0]
                bucket_name = query_params.get('bucket', [''])[0] or None
                
                if not object_name:
                    self.send_error(400, "Missing required parameter: object")
                    return
                
                # Anonymize data
                result = self.data_service.anonymize_data(object_name, bucket_name)
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                
                if result:
                    response = {
                        'status': 'success',
                        'message': 'Data anonymized successfully',
                        'anonymized_object': result,
                        'anonymized_bucket': f"{bucket_name or self.data_service.raw_data_bucket}-anonymized"
                    }
                else:
                    response = {
                        'status': 'error',
                        'message': 'Failed to anonymize data'
                    }
                
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                logger.error(f"Error anonymizing data: {str(e)}")
                self.send_error(500, f"Error anonymizing data: {str(e)}")
        elif self.path.startswith("/create-dataset-version"):
            try:
                # Parse query parameters
                query_params = parse_qs(parsed_url.query)
                object_name = query_params.get('object', [''])[0]
                bucket_name = query_params.get('bucket', [''])[0] or None
                version_tag = query_params.get('version', [''])[0] or None
                
                if not object_name:
                    self.send_error(400, "Missing required parameter: object")
                    return
                
                # Create dataset version
                result = self.data_service.create_dataset_version(object_name, bucket_name, version_tag)
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                
                if result:
                    response = {
                        'status': 'success',
                        'message': 'Dataset version created successfully',
                        'versioned_object': result
                    }
                else:
                    response = {
                        'status': 'error',
                        'message': 'Failed to create dataset version'
                    }
                
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                logger.error(f"Error creating dataset version: {str(e)}")
                self.send_error(500, f"Error creating dataset version: {str(e)}")
        elif self.path.startswith("/run-quality-check"):
            try:
                # Parse query parameters
                query_params = parse_qs(parsed_url.query)
                object_name = query_params.get('object', [''])[0]
                bucket_name = query_params.get('bucket', [''])[0] or None
                
                if not object_name:
                    self.send_error(400, "Missing required parameter: object")
                    return
                
                # Run quality check
                result = self.data_service.run_quality_check(object_name, bucket_name)
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                
                self.wfile.write(json.dumps(result).encode())
            except Exception as e:
                logger.error(f"Error running quality check: {str(e)}")
                self.send_error(500, f"Error running quality check: {str(e)}")
        elif self.path.startswith("/set-data-retention-policy"):
            try:
                # Parse query parameters
                query_params = parse_qs(parsed_url.query)
                bucket_name = query_params.get('bucket', [''])[0]
                prefix = query_params.get('prefix', [''])[0]
                days = int(query_params.get('days', [30])[0])
                
                if not bucket_name:
                    self.send_error(400, "Missing required parameter: bucket")
                    return
                
                # Set data retention policy
                result = self.data_service.set_data_retention_policy(bucket_name, prefix, days)
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                
                if result:
                    response = {
                        'status': 'success',
                        'message': 'Data retention policy set successfully'
                    }
                else:
                    response = {
                        'status': 'error',
                        'message': 'Failed to set data retention policy'
                    }
                
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                logger.error(f"Error setting data retention policy: {str(e)}")
                self.send_error(500, f"Error setting data retention policy: {str(e)}")
        elif self.path.startswith("/get-data-retention-policy"):
            try:
                # Parse query parameters
                query_params = parse_qs(parsed_url.query)
                bucket_name = query_params.get('bucket', [''])[0]
                
                if not bucket_name:
                    self.send_error(400, "Missing required parameter: bucket")
                    return
                
                # Get data retention policy
                result = self.data_service.get_data_retention_policy(bucket_name)
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                
                self.wfile.write(json.dumps(result).encode())
            except Exception as e:
                logger.error(f"Error getting data retention policy: {str(e)}")
                self.send_error(500, f"Error getting data retention policy: {str(e)}")
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        """Handle POST requests."""
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        
        if path == "/process-data":
            try:
                # Get content length
                content_length = int(self.headers.get('Content-Length', 0))
                
                # Handle empty request (no parameters provided)
                if content_length == 0:
                    year = "2023"
                    month = "01"
                    logger.info(f"No parameters provided, using default: {year}-{month}")
                else:
                    # Parse request body
                    post_data = self.rfile.read(content_length).decode('utf-8')
                    try:
                        data = json.loads(post_data)
                        year = data.get('year')
                        month = data.get('month')
                    except json.JSONDecodeError:
                        # Handle form data
                        form_data = parse_qs(post_data)
                        year = form_data.get('year', ['2023'])[0]
                        month = form_data.get('month', ['01'])[0]
                
                # Download data
                logger.info(f"Processing data for {year}-{month}")
                
                # Step 1: Download raw data
                try:
                    local_file_path = self.data_service.download_parquet_file(year, month)
                    logger.info(f"Downloaded data to {local_file_path}")
                except Exception as e:
                    logger.error(f"Error downloading data: {str(e)}")
                    self.send_error(500, f"Error downloading data: {str(e)}")
                    return
                
                # Step 2: Build features
                try:
                    processed_files = self.data_service.build_features(year, month)
                    if not processed_files:
                        logger.error("No files were processed")
                        self.send_error(500, "No files were processed")
                        return
                    logger.info(f"Processed {len(processed_files)} files")
                except Exception as e:
                    logger.error(f"Error building features: {str(e)}")
                    self.send_error(500, f"Error building features: {str(e)}")
                    return
                
                # Step 3: Load processed data for splitting
                try:
                    # Get the processed file name
                    processed_file = processed_files[0]
                    
                    # Create a temporary directory for processing
                    os.makedirs(SHARED_DATA_DIR, exist_ok=True)
                    
                    # Download the processed file from MinIO
                    processed_local_path = f"{SHARED_DATA_DIR}/{processed_file}"
                    if self.data_service._storage_manager_request('/download-file', method='POST', data={
                        'object_name': processed_file,
                        'bucket_name': self.data_service.processed_data_bucket,
                        'local_file_path': processed_local_path
                    }):
                        # Load the processed data
                        df = pd.read_parquet(processed_local_path)
                        
                        # Split and save train/test data
                        train_object, test_object = self.data_service._split_and_save_data(df, processed_file)
                        
                        if not train_object or not test_object:
                            logger.error("Failed to split and save train/test data")
                            self.send_error(500, "Failed to split and save train/test data")
                            return
                        
                        # Clean up temporary file
                        os.remove(processed_local_path)
                        
                    else:
                        logger.error(f"Failed to download processed file from MinIO")
                        self.send_error(500, "Failed to download processed file from MinIO")
                        return
                    
                except Exception as e:
                    logger.error(f"Error splitting data: {str(e)}")
                    self.send_error(500, f"Error splitting data: {str(e)}")
                    return
                
                # Send success response
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                
                response = {
                    'status': 'success',
                    'message': f'Data processed successfully for {year}-{month}',
                    'processed_files': processed_files,
                    'train_data': train_object,
                    'test_data': test_object
                }
                
                self.wfile.write(json.dumps(response).encode())
                
            except Exception as e:
                logger.error(f"Error processing data: {str(e)}")
                self.send_error(500, f"Error processing data: {str(e)}")
        else:
            self.send_error(404, "Not Found")

def start_server(port=8000):
    """Start the HTTP server for the data service."""
    server = HTTPServer(('0.0.0.0', port), DataServiceHandler)
    logger.info(f"Starting unified data service on port {port}")
    server.serve_forever()

if __name__ == "__main__":
    try:
        start_server(port=8000)
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
        sys.exit(0)
