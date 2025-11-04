import os
import logging
import functools

import boto3

from bare_metal_billing import config

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@functools.lru_cache
def get_bucket(bucket_name: str):
    if not config.S3_LEASE_APP_KEY or not config.S3_LEASE_KEY_ID:
        raise RuntimeError(
            "Please set the environment variables S3_LEASE_APP_KEY, S3_LEASE_KEY_ID"
        )

    s3_resource = boto3.resource(
        service_name="s3",
        endpoint_url=config.S3_LEASE_ENDPOINT_URL,
        aws_access_key_id=config.S3_LEASE_KEY_ID,
        aws_secret_access_key=config.S3_LEASE_APP_KEY,
    )

    return s3_resource.Bucket(bucket_name)


def fetch_s3(bucket_name: str, s3_filepath: str) -> str:
    local_name = os.path.basename(s3_filepath)
    lease_bucket = get_bucket(bucket_name)
    lease_bucket.download_file(s3_filepath, local_name)
    return local_name
