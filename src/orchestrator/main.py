"""
Orchestrator for the NYC Taxi MLOps pipeline.
Coordinates data ingestion, feature engineering, model training, and monitoring.
"""
import os
import time
import logging
import requests
from datetime import datetime
import sys

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    MINIO_ENDPOINT,
    MINIO_ROOT_USER,
    MINIO_ROOT_PASSWORD,
    MINIO_BUCKET,
    DATA_SERVICE_URL,
    TRAINING_SERVICE_URL,
    MONITORING_SERVICE_URL,
    MLFLOW_TRACKING_URI,
    HEALTH_CHECK_RETRIES,
    HEALTH_CHECK_INTERVAL,
    CONSOLIDATED_FILE_NAME,
    DEFAULT_YEAR,
    DEFAULT_MONTH,
    STORAGE_MANAGER_URL
)

from monitoring.audit import DataAuditor
from storage_manager.manager import StorageManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Service endpoints
DATA_SERVICE_ENDPOINT = DATA_SERVICE_URL
FEATURE_SERVICE_ENDPOINT = DATA_SERVICE_URL  # Feature engineering runs on data_service
TRAINING_SERVICE_ENDPOINT = TRAINING_SERVICE_URL
MONITORING_SERVICE_ENDPOINT = MONITORING_SERVICE_URL

