# MLOps Architecture Framing Document

## 1. Executive Summary

This document outlines the architecture for an MLOps system centered around MinIO as the core storage and data management solution. The system is designed for educational purposes as part of an MLOps beginner's exam, while providing industry-standard practices and security considerations. The architecture includes versioning capabilities, role-based access control, and GDPR compliance features to address real-world requirements.

## 2. Architecture Vision

The MinIO Storage Manager will serve as the central component of the architecture, acting as the backbone for data storage, versioning, access control, and lifecycle management. All other services will interact with the MinIO Storage Manager using dedicated service accounts with specific permissions tailored to their needs.

## 3. Core Requirements

### 3.1 MinIO Storage Manager as Central Hub

- MinIO Storage Manager will be the primary interface for all data operations
- All services will interact with data exclusively through the Storage Manager
- Centralized logging and auditing of data access and operations
- Unified access control and permission management

### 3.2 Version Control

- Utilize MinIO's native versioning capabilities for data objects
- Implement version tracking for datasets, models, and configuration files
- Support for retrieving specific versions of objects
- Version locking for regulatory or compliance purposes

### 3.3 Security Model

- Role-based access control (RBAC) with dedicated service accounts
- Training Service will access data using a restricted read-only account
- Data Service will use credentials with write permissions for specific buckets
- MLflow will access storage through dedicated credentials for artifact management
- API key management for all service-to-service communication

### 3.4 GDPR Compliance

- Implement data lifecycle policies for automated retention and deletion
- Support for data subject requests (right to be forgotten)
- Data anonymization capabilities
- Audit trails for all data access and modifications
- Data classification and tagging system

### 3.5 Data Workflow Management

- Clear data ingestion pipelines with validation steps
- Dataset versioning and lineage tracking
- Model training data selection by version
- Experiment tracking with data version references

## 4. Component Definitions

### 4.1 MinIO Storage Manager

**Purpose:** Central data storage and management service that handles all data operations, versioning, and lifecycle management.

**Key Responsibilities:**
- Implement bucket policy management
- Enforce access controls and permissions
- Manage object versioning
- Apply lifecycle policies
- Provide dataset analysis capabilities
- Generate audit logs for compliance
- Handle data subject requests

### 4.2 Data Service

**Purpose:** Responsible for data ingestion, transformation, and storage in a versioned manner.

**Key Responsibilities:**
- Upload datasets to MinIO through the Storage Manager
- Implement data validation and quality checks
- Apply appropriate metadata and tags for classification
- Create versioned datasets using MinIO's versioning capabilities
- Track dataset lineage and transformations

### 4.3 Training Service

**Purpose:** Executes model training using versioned datasets while logging metrics and artifacts.

**Key Responsibilities:**
- Request specific dataset versions from Storage Manager for training
- Retrieve data with read-only permissions
- Execute training jobs with specified parameters
- Log metrics and results to MLflow
- Store trained models as versioned objects

### 4.4 MLflow Tracking Server

**Purpose:** Experiment tracking and model registry with artifacts stored in MinIO.

**Key Responsibilities:**
- Track experiments with dataset version references
- Register models with lineage to training data
- Store artifacts in MinIO with proper versioning
- Provide model comparison and selection capabilities

### 4.5 Orchestrator

**Purpose:** Coordinates workflows between services, managing jobs and pipelines.

**Key Responsibilities:**
- Schedule training jobs
- Manage pipelines that include data processing and training
- Track job status and history
- Provide centralized management interface

## 5. Security Architecture

### 5.1 Service Accounts

1. **minio-admin**: Superuser account for administration (not used by services)
2. **storage-manager-service**: Full access to implement policies and manage objects
3. **data-service-user**: Write access to datasets and metadata buckets
4. **training-service-user**: Read-only access to datasets, write access to model bucket
5. **mlflow-service-user**: Read/write access to mlflow artifact bucket

### 5.2 Access Control Policies

| Service               | Buckets                        | Permissions                        |
|-----------------------|--------------------------------|------------------------------------|
| Storage Manager       | All                            | Full control                       |
| Data Service          | datasets, metadata             | Read/Write                         |
| Training Service      | datasets                       | Read-only                          |
| Training Service      | models                         | Read/Write                         |
| MLflow                | mlflow-artifacts               | Read/Write                         |

## 6. Data Lifecycle Management

### 6.1 Bucket Lifecycle Policies

| Bucket           | Retention Period | Transition   | Expiration |
|------------------|------------------|--------------|------------|
| datasets         | Indefinite       | Archive after 90 days | None |
| models           | 1 year           | Archive after 90 days | 365 days |
| mlflow-artifacts | 1 year           | Archive after 60 days | 365 days |
| temp-data        | 1 day            | None         | 24 hours  |
| logs             | 90 days          | Archive after 30 days | 90 days |

### 6.2 GDPR Request Handling

1. **Identification**: Process to identify all data associated with a subject
2. **Export**: Capability to export all subject data in portable format
3. **Anonymization**: Process to anonymize subject data
4. **Deletion**: Procedure to permanently remove subject data from all systems

## 7. Implementation Considerations

### 7.1 Docker Compose Structure

```
├── docker-compose.yml       # Main configuration
├── minio/                   # MinIO configuration
├── storage-manager/         # Storage Manager service
├── data-service/            # Data handling service
├── training-service/        # Model training service
├── mlflow/                  # MLflow tracking server
└── orchestrator/            # Workflow orchestration
```

### 7.2 Network Security

- Internal Docker network for service-to-service communication
- Limited port exposure to host system
- TLS for all external connections
- API authentication for all service endpoints

### 7.3 Scaling Considerations

- MinIO distributed mode for production scenarios
- Horizontal scaling of services through container orchestration
- Resource limits for training services

## 8. Exam Learning Objectives

Through working with this architecture, students will learn:

1. How to implement secure, versioned data storage using MinIO
2. Proper service isolation and role-based access control
3. Data lifecycle management for compliance purposes
4. Integration patterns between MLOps components
5. Versioning strategies for model development
6. Proper handling of sensitive data in ML workflows
7. Job orchestration and pipeline management

## 9. Next Steps

1. Implement MinIO with versioning enabled
2. Create the Storage Manager service with all required features
3. Configure proper service accounts and permission policies
4. Integrate all services with the Storage Manager
5. Implement and test GDPR compliance features
6. Create example workflows for the exam

## 10. Conclusion

This architecture provides a robust foundation for an MLOps system that emphasizes data governance, security, and proper versioning practices. By centralizing these concerns in the MinIO Storage Manager, we create a system that is both educational for beginners and representative of industry best practices.