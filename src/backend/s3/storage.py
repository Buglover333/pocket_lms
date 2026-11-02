"""Private S3 objects; signed URLs are created only after application access checks."""
import os
import re
import urllib.parse
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
    client = boto3.client(
        's3',
        endpoint_url=os.getenv('S3_ENDPOINT_URL') or None,
        region_name=os.getenv('AWS_DEFAULT_REGION') or 'us-east-1',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID') or None,
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY') or None,
        config=Config(signature_version='s3v4', retries={'max_attempts': 2}),
    )
    return client, bucket


def ensure_bucket_exists(bucket_name: str | None = None) -> None:
    """Проверяет существование бакета в S3/MinIO, и создаёт его при отсутствии."""
    try:
        client, default_bucket = configuration()
        target_bucket = bucket_name or default_bucket
        try:
            client.head_bucket(Bucket=target_bucket)
        except ClientError as exc:
            error_code = str(exc.response.get('Error', {}).get('Code', ''))
            if error_code in ('404', 'NoSuchBucket', 'NotFound'):
                region = os.getenv('AWS_DEFAULT_REGION') or 'us-east-1'
                if region == 'us-east-1':
                    client.create_bucket(Bucket=target_bucket)
                else:
                    client.create_bucket(
                        Bucket=target_bucket,
                        CreateBucketConfiguration={'LocationConstraint': region},
                    )
            else:
                raise
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(503, f'Ошибка инициализации S3 бакета: {exc}') from exc


def upload_url(key: str, mime_type: str):
    try:
        client, bucket = configuration()
        # POST policy enforces size and content type, unlike a bare presigned PUT.
        result = client.generate_presigned_post(
            Bucket=bucket,
            Key=key,
            Fields={'Content-Type': mime_type},
            Conditions=[{'Content-Type': mime_type}, ['content-length-range', 1, MAX_SIZE]],
            ExpiresIn=TTL,
        )
        return bucket, result
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(503, 'Хранилище недоступно') from exc


def download_url(bucket: str, key: str, filename: str | None = None) -> str:
    try:
        client, configured_bucket = configuration()
        if bucket != configured_bucket:
            raise HTTPException(403, 'Недопустимое хранилище')
        params: dict[str, str] = {'Bucket': bucket, 'Key': key}
        if filename:
            clean_filename = re.sub(r'[\r\n\x00-\x1f]', '', filename)
            safe_ascii = clean_filename.encode('ascii', 'ignore').decode('ascii').replace('\\', '_').replace('"', '_').strip()
            if not safe_ascii or safe_ascii.startswith('.'):
                safe_ascii = f'file{safe_ascii}'
            encoded_name = urllib.parse.quote(clean_filename)
            if clean_filename.isascii() and '"' not in clean_filename and '\\' not in clean_filename:
                params['ResponseContentDisposition'] = f'attachment; filename="{safe_ascii}"'
            else:
                params['ResponseContentDisposition'] = f'attachment; filename="{safe_ascii}"; filename*=UTF-8\'\'{encoded_name}'
        return client.generate_presigned_url('get_object', Params=params, ExpiresIn=TTL)
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(503, 'Хранилище недоступно') from exc


def verify_upload(bucket: str, key: str, expected_size: int, mime_type: str) -> None:
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


def delete_file_from_s3(bucket: str, key: str) -> None:
    """Удалить объект из S3/MinIO хранилища."""
    try:
        client, configured_bucket = configuration()
        if bucket != configured_bucket:
            raise HTTPException(403, 'Недопустимое хранилище')
        client.delete_object(Bucket=bucket, Key=key)
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(503, 'Хранилище недоступно') from exc
