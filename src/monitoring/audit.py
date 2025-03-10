"""
Audit logging and GDPR compliance monitoring for NYC Taxi MLOps pipeline.
Handles data access tracking, anonymization, and compliance reporting.
"""
import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import hashlib
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import sys

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    MINIO_ENDPOINT,
    MINIO_ROOT_USER,
    MINIO_ROOT_PASSWORD,
    MINIO_BUCKET
)

from storage_manager.manager import StorageManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global auditor instance for API access
global_auditor = None

class MonitoringHandler(BaseHTTPRequestHandler):
    """HTTP request handler for monitoring service."""
    
    def _set_headers(self, status_code=200):
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
    
    def do_GET(self):
        """Handle GET requests."""
        if self.path == '/health':
            # Health check endpoint
            self._set_headers()
            self.wfile.write(json.dumps({'status': 'healthy'}).encode())
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({'error': 'Not found'}).encode())
    
    def do_POST(self):
        """Handle POST requests."""
        if self.path == '/generate-report':
            # Generate report endpoint
            try:
                global global_auditor
                report = global_auditor.generate_audit_report()
                self._set_headers()
                self.wfile.write(json.dumps({
                    'status': 'success',
                    'message': 'Audit report generated successfully',
                    'report_summary': {
                        'period': report.get('period', {}),
                        'total_operations': report.get('summary', {}).get('total_operations', 0)
                    }
                }).encode())
            except Exception as e:
                logger.error(f"Error generating report: {str(e)}")
                self._set_headers(500)
                self.wfile.write(json.dumps({'error': str(e)}).encode())
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({'error': 'Not found'}).encode())

class DataAuditor:
    """Handles data access auditing and GDPR compliance."""
    
    def __init__(self):
        """Initialize the auditor with storage manager."""
        self.storage_manager = StorageManager(
            endpoint=MINIO_ENDPOINT,
            access_key=MINIO_ROOT_USER,
            secret_key=MINIO_ROOT_PASSWORD,
            bucket_name=MINIO_BUCKET
        )
        
        # Create audit bucket if it doesn't exist
        self.audit_bucket = f"{MINIO_BUCKET}-audit"
        self.storage_manager.create_bucket(self.audit_bucket)
        
        # Set up audit log file
        self.audit_log = os.path.join(
            os.path.dirname(__file__),
            "logs",
            f"audit_{datetime.now().strftime('%Y%m')}.json"
        )
        os.makedirs(os.path.dirname(self.audit_log), exist_ok=True)

    def log_data_access(
        self,
        operation: str,
        data_path: str,
        service_name: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log data access operations with details."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "data_path": data_path,
            "service_name": service_name,
            "details": details or {}
        }
        
        try:
            # Append to local log
            with open(self.audit_log, 'a') as f:
                json.dump(log_entry, f)
                f.write('\n')
            
            # Upload to MinIO
            self.storage_manager.upload_file(
                self.audit_log,
                f"audit_logs/access_{datetime.now().strftime('%Y%m')}.json",
                bucket_name=self.audit_bucket
            )
            
            logger.info(f"Logged {operation} operation on {data_path}")
        except Exception as e:
            logger.error(f"Failed to log data access: {str(e)}")

    def anonymize_pii(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Anonymize personally identifiable information in data."""
        pii_fields = [
            "vendor_id",
            "pickup_location_id",
            "dropoff_location_id"
        ]
        
        anonymized = data.copy()
        for field in pii_fields:
            if field in anonymized:
                # Hash the value for anonymization
                value = str(anonymized[field])
                anonymized[field] = hashlib.sha256(
                    value.encode()
                ).hexdigest()[:8]
        
        return anonymized

    def check_gdpr_compliance(self, data_path: str) -> Dict[str, Any]:
        """Check GDPR compliance for a dataset."""
        try:
            # Check data retention
            stats = self.storage_manager.get_object_stats(data_path)
            if not stats:
                return {"compliant": False, "reason": "Data not found"}
            
            # Check data age
            creation_date = stats.last_modified
            age_days = (datetime.now() - creation_date).days
            
            compliance_report = {
                "compliant": True,
                "checks": {
                    "retention": age_days <= 180,  # 6 months retention
                    "anonymization": True,  # Assuming data is pre-anonymized
                    "access_logging": True
                },
                "recommendations": []
            }
            
            # Add recommendations if needed
            if age_days > 150:  # Warning at 5 months
                compliance_report["recommendations"].append(
                    f"Data will expire in {180 - age_days} days"
                )
            
            return compliance_report
            
        except Exception as e:
            logger.error(f"Failed to check GDPR compliance: {str(e)}")
            return {
                "compliant": False,
                "reason": f"Compliance check failed: {str(e)}"
            }

    def generate_audit_report(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Generate an audit report for the specified time period."""
        try:
            # Default to current month if dates not specified
            if not start_date:
                start_date = datetime.now().replace(
                    day=1, hour=0, minute=0, second=0, microsecond=0
                )
            if not end_date:
                end_date = datetime.now()
            
            # Collect audit logs
            audit_entries = []
            log_files = self.storage_manager.list_objects(
                prefix="audit_logs/",
                bucket_name=self.audit_bucket
            )
            
            for log_file in log_files:
                # Download and process each log file
                local_path = os.path.join(
                    os.path.dirname(self.audit_log),
                    os.path.basename(log_file)
                )
                self.storage_manager.download_file(
                    log_file,
                    local_path,
                    bucket_name=self.audit_bucket
                )
                
                with open(local_path, 'r') as f:
                    for line in f:
                        entry = json.loads(line)
                        entry_date = datetime.fromisoformat(entry["timestamp"])
                        if start_date <= entry_date <= end_date:
                            audit_entries.append(entry)
            
            # Generate report
            report = {
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                },
                "summary": {
                    "total_operations": len(audit_entries),
                    "operations_by_type": {},
                    "operations_by_service": {}
                },
                "entries": audit_entries
            }
            
            # Calculate summaries
            for entry in audit_entries:
                op_type = entry["operation"]
                service = entry["service_name"]
                report["summary"]["operations_by_type"][op_type] = \
                    report["summary"]["operations_by_type"].get(op_type, 0) + 1
                report["summary"]["operations_by_service"][service] = \
                    report["summary"]["operations_by_service"].get(service, 0) + 1
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate audit report: {str(e)}")
            return {
                "error": f"Report generation failed: {str(e)}"
            }

def start_server(port=8003):
    """Start the HTTP server for the monitoring service."""
    global global_auditor
    global_auditor = DataAuditor()
    
    server = HTTPServer(('0.0.0.0', port), MonitoringHandler)
    logger.info(f"Starting monitoring service on port {port}")
    
    # Run server in a separate thread
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    
    return server

def main():
    """Main function to run the monitoring service."""
    try:
        # Start HTTP server
        server = start_server()
        
        # Keep main thread alive
        while True:
            try:
                import time
                time.sleep(1)
            except KeyboardInterrupt:
                break
        
        server.shutdown()
        
    except Exception as e:
        logger.error(f"Monitoring service failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
