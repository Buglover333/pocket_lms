"""Private S3 objects; signed URLs are created only after application access checks."""
import os
import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException

TTL = 300
MAX_SIZE = 50 * 1024 * 1024

def configuration():
    bucket = os.getenv('S3_BUCKET')
    if not bucket:
        raise HTTPException(503, 'S3_BUCKET не настроен')
    client = boto3.client('s3', endpoint_url=os.getenv('S3_ENDPOINT_URL') or None,
                          region_name=os.getenv('AWS_DEFAULT_REGION', 'us-east-1'),
                          config=Config(signature_version='s3v4', retries={'max_attempts': 2}))
    return client, bucket

def upload_url(key, mime_type):
    try:
        client, bucket = configuration()
        # POST policy enforces size and content type, unlike a bare presigned PUT.
        result = client.generate_presigned_post(
            Bucket=bucket, Key=key,
            Fields={'Content-Type': mime_type},
            Conditions=[{'Content-Type': mime_type}, ['content-length-range', 1, MAX_SIZE]],
            ExpiresIn=TTL)
        return bucket, result
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(503, 'Хранилище недоступно') from exc

def download_url(bucket, key):
    try:
        client, configured_bucket = configuration()
        if bucket != configured_bucket:
            raise HTTPException(403, 'Недопустимое хранилище')
        return client.generate_presigned_url('get_object', Params={'Bucket': bucket, 'Key': key}, ExpiresIn=TTL)
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(503, 'Хранилище недоступно') from exc

def verify_upload(bucket, key, expected_size, mime_type):
    try:
        client, configured_bucket = configuration()
        if bucket != configured_bucket:
            raise HTTPException(403, 'Недопустимое хранилище')
        info = client.head_object(Bucket=bucket, Key=key)
        if info['ContentLength'] != expected_size or info.get('ContentType') != mime_type:
            raise HTTPException(409, 'Размер или тип загруженного файла не совпадает')
    except ClientError as exc:
        if exc.response.get('Error', {}).get('Code') in ('404', 'NoSuchKey', 'NotFound'):
            raise HTTPException(409, 'Файл ещё не загружен') from exc
        raise HTTPException(503, 'Хранилище недоступно') from exc
    except BotoCoreError as exc:
        raise HTTPException(503, 'Хранилище недоступно') from exc
