import os

# S3 Configuration
S3_LEASE_ENDPOINT_URL = os.getenv(
    "S3_LEASE_ENDPOINT_URL", "https://s3.us-east-005.backblazeb2.com"
)
S3_LEASE_KEY_ID = os.getenv("S3_LEASE_KEY_ID")
S3_LEASE_APP_KEY = os.getenv("S3_LEASE_APP_KEY")
S3_LEASE_BUCKET = os.getenv("S3_LEASE_BUCKET")
