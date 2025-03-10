from setuptools import setup, find_packages

setup(
    name="nyc_taxi_mlops",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "pandas",
        "scikit-learn",
        "mlflow",
        "minio",
        "python-dotenv",
        "requests",
    ],
    python_requires=">=3.9",
    description="NYC Taxi MLOps Pipeline with MinIO",
    author="NYC Taxi MLOps Team",
)