class MLOpsOrchestrator:
    """Orchestrates the MLOps pipeline components."""
    
    def __init__(self):
        """Initialize the orchestrator with required services."""
        self.storage_manager = None
        self.auditor = None
        
        # Initialize services only after health checks
        logger.info("Orchestrator initialized. Services will be connected after health checks.")
    
    def check_service_health(self, service_name, url, max_retries=HEALTH_CHECK_RETRIES, retry_interval=HEALTH_CHECK_INTERVAL):
        """
        Check if a service is healthy by making a request to its health endpoint.
        
        Args:
            service_name: Name of the service to check
            url: URL to check for health
            max_retries: Maximum number of retry attempts
            retry_interval: Time in seconds between retries
            
        Returns:
            bool: True if service is healthy, False otherwise
        """
        logger.info(f"Checking health of {service_name} at {url}")
        
        for attempt in range(max_retries):
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    logger.info(f"{service_name} is healthy")
                    return True
                else:
                    logger.warning(f"{service_name} returned status code {response.status_code}")
            except requests.RequestException as e:
                logger.warning(f"Attempt {attempt+1}/{max_retries}: {service_name} health check failed: {str(e)}")
            
            if attempt < max_retries - 1:
                logger.info(f"Waiting {retry_interval} seconds before next retry...")
                time.sleep(retry_interval)
        
        logger.error(f"{service_name} health check failed after {max_retries} attempts")
        return False
    
    def check_minio_health(self, max_retries=HEALTH_CHECK_RETRIES, retry_interval=HEALTH_CHECK_INTERVAL):
        """Check if MinIO is healthy."""
        # Extract host and port from MINIO_ENDPOINT
        endpoint = MINIO_ENDPOINT.replace('http://', '').replace('https://', '')
        if ':' in endpoint:
            host, port = endpoint.split(':')
        else:
            host, port = endpoint, '9000'
        
        health_url = f"http://{host}:{port}/minio/health/live"
        return self.check_service_health("MinIO", health_url, max_retries, retry_interval)
    
    def check_mlflow_health(self, max_retries=HEALTH_CHECK_RETRIES, retry_interval=HEALTH_CHECK_INTERVAL):
        """Check if MLflow is healthy."""
        mlflow_url = MLFLOW_TRACKING_URI
        return self.check_service_health("MLflow", mlflow_url, max_retries, retry_interval)
    
    def check_data_service_health(self, max_retries=HEALTH_CHECK_RETRIES, retry_interval=HEALTH_CHECK_INTERVAL):
        """Check if the data service is healthy."""
        return self.check_service_health("Data Service", f"{DATA_SERVICE_ENDPOINT}/health", max_retries, retry_interval)
    
    def check_feature_service_health(self, max_retries=HEALTH_CHECK_RETRIES, retry_interval=HEALTH_CHECK_INTERVAL):
        """Check if the feature service is healthy"""
        return self.check_service_health("Feature Service", f"{FEATURE_SERVICE_ENDPOINT}/health", max_retries, retry_interval)
    
    def check_storage_manager_health(self, max_retries=HEALTH_CHECK_RETRIES, retry_interval=HEALTH_CHECK_INTERVAL):
        """Check if the storage manager service is healthy"""
        return self.check_service_health("Storage Manager", f"{STORAGE_MANAGER_URL}/health", max_retries, retry_interval)
    
    def check_monitoring_service_health(self, max_retries=HEALTH_CHECK_RETRIES, retry_interval=HEALTH_CHECK_INTERVAL):
        """Check if the monitoring service is healthy"""
        return self.check_service_health("Monitoring Service", f"{MONITORING_SERVICE_ENDPOINT}/health", max_retries, retry_interval)
    
    def check_training_service_health(self, max_retries=HEALTH_CHECK_RETRIES, retry_interval=HEALTH_CHECK_INTERVAL):
        """Check if the training service is healthy."""
        return self.check_service_health("Training Service", f"{TRAINING_SERVICE_ENDPOINT}/health", max_retries, retry_interval)
    
    def initialize_services(self):
        """Initialize all services after health checks."""
        try:
            # Initialize storage manager
            self.storage_manager = StorageManager(
                endpoint=MINIO_ENDPOINT,
                access_key=MINIO_ROOT_USER,
                secret_key=MINIO_ROOT_PASSWORD,
                bucket_name=MINIO_BUCKET
            )
            
            # Initialize auditor
            self.auditor = DataAuditor()
            
            # Log orchestrator initialization
            self.auditor.log_data_access(
                "orchestrator_init",
                "pipeline",
                "orchestrator",
                {"status": "initialized", "timestamp": datetime.now().isoformat()}
            )
            
            logger.info("All services initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize services: {str(e)}")
            return False

    def run_data_pipeline(self, year=None, month=None):
        """Run the data ingestion and feature engineering pipeline.
        
        Args:
            year (str, optional): Year to process data for. Defaults to value from config.
            month (str, optional): Month to process data for. Defaults to value from config.
            
        Returns:
            tuple: (success, train_file, test_file) where success is a boolean indicating
                  if the pipeline completed successfully, and train_file and test_file
                  are the names of the generated training and test files.
        """
        try:
            # Use provided values or defaults
            year = year or DEFAULT_YEAR
            month = month or DEFAULT_MONTH
            
            # Start data pipeline
            self.auditor.log_data_access(
                "pipeline_start",
                "data_pipeline",
                "orchestrator",
                {"component": "data_ingestion"}
            )
            
            # Prepare request data with year and month
            request_data = {
                "year": year,
                "month": month
            }
            
            # Run data ingestion service via HTTP request
            logger.info(f"Delegating data ingestion to data-service for {year}-{month}")
            response = requests.post(
                f"{DATA_SERVICE_ENDPOINT}/process-data", 
                json=request_data,
                timeout=300
            )
            if response.status_code != 200:
                raise Exception(f"Data ingestion failed with status code {response.status_code}: {response.text}")
            
            data_response = response.json()
            logger.info(f"Data ingestion completed with response: {data_response}")
            
            # Check GDPR compliance - use the correct file name from config
            compliance_report = self.auditor.check_gdpr_compliance(
                CONSOLIDATED_FILE_NAME
            )
            if not compliance_report["compliant"]:
                logger.warning(f"GDPR compliance issues: {compliance_report}")
                # Continue anyway since this is just a warning
            
            # Run feature engineering via HTTP request
            logger.info(f"Delegating feature engineering to feature-service for {year}-{month}")
            response = requests.post(
                f"{FEATURE_SERVICE_ENDPOINT}/process-data", 
                json=request_data,  # Pass the same request_data with year and month
                timeout=300
            )
            if response.status_code != 200:
                raise Exception(f"Feature engineering failed with status code {response.status_code}: {response.text}")
            
            feature_response = response.json()
            logger.info(f"Feature engineering completed with response: {feature_response}")
            
            # Extract train and test file names from the response
            train_file = feature_response.get('train_data') or data_response.get('train_data')
            test_file = feature_response.get('test_data') or data_response.get('test_data')
            
            if not train_file or not test_file:
                logger.warning("Train or test file names not found in feature engineering response")
            else:
                logger.info(f"Extracted train file: {train_file}, test file: {test_file}")
            
            # Log pipeline completion
            self.auditor.log_data_access(
                "pipeline_complete",
                "data_pipeline",
                "orchestrator",
                {"status": "success", "timestamp": datetime.now().isoformat()}
            )
            
            return True, train_file, test_file
            
        except requests.RequestException as e:
            logger.error(f"Data pipeline failed due to request error: {str(e)}")
            self.auditor.log_data_access(
                "pipeline_error",
                "data_pipeline",
                "orchestrator",
                {"error": str(e), "timestamp": datetime.now().isoformat()}
            )
            return False, None, None
        except Exception as e:
            logger.error(f"Data pipeline failed: {str(e)}")
            self.auditor.log_data_access(
                "pipeline_error",
                "data_pipeline",
                "orchestrator",
                {"error": str(e), "timestamp": datetime.now().isoformat()}
            )
            return False, None, None

    def run_training_pipeline(self, train_file=None, test_file=None):
        """Run the model training pipeline.
        
        Args:
            train_file: Optional name of the training file
            test_file: Optional name of the test file
            
        Returns:
            Tuple of (success, metrics)
        """
        try:
            logger.info("Starting model training pipeline")
            
            # Prepare request data
            request_data = {
                "train_file": train_file,
                "test_file": test_file,
                "sample_size": 100000  # Use sample for faster training
            }
            
            # Log training request
            self.auditor.log_data_access(
                "training_request",
                "model_training",
                "orchestrator",
                request_data
            )
            
            # Send request to training service
            logger.info(f"Sending training request to {TRAINING_SERVICE_URL}/train")
            response = requests.post(
                f"{TRAINING_SERVICE_URL}/train",
                json=request_data,
                timeout=1800  # 30 minutes timeout for large datasets
            )
            
            # Check response
            if response.status_code != 200:
                logger.error(f"Training service returned error: {response.status_code} - {response.text}")
                self.auditor.log_data_access(
                    "training_error",
                    "model_training",
                    "orchestrator",
                    {"error": f"Training service returned {response.status_code}", "response": response.text}
                )
                return False, None
            
            # Parse response
            try:
                response_data = response.json()
                if response_data.get("status") != "success":
                    logger.error(f"Training service reported failure: {response_data}")
                    self.auditor.log_data_access(
                        "training_error",
                        "model_training",
                        "orchestrator",
                        {"error": "Training service reported failure", "response": response_data}
                    )
                    return False, None
                
                # Extract metrics
                metrics = response_data.get("metrics", {})
                
                # Log training success
                logger.info(f"Model training completed successfully with metrics: {metrics}")
                self.auditor.log_data_access(
                    "training_success",
                    "model_training",
                    "orchestrator",
                    {"metrics": metrics}
                )
                
                return True, metrics
                
            except ValueError as e:
                logger.error(f"Error parsing training service response: {e}")
                self.auditor.log_data_access(
                    "training_error",
                    "model_training",
                    "orchestrator",
                    {"error": f"Error parsing response: {str(e)}", "response": response.text}
                )
                return False, None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error communicating with training service: {e}")
            self.auditor.log_data_access(
                "training_error",
                "model_training",
                "orchestrator",
                {"error": f"Communication error: {str(e)}"}
            )
            return False, None
            
        except Exception as e:
            logger.error(f"Unexpected error in training pipeline: {e}")
            self.auditor.log_data_access(
                "training_error",
                "model_training",
                "orchestrator",
                {"error": f"Unexpected error: {str(e)}"}
            )
            return False, None

    def generate_reports(self):
        """Generate monitoring and compliance reports."""
        try:
            # Generate audit report via monitoring service
            logger.info("Delegating report generation to monitoring service")
            response = requests.post(f"{MONITORING_SERVICE_ENDPOINT}/generate-report", timeout=300)
            if response.status_code != 200:
                raise Exception(f"Report generation failed with status code {response.status_code}: {response.text}")
            
            logger.info(f"Report generation completed with response: {response.json()}")
            
            # Log report generation
            self.auditor.log_data_access(
                "report_generation",
                "reports",
                "orchestrator",
                {
                    "report_type": "audit",
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            return True
            
        except requests.RequestException as e:
            logger.error(f"Report generation failed due to request error: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Report generation failed: {str(e)}")
            return None

    def run_pipeline(self):
        """Run the complete MLOps pipeline from data ingestion to model training."""
        start_time = time.time()
        success = False
        retry_count = 0
        max_retries = 3
        
        while not success and retry_count < max_retries:
            try:
                # Start pipeline
                logger.info("Starting MLOps pipeline")
                
                # Check service health
                logger.info("Checking service health...")
                all_healthy = self._check_service_health()
                if not all_healthy:
                    raise Exception("Not all services are healthy")
                
                # Initialize services
                logger.info("Initializing services...")
                self._initialize_services()
                logger.info("All services initialized successfully")
                
                # Log pipeline start
                self.auditor.log_data_access(
                    "pipeline_start",
                    "data_pipeline",
                    "orchestrator",
                    {"component": "data_ingestion"}
                )
                
                # Run data pipeline
                logger.info("Delegating data ingestion to data-service")
                year = os.environ.get("DATA_YEAR", DEFAULT_YEAR)
                month = os.environ.get("DATA_MONTH", DEFAULT_MONTH)
                data_success, train_file, test_file = self.run_data_pipeline(year=year, month=month)
                
                if not data_success:
                    logger.error("Data pipeline failed. Aborting pipeline.")
                    self.auditor.log_data_access(
                        "pipeline_error",
                        "data_pipeline",
                        "orchestrator",
                        {"error": "Data pipeline failed"}
                    )
                    retry_count += 1
                    logger.info(f"Retrying pipeline (attempt {retry_count}/{max_retries})")
                    time.sleep(10)  # Wait before retrying
                    continue
                
                # Log data pipeline completion
                self.auditor.log_data_access(
                    "pipeline_complete",
                    "data_pipeline",
                    "orchestrator",
                    {"train_file": train_file, "test_file": test_file}
                )
                
                # Run training pipeline
                logger.info("Delegating model training to Training Service with files: {}, {}".format(train_file, test_file))
                self.auditor.log_data_access(
                    "pipeline_start",
                    "training_pipeline",
                    "orchestrator",
                    {"component": "model_training"}
                )
                
                training_success, metrics = self.run_training_pipeline(train_file, test_file)
                
                if not training_success:
                    logger.error("Training pipeline failed. Aborting pipeline.")
                    self.auditor.log_data_access(
                        "pipeline_error",
                        "training_pipeline",
                        "orchestrator",
                        {"error": "Training pipeline failed"}
                    )
                    retry_count += 1
                    logger.info(f"Retrying pipeline (attempt {retry_count}/{max_retries})")
                    time.sleep(10)  # Wait before retrying
                    continue
                
                # Log training pipeline completion
                self.auditor.log_data_access(
                    "pipeline_complete",
                    "training_pipeline",
                    "orchestrator",
                    {"metrics": metrics}
                )
                
                # Generate reports
                logger.info("Delegating report generation to monitoring service")
                report_success = self.generate_reports()
                
                if not report_success:
                    logger.warning("Report generation failed, but continuing pipeline")
                else:
                    logger.info("Pipeline reports generated successfully")
                
                # Log pipeline completion
                duration = time.time() - start_time
                self.auditor.log_data_access(
                    "pipeline_complete",
                    "full_pipeline",
                    "orchestrator",
                    {"duration": duration}
                )
                
                logger.info(f"MLOps pipeline completed successfully in {duration:.2f} seconds")
                success = True
                
            except Exception as e:
                logger.error(f"Pipeline failed with error: {str(e)}")
                self.auditor.log_data_access(
                    "pipeline_error",
                    "full_pipeline",
                    "orchestrator",
                    {"error": str(e)}
                )
                retry_count += 1
                if retry_count < max_retries:
                    logger.info(f"Retrying pipeline (attempt {retry_count}/{max_retries})")
                    time.sleep(10)  # Wait before retrying
                else:
                    logger.error(f"Pipeline failed after {max_retries} attempts")
                    return False
        
        if success:
            logger.info("MLOps pipeline executed successfully")
            return True
        else:
            logger.error("MLOps pipeline failed")
            return False

    def _check_service_health(self):
        """Check the health of all services"""
        health_checks = [
            ("MinIO", self.check_minio_health()),
            ("MLflow", self.check_mlflow_health()),
            ("Data Service", self.check_data_service_health()),
            ("Feature Service", self.check_feature_service_health()),
            ("Storage Manager", self.check_storage_manager_health()),
            ("Monitoring Service", self.check_monitoring_service_health()),
            ("Training Service", self.check_training_service_health())
        ]
        
        for service, healthy in health_checks:
            if not healthy:
                logger.error(f"{service} is not healthy")
                return False
        
        logger.info("All services are healthy")
        return True

    def _initialize_services(self):
        """Initialize all services."""
        self.initialize_services()

def main():
    """Main function to run the MLOps orchestrator."""
    try:
        # Add a delay to ensure other services have time to start
        logger.info("Waiting for services to initialize...")
        time.sleep(30)  # Wait 30 seconds before starting health checks
        
        orchestrator = MLOpsOrchestrator()
        success = orchestrator.run_pipeline()
        
        if success:
            logger.info("MLOps pipeline executed successfully")
        else:
            logger.error("MLOps pipeline failed")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Orchestrator failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
