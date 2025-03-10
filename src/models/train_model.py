import os
import pandas as pd
import mlflow
import mlflow.sklearn
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import pickle
from datetime import datetime
from pathlib import Path
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import time
import numpy as np

import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))

from storage_manager.manager import StorageManager
from config import (
    MINIO_ENDPOINT,
    MINIO_ROOT_USER,
    MINIO_ROOT_PASSWORD,
    MINIO_BUCKET,
    PROCESSED_DATA_DIR,
    MLFLOW_TRACKING_URI
)
from monitoring.audit import DataAuditor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ModelTrainer:
    """Class for training ML models on NYC Taxi data."""
    
    def __init__(self):
        """Initialize the model trainer with storage manager and auditor."""
        # Initialize storage manager for this service
        self.storage_manager = StorageManager(
            endpoint=MINIO_ENDPOINT,
            access_key=MINIO_ROOT_USER,
            secret_key=MINIO_ROOT_PASSWORD,
            bucket_name=MINIO_BUCKET
        )
        
        # Initialize auditor
        self.auditor = DataAuditor()
        
        # Set up MLflow
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        os.environ["MLFLOW_S3_ENDPOINT_URL"] = MINIO_ENDPOINT
        os.environ["AWS_ACCESS_KEY_ID"] = MINIO_ROOT_USER
        os.environ["AWS_SECRET_ACCESS_KEY"] = MINIO_ROOT_PASSWORD
        
        # Ensure model directory exists
        os.makedirs(PROCESSED_DATA_DIR, exist_ok=True)

    def load_data(self, train_file=None, test_file=None, sample_size=None):
        """
        Load the train and test datasets from MinIO.
        
        Args:
            train_file: Optional name of the training file to load
            test_file: Optional name of the test file to load
            sample_size: Optional integer to limit the dataset size for faster processing
            
        If file names are not provided, will attempt to find the latest files in the buckets.
        """
        try:
            # If file names not provided, find the latest files
            if not train_file or not test_file:
                # List files in train and test buckets
                train_files = self.storage_manager.list_objects(bucket_name="nyc-taxi-data-train")
                test_files = self.storage_manager.list_objects(bucket_name="nyc-taxi-data-test")
                
                if not train_files or not test_files:
                    raise Exception("No training or test files found in buckets")
                
                # Sort by last modified time (newest first)
                train_files.sort(key=lambda x: x.last_modified, reverse=True)
                test_files.sort(key=lambda x: x.last_modified, reverse=True)
                
                # Get the latest files
                train_file = train_files[0].object_name
                test_file = test_files[0].object_name
                
                logger.info(f"Using latest train file: {train_file}")
                logger.info(f"Using latest test file: {test_file}")
            
            # Download datasets using storage manager
            train_local_path = os.path.join(PROCESSED_DATA_DIR, train_file)
            test_local_path = os.path.join(PROCESSED_DATA_DIR, test_file)
            
            logger.info(f"Downloading training file: {train_file}")
            self.storage_manager.download_file(
                train_file, 
                train_local_path, 
                bucket_name="nyc-taxi-data-train"
            )
            
            logger.info(f"Downloading test file: {test_file}")
            self.storage_manager.download_file(
                test_file, 
                test_local_path, 
                bucket_name="nyc-taxi-data-test"
            )
            
            # Log data access
            self.auditor.log_data_access(
                "read",
                train_file,
                "training_service",
                {"purpose": "model_training"}
            )
            
            self.auditor.log_data_access(
                "read",
                test_file,
                "training_service",
                {"purpose": "model_training"}
            )

            # Load datasets
            logger.info("Loading training data into memory")
            train_df = pd.read_parquet(train_local_path)
            logger.info("Loading test data into memory")
            test_df = pd.read_parquet(test_local_path)
            
            # Apply sampling if requested (for faster processing)
            if sample_size and isinstance(sample_size, int) and sample_size > 0:
                logger.info(f"Sampling data to {sample_size} rows for faster processing")
                if len(train_df) > sample_size:
                    train_df = train_df.sample(sample_size, random_state=42)
                if len(test_df) > sample_size // 4:  # Use 1/4 of sample size for test set
                    test_df = test_df.sample(sample_size // 4, random_state=42)
                logger.info(f"After sampling - Train: {len(train_df)} rows, Test: {len(test_df)} rows")
            
            # Preprocess data - handle timestamps and other data types
            def preprocess_dataframe(df):
                # Convert timestamp columns to numeric features
                for col in df.select_dtypes(include=['datetime64']).columns:
                    logger.info(f"Converting timestamp column {col} to numeric features")
                    # Extract useful components from timestamps
                    df[f"{col}_hour"] = df[col].dt.hour
                    df[f"{col}_day"] = df[col].dt.day
                    df[f"{col}_month"] = df[col].dt.month
                    df[f"{col}_dayofweek"] = df[col].dt.dayofweek
                    # Drop the original timestamp column
                    df = df.drop(col, axis=1)
                
                # Handle categorical columns
                for col in df.select_dtypes(include=['object']).columns:
                    logger.info(f"Converting categorical column {col} to numeric")
                    df[col] = pd.factorize(df[col])[0]
                
                # Handle any NaN values
                if df.isna().any().any():
                    logger.info("Filling NaN values")
                    df = df.fillna(df.median())
                
                return df
            
            # Apply preprocessing
            logger.info("Preprocessing training data")
            train_df = preprocess_dataframe(train_df)
            logger.info("Preprocessing test data")
            test_df = preprocess_dataframe(test_df)
            
            # Log data shapes after preprocessing
            logger.info(f"Data shapes after preprocessing - Train: {train_df.shape}, Test: {test_df.shape}")
            
            # Check for any remaining non-numeric columns
            non_numeric_cols_train = train_df.select_dtypes(exclude=['number']).columns.tolist()
            non_numeric_cols_test = test_df.select_dtypes(exclude=['number']).columns.tolist()
            
            if non_numeric_cols_train:
                logger.warning(f"Non-numeric columns in training data: {non_numeric_cols_train}")
                # Drop these columns as they can't be used by RandomForest
                train_df = train_df.drop(non_numeric_cols_train, axis=1)
                test_df = test_df.drop(non_numeric_cols_train, axis=1)
                logger.info(f"Dropped non-numeric columns. New shapes - Train: {train_df.shape}, Test: {test_df.shape}")
            
            # Separate features and target
            # Assuming 'fare_amount' is the target variable
            if 'fare_amount' not in train_df.columns:
                # If fare_amount is not in the columns, use the last column as target
                logger.warning("fare_amount column not found, using last column as target")
                y_train = train_df.iloc[:, -1]
                X_train = train_df.iloc[:, :-1]
                y_test = test_df.iloc[:, -1]
                X_test = test_df.iloc[:, :-1]
            else:
                X_train = train_df.drop('fare_amount', axis=1)
                y_train = train_df['fare_amount']
                X_test = test_df.drop('fare_amount', axis=1)
                y_test = test_df['fare_amount']
            
            logger.info(f"Data loaded successfully. Train shape: {X_train.shape}, Test shape: {X_test.shape}")
            return X_train, X_test, y_train, y_test
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            return None, None, None, None

    def train_model(self, X_train, X_test, y_train, y_test):
        """
        Train a RandomForest model on the provided data.
        
        Args:
            X_train: Training features
            X_test: Test features
            y_train: Training target
            y_test: Test target
            
        Returns:
            Dictionary with model metrics
        """
        try:
            logger.info(f"Starting model training with {X_train.shape[0]} samples")
            
            # Log data access for model training
            self.auditor.log_data_access(
                "model_training_start",
                "model_training",
                "training_service",
                {"samples": X_train.shape[0], "features": X_train.shape[1]}
            )
            
            # Set up MLflow tracking
            mlflow.set_experiment("nyc-taxi-fare-prediction")
            
            # Process data in chunks if it's very large
            chunk_size = 500000  # Process 500k rows at a time if dataset is large
            
            with mlflow.start_run() as run:
                # Log dataset info
                mlflow.log_param("train_samples", X_train.shape[0])
                mlflow.log_param("test_samples", X_test.shape[0])
                mlflow.log_param("features", X_train.shape[1])
                
                # Initialize model
                model = RandomForestRegressor(
                    n_estimators=100,
                    max_depth=10,
                    random_state=42,
                    n_jobs=-1  # Use all available cores
                )
                
                # Train model in chunks if dataset is large
                if X_train.shape[0] > chunk_size:
                    logger.info(f"Dataset is large, training in chunks of {chunk_size} samples")
                    
                    # Train on chunks
                    for i in range(0, X_train.shape[0], chunk_size):
                        end_idx = min(i + chunk_size, X_train.shape[0])
                        chunk_X = X_train.iloc[i:end_idx]
                        chunk_y = y_train.iloc[i:end_idx]
                        
                        logger.info(f"Training on chunk {i//chunk_size + 1}: samples {i} to {end_idx}")
                        if i == 0:
                            # First chunk - fit the model
                            model.fit(chunk_X, chunk_y)
                        else:
                            # Subsequent chunks - partial_fit not available for RandomForest
                            # So we'll update with a new model and average the predictions
                            temp_model = RandomForestRegressor(
                                n_estimators=100,
                                max_depth=10,
                                random_state=42,
                                n_jobs=-1
                            )
                            temp_model.fit(chunk_X, chunk_y)
                            
                            # Update the main model by averaging the predictions
                            # This is a simple approach - in production, you might use more sophisticated methods
                            model.estimators_ = model.estimators_ + temp_model.estimators_
                            model.n_estimators = len(model.estimators_)
                else:
                    # Train on the entire dataset at once
                    logger.info("Training model on entire dataset")
                    model.fit(X_train, y_train)
                
                # Make predictions
                y_pred = model.predict(X_test)
                
                # Calculate metrics
                mse = mean_squared_error(y_test, y_pred)
                rmse = np.sqrt(mse)
                mae = mean_absolute_error(y_test, y_pred)
                r2 = r2_score(y_test, y_pred)
                
                # Log metrics to MLflow
                mlflow.log_metric("mse", mse)
                mlflow.log_metric("rmse", rmse)
                mlflow.log_metric("mae", mae)
                mlflow.log_metric("r2", r2)
                
                # Log model to MLflow
                mlflow.sklearn.log_model(model, "model")
                
                # Save model locally
                model_path = os.path.join(PROCESSED_DATA_DIR, "model.pkl")
                with open(model_path, "wb") as f:
                    pickle.dump(model, f)
                
                logger.info(f"Model saved to {model_path}")
                logger.info(f"Model metrics: MSE={mse:.4f}, RMSE={rmse:.4f}, MAE={mae:.4f}, R2={r2:.4f}")
                
                # Log data access for model completion
                self.auditor.log_data_access(
                    "model_training_complete",
                    "model_training",
                    "training_service",
                    {
                        "mse": float(mse),
                        "rmse": float(rmse),
                        "mae": float(mae),
                        "r2": float(r2),
                        "model_path": model_path,
                        "mlflow_run_id": run.info.run_id
                    }
                )
                
                # Return metrics
                return {
                    "mse": float(mse),
                    "rmse": float(rmse),
                    "mae": float(mae),
                    "r2": float(r2),
                    "model_path": model_path,
                    "mlflow_run_id": run.info.run_id
                }
                
        except Exception as e:
            logger.error(f"Error training model: {str(e)}")
            self.auditor.log_data_access(
                "model_training_error",
                "model_training",
                "training_service",
                {"error": str(e)}
            )
            raise

    def log_model(self, model, metrics, model_path, params):
        """Log model, parameters, metrics, and artifacts to MLflow."""
        with mlflow.start_run(run_name=f"training_{datetime.now().strftime('%Y%m%d_%H%M%S')}") as run:
            # Log parameters
            mlflow.log_params(params)
            
            # Log metrics
            mlflow.log_metrics(metrics)
            
            # Log model
            mlflow.sklearn.log_model(model, "model")
            
            # Log the saved model file as an artifact
            mlflow.log_artifact(model_path)
            
            # Upload model to MinIO
            model_minio_path = f"models/model_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl"
            self.storage_manager.upload_file(model_path, model_minio_path)
            
            # Log model registration
            self.auditor.log_data_access(
                "model_registration",
                model_minio_path,
                "training_service",
                {
                    "mlflow_run_id": run.info.run_id,
                    "metrics": metrics,
                    "parameters": params
                }
            )
            
            logger.info(f"Model logged to MLflow with run_id: {run.info.run_id}")
            return run.info.run_id

# Global model trainer instance for API access
model_trainer = None

class ModelTrainingHandler(BaseHTTPRequestHandler):
    """HTTP request handler for model training service."""
    
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
        """Handle POST requests for model training."""
        try:
            if self.path == '/health':
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "healthy"}).encode())
                return
                
            if self.path == '/train-model':
                # Get request body
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length).decode('utf-8')
                request_data = json.loads(post_data)
                
                # Extract parameters
                train_file = request_data.get('train_file')
                test_file = request_data.get('test_file')
                sample_size = request_data.get('sample_size')
                
                logger.info(f"Received training request with train_file={train_file}, test_file={test_file}, sample_size={sample_size}")
                
                # Initialize model trainer
                model_trainer = ModelTrainer()
                
                # Load data
                logger.info("Loading data...")
                X_train, X_test, y_train, y_test = model_trainer.load_data(train_file, test_file, sample_size)
                
                if X_train is None or X_test is None or y_train is None or y_test is None:
                    logger.error("Failed to load data")
                    self.send_response(500)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "status": "error",
                        "message": "Failed to load data"
                    }).encode())
                    return
                
                # Train model
                logger.info("Training model...")
                try:
                    metrics = model_trainer.train_model(X_train, X_test, y_train, y_test)
                    
                    # Send response
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "status": "success",
                        "metrics": metrics
                    }).encode())
                    
                except Exception as e:
                    logger.error(f"Error during model training: {str(e)}")
                    self.send_response(500)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "status": "error",
                        "message": f"Model training failed: {str(e)}"
                    }).encode())
                return
                
            # Handle unknown paths
            self.send_response(404)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "error",
                "message": f"Unknown path: {self.path}"
            }).encode())
            
        except Exception as e:
            logger.error(f"Error handling request: {str(e)}")
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "error",
                "message": f"Server error: {str(e)}"
            }).encode())

def start_server(port=8002):
    """Start the HTTP server for the model training service."""
    global model_trainer
    model_trainer = ModelTrainer()
    
    # Set up MLflow experiment
    mlflow.set_experiment("nyc_taxi_fare_prediction")
    
    server = HTTPServer(('0.0.0.0', port), ModelTrainingHandler)
    logger.info(f"Starting model training service on port {port}")
    
    # Run server in a separate thread
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    
    return server

def main():
    """Main function to run the model training service."""
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
        logger.error(f"Model training service failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
