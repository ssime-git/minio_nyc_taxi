#!/usr/bin/env python3
"""
Test script for validating HTTP communication between services.
This script tests the functionality of the DataService and StorageManager services.
"""

import os
import sys
import json
import time
import logging
import requests
import argparse
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('service_tester')

class ServiceTester:
    """Test the functionality of the DataService and StorageManager services."""
    
    def __init__(self, data_service_url="http://localhost:8000", storage_manager_url="http://localhost:8001"):
        """
        Initialize the ServiceTester.
        
        Args:
            data_service_url (str): URL of the DataService
            storage_manager_url (str): URL of the StorageManager
        """
        self.data_service_url = data_service_url
        self.storage_manager_url = storage_manager_url
        self.test_bucket = "test-bucket"
        self.test_file = "test-file.txt"
        self.test_content = f"Test content generated at {datetime.now().isoformat()}"
        self.test_file_path = "/tmp/test-file.txt"
        
        # Create test file
        with open(self.test_file_path, 'w') as f:
            f.write(self.test_content)
        
        logger.info(f"Initialized ServiceTester with DataService at {data_service_url} and StorageManager at {storage_manager_url}")
    
    def run_all_tests(self):
        """Run all tests and report results."""
        test_results = {
            "storage_manager_tests": {},
            "data_service_tests": {},
            "integration_tests": {}
        }
        
        # Test StorageManager service
        logger.info("Testing StorageManager service...")
        test_results["storage_manager_tests"]["create_bucket"] = self.test_create_bucket()
        test_results["storage_manager_tests"]["upload_file"] = self.test_upload_file()
        test_results["storage_manager_tests"]["check_object_exists"] = self.test_check_object_exists()
        test_results["storage_manager_tests"]["create_version"] = self.test_create_version()
        test_results["storage_manager_tests"]["set_lifecycle_policy"] = self.test_set_lifecycle_policy()
        test_results["storage_manager_tests"]["get_lifecycle_policy"] = self.test_get_lifecycle_policy()
        
        # Test DataService
        logger.info("Testing DataService...")
        test_results["data_service_tests"]["create_dataset_version"] = self.test_create_dataset_version()
        test_results["data_service_tests"]["run_quality_check"] = self.test_run_quality_check()
        test_results["data_service_tests"]["set_data_retention_policy"] = self.test_set_data_retention_policy()
        test_results["data_service_tests"]["get_data_retention_policy"] = self.test_get_data_retention_policy()
        
        # Test integration between services
        logger.info("Testing integration between services...")
        test_results["integration_tests"]["end_to_end_flow"] = self.test_end_to_end_flow()
        
        # Print summary
        self._print_test_summary(test_results)
        
        # Clean up
        self._cleanup()
        
        # Return overall success
        return all([
            all(test_results["storage_manager_tests"].values()),
            all(test_results["data_service_tests"].values()),
            all(test_results["integration_tests"].values())
        ])
    
    def test_create_bucket(self):
        """Test creating a bucket in MinIO."""
        try:
            response = requests.post(
                f"{self.storage_manager_url}/create-bucket",
                json={"bucket_name": self.test_bucket}
            )
            
            if response.status_code == 200 and response.json().get("status") == "success":
                logger.info(f"Successfully created bucket: {self.test_bucket}")
                return True
            else:
                logger.error(f"Failed to create bucket: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error testing create bucket: {str(e)}")
            return False
    
    def test_upload_file(self):
        """Test uploading a file to MinIO."""
        try:
            with open(self.test_file_path, 'rb') as f:
                files = {'file': (self.test_file, f)}
                response = requests.post(
                    f"{self.storage_manager_url}/upload-file",
                    data={"bucket_name": self.test_bucket, "object_name": self.test_file},
                    files=files
                )
            
            if response.status_code == 200 and response.json().get("status") == "success":
                logger.info(f"Successfully uploaded file: {self.test_file}")
                return True
            else:
                logger.error(f"Failed to upload file: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error testing upload file: {str(e)}")
            return False
    
    def test_check_object_exists(self):
        """Test checking if an object exists in MinIO."""
        try:
            response = requests.get(
                f"{self.storage_manager_url}/object-exists",
                params={"bucket": self.test_bucket, "object": self.test_file}
            )
            
            if response.status_code == 200 and response.json().get("exists") is True:
                logger.info(f"Successfully verified object exists: {self.test_file}")
                return True
            else:
                logger.error(f"Failed to verify object exists: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error testing check object exists: {str(e)}")
            return False
    
    def test_create_version(self):
        """Test creating a versioned copy of an object."""
        try:
            response = requests.post(
                f"{self.storage_manager_url}/create-version",
                json={
                    "bucket_name": self.test_bucket,
                    "object_name": self.test_file,
                    "version_tag": "test-version"
                }
            )
            
            if response.status_code == 200 and response.json().get("status") == "success":
                versioned_object = response.json().get("versioned_object_name")
                logger.info(f"Successfully created version: {versioned_object}")
                return True
            else:
                logger.error(f"Failed to create version: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error testing create version: {str(e)}")
            return False
    
    def test_set_lifecycle_policy(self):
        """Test setting a lifecycle policy."""
        try:
            response = requests.post(
                f"{self.storage_manager_url}/set-lifecycle-policy",
                json={
                    "bucket_name": self.test_bucket,
                    "prefix": "test",
                    "days": 7
                }
            )
            
            if response.status_code == 200 and response.json().get("status") == "success":
                logger.info(f"Successfully set lifecycle policy for bucket: {self.test_bucket}")
                return True
            else:
                logger.error(f"Failed to set lifecycle policy: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error testing set lifecycle policy: {str(e)}")
            return False
    
    def test_get_lifecycle_policy(self):
        """Test getting a lifecycle policy."""
        try:
            response = requests.get(
                f"{self.storage_manager_url}/get-lifecycle-policy",
                params={"bucket": self.test_bucket}
            )
            
            if response.status_code == 200 and response.json().get("status") == "success":
                logger.info(f"Successfully retrieved lifecycle policy for bucket: {self.test_bucket}")
                return True
            else:
                logger.error(f"Failed to get lifecycle policy: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error testing get lifecycle policy: {str(e)}")
            return False
    
    def test_create_dataset_version(self):
        """Test creating a dataset version through the DataService."""
        try:
            response = requests.get(
                f"{self.data_service_url}/create-dataset-version",
                params={
                    "object": self.test_file,
                    "bucket": self.test_bucket,
                    "version": "data-service-test"
                }
            )
            
            if response.status_code == 200 and response.json().get("status") == "success":
                versioned_object = response.json().get("versioned_object")
                logger.info(f"Successfully created dataset version: {versioned_object}")
                return True
            else:
                logger.error(f"Failed to create dataset version: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error testing create dataset version: {str(e)}")
            return False
    
    def test_run_quality_check(self):
        """Test running a quality check on a dataset."""
        try:
            # Create a test CSV file for quality checks
            test_csv_path = "/tmp/test-data.csv"
            with open(test_csv_path, 'w') as f:
                f.write("id,name,value\n")
                f.write("1,test1,100\n")
                f.write("2,test2,200\n")
                f.write("3,test3,300\n")
            
            # Upload the CSV file
            with open(test_csv_path, 'rb') as f:
                files = {'file': ('test-data.csv', f)}
                response = requests.post(
                    f"{self.storage_manager_url}/upload-file",
                    data={"bucket_name": self.test_bucket, "object_name": "test-data.csv"},
                    files=files
                )
            
            if response.status_code != 200:
                logger.error(f"Failed to upload test CSV file: {response.text}")
                return False
            
            # Run quality check
            response = requests.get(
                f"{self.data_service_url}/run-quality-check",
                params={"object": "test-data.csv", "bucket": self.test_bucket}
            )
            
            if response.status_code == 200 and response.json().get("status") in ["pass", "fail"]:
                logger.info(f"Successfully ran quality check on test data")
                return True
            else:
                logger.error(f"Failed to run quality check: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error testing run quality check: {str(e)}")
            return False
    
    def test_set_data_retention_policy(self):
        """Test setting a data retention policy through the DataService."""
        try:
            response = requests.get(
                f"{self.data_service_url}/set-data-retention-policy",
                params={
                    "bucket": self.test_bucket,
                    "prefix": "test",
                    "days": 14
                }
            )
            
            if response.status_code == 200 and response.json().get("status") == "success":
                logger.info(f"Successfully set data retention policy for bucket: {self.test_bucket}")
                return True
            else:
                logger.error(f"Failed to set data retention policy: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error testing set data retention policy: {str(e)}")
            return False
    
    def test_get_data_retention_policy(self):
        """Test getting a data retention policy through the DataService."""
        try:
            response = requests.get(
                f"{self.data_service_url}/get-data-retention-policy",
                params={"bucket": self.test_bucket}
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully retrieved data retention policy for bucket: {self.test_bucket}")
                return True
            else:
                logger.error(f"Failed to get data retention policy: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error testing get data retention policy: {str(e)}")
            return False
    
    def test_end_to_end_flow(self):
        """Test an end-to-end flow between DataService and StorageManager."""
        try:
            # 1. Create a new test file with timestamp
            test_flow_file = f"flow-test-{int(time.time())}.txt"
            test_flow_path = f"/tmp/{test_flow_file}"
            with open(test_flow_path, 'w') as f:
                f.write(f"End-to-end test content at {datetime.now().isoformat()}")
            
            # 2. Upload the file through StorageManager
            with open(test_flow_path, 'rb') as f:
                files = {'file': (test_flow_file, f)}
                response = requests.post(
                    f"{self.storage_manager_url}/upload-file",
                    data={"bucket_name": self.test_bucket, "object_name": test_flow_file},
                    files=files
                )
            
            if response.status_code != 200:
                logger.error(f"End-to-end test failed at upload step: {response.text}")
                return False
            
            # 3. Create a version through DataService
            response = requests.get(
                f"{self.data_service_url}/create-dataset-version",
                params={
                    "object": test_flow_file,
                    "bucket": self.test_bucket,
                    "version": "flow-test"
                }
            )
            
            if response.status_code != 200 or response.json().get("status") != "success":
                logger.error(f"End-to-end test failed at version creation step: {response.text}")
                return False
            
            versioned_object = response.json().get("versioned_object")
            
            # 4. Verify the versioned object exists through StorageManager
            response = requests.get(
                f"{self.storage_manager_url}/object-exists",
                params={"bucket": self.test_bucket, "object": versioned_object}
            )
            
            if response.status_code != 200 or response.json().get("exists") is not True:
                logger.error(f"End-to-end test failed at verification step: {response.text}")
                return False
            
            logger.info(f"Successfully completed end-to-end test flow")
            return True
            
        except Exception as e:
            logger.error(f"Error in end-to-end test flow: {str(e)}")
            return False
    
    def _print_test_summary(self, results):
        """Print a summary of test results."""
        print("\n" + "="*50)
        print("TEST RESULTS SUMMARY")
        print("="*50)
        
        total_tests = 0
        passed_tests = 0
        
        for category, tests in results.items():
            print(f"\n{category.upper()}:")
            for test_name, result in tests.items():
                status = "PASSED" if result else "FAILED"
                status_color = "\033[92m" if result else "\033[91m"  # Green for pass, red for fail
                print(f"  {status_color}{test_name}: {status}\033[0m")
                total_tests += 1
                if result:
                    passed_tests += 1
        
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        overall_status = "PASSED" if success_rate == 100 else "FAILED"
        status_color = "\033[92m" if success_rate == 100 else "\033[91m"
        
        print("\n" + "="*50)
        print(f"{status_color}OVERALL: {overall_status} ({passed_tests}/{total_tests} tests, {success_rate:.1f}%)\033[0m")
        print("="*50 + "\n")
    
    def _cleanup(self):
        """Clean up test resources."""
        try:
            # Remove local test files
            if os.path.exists(self.test_file_path):
                os.remove(self.test_file_path)
            
            if os.path.exists("/tmp/test-data.csv"):
                os.remove("/tmp/test-data.csv")
            
            logger.info("Cleaned up local test files")
            
            # Note: We're not deleting the MinIO test bucket and objects
            # to allow for manual inspection if needed
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")

def main():
    """Run the service tests."""
    parser = argparse.ArgumentParser(description='Test HTTP communication between services')
    parser.add_argument('--data-service', default='http://localhost:8000',
                        help='URL of the DataService (default: http://localhost:8000)')
    parser.add_argument('--storage-manager', default='http://localhost:8001',
                        help='URL of the StorageManager (default: http://localhost:8001)')
    
    args = parser.parse_args()
    
    tester = ServiceTester(args.data_service, args.storage_manager)
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
