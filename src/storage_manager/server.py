"""
HTTP server for the Storage Manager service.
Provides RESTful API endpoints for storage operations.
"""
import os
import sys
import json
import logging
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

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

class StorageManagerHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the Storage Manager service."""
    
    # Class-level attribute for the storage manager
    storage_manager = StorageManager()
    
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
                'service': 'storage-manager',
                'timestamp': __import__('datetime').datetime.now().isoformat()
            }
            
            self.wfile.write(json.dumps(response).encode())
        
        elif path == "/list-objects":
            try:
                # Parse query parameters
                query_params = parse_qs(parsed_url.query)
                bucket_name = query_params.get('bucket', [''])[0] or None
                prefix = query_params.get('prefix', [''])[0] or ""
                recursive = query_params.get('recursive', ['true'])[0].lower() == 'true'
                
                # List objects
                objects = self.storage_manager.list_objects(prefix, recursive, bucket_name)
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                
                response = {
                    'status': 'success',
                    'objects': objects
                }
                
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                logger.error(f"Error listing objects: {str(e)}")
                self.send_error(500, f"Error listing objects: {str(e)}")
        
        elif path == "/object-exists":
            try:
                # Parse query parameters
                query_params = parse_qs(parsed_url.query)
                object_name = query_params.get('object', [''])[0]
                bucket_name = query_params.get('bucket', [''])[0] or None
                
                if not object_name:
                    self.send_error(400, "Missing required parameter: object")
                    return
                
                # Check if object exists
                exists = self.storage_manager.object_exists(object_name, bucket_name)
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                
                response = {
                    'status': 'success',
                    'exists': exists
                }
                
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                logger.error(f"Error checking if object exists: {str(e)}")
                self.send_error(500, f"Error checking if object exists: {str(e)}")
        
        elif path == "/get-lifecycle-policy":
            try:
                # Parse query parameters
                query_params = parse_qs(parsed_url.query)
                bucket_name = query_params.get('bucket', [''])[0]
                
                if not bucket_name:
                    self.send_error(400, "Missing required parameter: bucket")
                    return
                
                # Get lifecycle policy
                try:
                    # MinIO client for lifecycle policies
                    client = self.storage_manager.client
                    
                    # Get the lifecycle policy
                    policy = client.get_bucket_lifecycle(bucket_name)
                    
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    
                    response = {
                        'status': 'success',
                        'bucket': bucket_name,
                        'policy': policy
                    }
                    
                    self.wfile.write(json.dumps(response).encode())
                except Exception as e:
                    logger.error(f"Error getting lifecycle policy: {str(e)}")
                    self.send_error(500, f"Error getting lifecycle policy: {str(e)}")
            except Exception as e:
                logger.error(f"Error processing get lifecycle policy request: {str(e)}")
                self.send_error(500, f"Error processing get lifecycle policy request: {str(e)}")
        
        else:
            self.send_error(404, "Not Found")
    
    def do_POST(self):
        """Handle POST requests."""
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        
        if path == "/download-from-url":
            try:
                # Get content length
                content_length = int(self.headers.get('Content-Length', 0))
                
                if content_length == 0:
                    self.send_error(400, "Empty request body")
                    return
                
                # Parse request body
                post_data = self.rfile.read(content_length).decode('utf-8')
                data = json.loads(post_data)
                
                url = data.get('url')
                object_name = data.get('object_name')
                bucket_name = data.get('bucket_name')
                
                if not url:
                    self.send_error(400, "Missing required parameter: url")
                    return
                
                # Download from URL
                result = self.storage_manager.download_from_url(url, object_name, bucket_name)
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                
                if result:
                    response = {
                        'status': 'success',
                        'message': f'Downloaded from {url} successfully',
                        'object_name': result
                    }
                else:
                    response = {
                        'status': 'error',
                        'message': f'Failed to download from {url}'
                    }
                
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                logger.error(f"Error downloading from URL: {str(e)}")
                self.send_error(500, f"Error downloading from URL: {str(e)}")
        
        elif path == "/integrate-data":
            try:
                # Get content length
                content_length = int(self.headers.get('Content-Length', 0))
                
                if content_length == 0:
                    self.send_error(400, "Empty request body")
                    return
                
                # Parse request body
                post_data = self.rfile.read(content_length).decode('utf-8')
                data = json.loads(post_data)
                
                new_data_object = data.get('new_data_object')
                consolidated_object = data.get('consolidated_object')
                sample_fraction = data.get('sample_fraction', 0.01)
                months_to_keep = data.get('months_to_keep', 6)
                bucket_name = data.get('bucket_name')
                
                if not new_data_object or not consolidated_object:
                    self.send_error(400, "Missing required parameters: new_data_object, consolidated_object")
                    return
                
                # Integrate data
                result = self.storage_manager.integrate_data(
                    new_data_object,
                    consolidated_object,
                    sample_fraction,
                    months_to_keep,
                    bucket_name
                )
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                
                if result:
                    response = {
                        'status': 'success',
                        'message': 'Data integrated successfully'
                    }
                else:
                    response = {
                        'status': 'error',
                        'message': 'Failed to integrate data'
                    }
                
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                logger.error(f"Error integrating data: {str(e)}")
                self.send_error(500, f"Error integrating data: {str(e)}")
        
        elif path == "/upload-file":
            try:
                # Check if this is a multipart/form-data request
                content_type = self.headers.get('Content-Type', '')
                
                if content_type.startswith('multipart/form-data'):
                    # Handle multipart form data
                    import cgi
                    
                    # Parse the form data
                    form = cgi.FieldStorage(
                        fp=self.rfile,
                        headers=self.headers,
                        environ={'REQUEST_METHOD': 'POST'}
                    )
                    
                    # Get file data
                    if 'file' not in form:
                        self.send_error(400, "Missing file data")
                        return
                    
                    fileitem = form['file']
                    if not fileitem.file:
                        self.send_error(400, "Empty file")
                        return
                    
                    # Get other form fields
                    object_name = form.getvalue('object_name') if 'object_name' in form else fileitem.filename
                    bucket_name = form.getvalue('bucket_name')
                    
                    # Save file to temporary location
                    temp_dir = "/tmp/storage_manager"
                    os.makedirs(temp_dir, exist_ok=True)
                    local_path = f"{temp_dir}/{object_name}"
                    
                    with open(local_path, 'wb') as f:
                        f.write(fileitem.file.read())
                    
                    # Upload the file to MinIO
                    result = self.storage_manager.upload_file(local_path, object_name, bucket_name)
                    
                    # Clean up
                    os.remove(local_path)
                    
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    
                    if result:
                        response = {
                            'status': 'success',
                            'message': 'File uploaded successfully',
                            'object_name': object_name,
                            'bucket_name': bucket_name
                        }
                    else:
                        response = {
                            'status': 'error',
                            'message': 'Failed to upload file'
                        }
                    
                    self.wfile.write(json.dumps(response).encode())
                    
                else:
                    # Handle JSON request (URL-based upload)
                    content_length = int(self.headers.get('Content-Length', 0))
                    
                    if content_length == 0:
                        self.send_error(400, "Empty request body")
                        return
                    
                    # Parse request body
                    post_data = self.rfile.read(content_length).decode('utf-8')
                    data = json.loads(post_data)
                    
                    file_url = data.get('file_url')
                    local_file_path = data.get('local_file_path')
                    object_name = data.get('object_name')
                    bucket_name = data.get('bucket_name')
                    
                    if not file_url and not local_file_path:
                        self.send_error(400, "Missing required parameter: either file_url or local_file_path must be provided")
                        return
                    
                    # If local_file_path is provided, use it directly
                    if local_file_path:
                        if not os.path.exists(local_file_path):
                            self.send_error(400, f"Local file not found: {local_file_path}")
                            return
                        
                        # Upload the file to MinIO
                        result = self.storage_manager.upload_file(local_file_path, object_name, bucket_name)
                    else:
                        # Download the file to a temporary location
                        temp_dir = "/tmp/storage_manager"
                        os.makedirs(temp_dir, exist_ok=True)
                        local_path = f"{temp_dir}/temp_file"
                        
                        response = requests.get(file_url, stream=True)
                        response.raise_for_status()
                        
                        with open(local_path, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                f.write(chunk)
                        
                        # Upload the file to MinIO
                        result = self.storage_manager.upload_file(local_path, object_name, bucket_name)
                        
                        # Clean up
                        os.remove(local_path)
                    
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    
                    if result:
                        response = {
                            'status': 'success',
                            'message': 'File uploaded successfully',
                            'object_name': object_name,
                            'bucket_name': bucket_name
                        }
                    else:
                        response = {
                            'status': 'error',
                            'message': 'Failed to upload file'
                        }
                    
                    self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                logger.error(f"Error uploading file: {str(e)}")
                self.send_error(500, f"Error uploading file: {str(e)}")
        
        elif path == "/create-version":
            try:
                # Get content length
                content_length = int(self.headers.get('Content-Length', 0))
                
                if content_length == 0:
                    self.send_error(400, "Empty request body")
                    return
                
                # Parse request body
                post_data = self.rfile.read(content_length).decode('utf-8')
                data = json.loads(post_data)
                
                object_name = data.get('object_name')
                bucket_name = data.get('bucket_name')
                version_tag = data.get('version_tag', f"v{__import__('datetime').datetime.now().strftime('%Y%m%d%H%M%S')}")
                
                if not object_name:
                    self.send_error(400, "Missing required parameter: object_name")
                    return
                
                # Create a versioned copy of the object
                versioned_object_name = f"{object_name.split('.')[0]}_{version_tag}.{object_name.split('.')[-1]}"
                
                # Download the original object
                temp_dir = "/tmp/storage_manager"
                os.makedirs(temp_dir, exist_ok=True)
                local_path = f"{temp_dir}/{object_name}"
                
                # Download the original object
                if self.storage_manager.download_file(object_name, local_path, bucket_name):
                    # Upload as a new versioned object
                    if self.storage_manager.upload_file(local_path, versioned_object_name, bucket_name):
                        # Clean up
                        os.remove(local_path)
                        
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        
                        response = {
                            'status': 'success',
                            'message': 'Version created successfully',
                            'versioned_object_name': versioned_object_name
                        }
                        
                        self.wfile.write(json.dumps(response).encode())
                    else:
                        self.send_error(500, "Failed to upload versioned object")
                else:
                    self.send_error(500, "Failed to download original object")
            except Exception as e:
                logger.error(f"Error creating version: {str(e)}")
                self.send_error(500, f"Error creating version: {str(e)}")
        
        elif path == "/set-lifecycle-policy":
            try:
                # Get content length
                content_length = int(self.headers.get('Content-Length', 0))
                
                if content_length == 0:
                    self.send_error(400, "Empty request body")
                    return
                
                # Parse request body
                post_data = self.rfile.read(content_length).decode('utf-8')
                data = json.loads(post_data)
                
                bucket_name = data.get('bucket_name')
                prefix = data.get('prefix', '')
                days = data.get('days', 30)  # Default retention period of 30 days
                
                if not bucket_name:
                    self.send_error(400, "Missing required parameter: bucket_name")
                    return
                
                # Set lifecycle policy
                try:
                    # MinIO client for lifecycle policies
                    client = self.storage_manager.client
                    
                    # Create lifecycle configuration
                    config = {
                        "Rules": [
                            {
                                "ID": f"Expire-{prefix}-after-{days}-days",
                                "Status": "Enabled",
                                "Filter": {
                                    "Prefix": prefix
                                },
                                "Expiration": {
                                    "Days": days
                                }
                            }
                        ]
                    }
                    
                    # Set the lifecycle policy
                    client.set_bucket_lifecycle(bucket_name, config)
                    
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    
                    response = {
                        'status': 'success',
                        'message': f'Lifecycle policy set for bucket {bucket_name}',
                        'details': {
                            'bucket': bucket_name,
                            'prefix': prefix,
                            'days': days
                        }
                    }
                    
                    self.wfile.write(json.dumps(response).encode())
                except Exception as e:
                    logger.error(f"Error setting lifecycle policy: {str(e)}")
                    self.send_error(500, f"Error setting lifecycle policy: {str(e)}")
            except Exception as e:
                logger.error(f"Error processing lifecycle policy request: {str(e)}")
                self.send_error(500, f"Error processing lifecycle policy request: {str(e)}")
        
        elif path == "/create-bucket":
            try:
                # Get content length
                content_length = int(self.headers.get('Content-Length', 0))
                
                if content_length == 0:
                    self.send_error(400, "Empty request body")
                    return
                
                # Parse request body
                post_data = self.rfile.read(content_length).decode('utf-8')
                data = json.loads(post_data)
                
                bucket_name = data.get('bucket_name')
                
                if not bucket_name:
                    self.send_error(400, "Missing required parameter: bucket_name")
                    return
                
                # Create bucket
                try:
                    # Check if bucket already exists
                    if self.storage_manager.client.bucket_exists(bucket_name):
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        
                        response = {
                            'status': 'success',
                            'message': f'Bucket {bucket_name} already exists'
                        }
                        
                        self.wfile.write(json.dumps(response).encode())
                        return
                    
                    # Create the bucket
                    self.storage_manager.client.make_bucket(bucket_name)
                    
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    
                    response = {
                        'status': 'success',
                        'message': f'Bucket {bucket_name} created successfully'
                    }
                    
                    self.wfile.write(json.dumps(response).encode())
                except Exception as e:
                    logger.error(f"Error creating bucket: {str(e)}")
                    self.send_error(500, f"Error creating bucket: {str(e)}")
            except Exception as e:
                logger.error(f"Error processing create bucket request: {str(e)}")
                self.send_error(500, f"Error processing create bucket request: {str(e)}")
        
        elif path == "/download-file":
            try:
                # Get content length
                content_length = int(self.headers.get('Content-Length', 0))
                
                if content_length == 0:
                    self.send_error(400, "Empty request body")
                    return
                
                # Parse request body
                post_data = self.rfile.read(content_length).decode('utf-8')
                data = json.loads(post_data)
                
                file_url = data.get('file_url')
                object_name = data.get('object_name')
                bucket_name = data.get('bucket_name')
                local_file_path = data.get('local_file_path', f"{SHARED_DATA_DIR}/{object_name}")
                version_id = data.get('version_id')
                
                if not object_name:
                    self.send_error(400, "Missing required parameter: object_name")
                    return
                
                if not bucket_name:
                    self.send_error(400, "Missing required parameter: bucket_name")
                    return
                
                # If file_url is provided, download from URL first
                if file_url:
                    # Create directory if it doesn't exist
                    os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
                    
                    # Download from URL
                    try:
                        response = requests.get(file_url, stream=True)
                        response.raise_for_status()
                        
                        with open(local_file_path, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                f.write(chunk)
                        
                        # Upload to MinIO
                        result = self.storage_manager.upload_file(local_file_path, object_name, bucket_name)
                        
                        if result:
                            self.send_response(200)
                            self.send_header('Content-Type', 'application/json')
                            self.end_headers()
                            
                            response = {
                                'status': 'success',
                                'message': 'File downloaded and stored in MinIO',
                                'local_file_path': local_file_path
                            }
                            
                            self.wfile.write(json.dumps(response).encode())
                        else:
                            self.send_error(500, "Failed to upload file to MinIO")
                    except Exception as e:
                        logger.error(f"Error downloading file from URL: {str(e)}")
                        self.send_error(500, f"Error downloading file from URL: {str(e)}")
                else:
                    # Download from MinIO
                    try:
                        # Create directory if it doesn't exist
                        os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
                        
                        # Download from MinIO
                        result = self.storage_manager.download_file(object_name, local_file_path, bucket_name, version_id)
                        
                        if result:
                            self.send_response(200)
                            self.send_header('Content-Type', 'application/json')
                            self.end_headers()
                            
                            response = {
                                'status': 'success',
                                'message': 'File downloaded from MinIO',
                                'local_file_path': local_file_path
                            }
                            
                            self.wfile.write(json.dumps(response).encode())
                        else:
                            self.send_error(500, "Failed to download file from MinIO")
                    except Exception as e:
                        logger.error(f"Error downloading file from MinIO: {str(e)}")
                        self.send_error(500, f"Error downloading file from MinIO: {str(e)}")
            except Exception as e:
                logger.error(f"Error processing download request: {str(e)}")
                self.send_error(500, f"Error processing download request: {str(e)}")

        else:
            self.send_error(404, "Not Found")

def start_server(port=8001):
    """Start the HTTP server for the storage manager service."""
    server_address = ('', port)
    httpd = HTTPServer(server_address, StorageManagerHandler)
    logger.info(f"Starting storage manager server on port {port}")
    httpd.serve_forever()

if __name__ == "__main__":
    start_server()
