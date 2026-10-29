"""Тесты для модуля файлового хранилища S3 (MinIO) и роутера файлов."""

import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

from botocore.exceptions import ClientError
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.api.dependencies import (
    DEFAULT_MOCK_USER,
    get_connection,
    get_current_user,
    get_mock_current_user,
)
from backend.api.main import app
from backend.s3 import storage


class StorageServiceUnitTests(unittest.TestCase):
    """Модульные тесты сервисного слоя storage.py с мокированием boto3."""

    def setUp(self):
        self.bucket = "test-bucket"
        self.env_patcher = patch.dict(
            os.environ,
            {
                "S3_BUCKET": self.bucket,
                "S3_ENDPOINT_URL": "http://localhost:9000",
                "AWS_ACCESS_KEY_ID": "minioadmin",
                "AWS_SECRET_ACCESS_KEY": "minioadmin",
                "AWS_DEFAULT_REGION": "us-east-1",
            },
        )
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()

    def test_configuration_missing_bucket(self):
        with patch.dict(os.environ, {"S3_BUCKET": ""}):
            with self.assertRaises(HTTPException) as ctx:
                storage.configuration()
            self.assertEqual(ctx.exception.status_code, 503)

    @patch("backend.s3.storage.boto3.client")
    def test_configuration_with_credentials(self, mock_boto):
        mock_client = MagicMock()
        mock_boto.return_value = mock_client

        client, bucket = storage.configuration()
        self.assertEqual(bucket, "test-bucket")
        mock_boto.assert_called_once()
        _, kwargs = mock_boto.call_args
        self.assertEqual(kwargs["endpoint_url"], "http://localhost:9000")
        self.assertEqual(kwargs["aws_access_key_id"], "minioadmin")
        self.assertEqual(kwargs["aws_secret_access_key"], "minioadmin")
        self.assertEqual(kwargs["region_name"], "us-east-1")

    @patch("backend.s3.storage.configuration")
    def test_upload_url_generates_presigned_post(self, mock_cfg):
        mock_client = MagicMock()
        mock_client.generate_presigned_post.return_value = {
            "url": "http://localhost:9000/test-bucket",
            "fields": {"key": "uploads/123/file.pdf", "Content-Type": "application/pdf"},
        }
        mock_cfg.return_value = (mock_client, self.bucket)

        bucket, result = storage.upload_url("uploads/123/file.pdf", "application/pdf")
        self.assertEqual(bucket, self.bucket)
        self.assertIn("url", result)
        self.assertIn("fields", result)
        mock_client.generate_presigned_post.assert_called_once_with(
            Bucket=self.bucket,
            Key="uploads/123/file.pdf",
            Fields={"Content-Type": "application/pdf"},
            Conditions=[{"Content-Type": "application/pdf"}, ["content-length-range", 1, storage.MAX_SIZE]],
            ExpiresIn=storage.TTL,
        )

    @patch("backend.s3.storage.configuration")
    def test_download_url_generates_presigned_get(self, mock_cfg):
        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = "http://localhost:9000/signed-download"
        mock_cfg.return_value = (mock_client, self.bucket)

        url = storage.download_url(self.bucket, "uploads/123/file.pdf", filename="report.pdf")
        self.assertEqual(url, "http://localhost:9000/signed-download")
        mock_client.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": "uploads/123/file.pdf",
                "ResponseContentDisposition": 'attachment; filename="report.pdf"',
            },
            ExpiresIn=storage.TTL,
        )

    @patch("backend.s3.storage.configuration")
    def test_download_url_wrong_bucket_raises_403(self, mock_cfg):
        mock_cfg.return_value = (MagicMock(), "allowed-bucket")
        with self.assertRaises(HTTPException) as ctx:
            storage.download_url("foreign-bucket", "some-key")
        self.assertEqual(ctx.exception.status_code, 403)

    @patch("backend.s3.storage.configuration")
    def test_verify_upload_success(self, mock_cfg):
        mock_client = MagicMock()
        mock_client.head_object.return_value = {
            "ContentLength": 1024,
            "ContentType": "application/pdf",
        }
        mock_cfg.return_value = (mock_client, self.bucket)

        storage.verify_upload(self.bucket, "uploads/key", 1024, "application/pdf")
        mock_client.head_object.assert_called_once_with(Bucket=self.bucket, Key="uploads/key")

    @patch("backend.s3.storage.configuration")
    def test_verify_upload_size_mismatch(self, mock_cfg):
        mock_client = MagicMock()
        mock_client.head_object.return_value = {
            "ContentLength": 500,
            "ContentType": "application/pdf",
        }
        mock_cfg.return_value = (mock_client, self.bucket)

        with self.assertRaises(HTTPException) as ctx:
            storage.verify_upload(self.bucket, "uploads/key", 1024, "application/pdf")
        self.assertEqual(ctx.exception.status_code, 409)

    @patch("backend.s3.storage.configuration")
    def test_verify_upload_not_found(self, mock_cfg):
        mock_client = MagicMock()
        error_resp = {"Error": {"Code": "404", "Message": "Not Found"}}
        mock_client.head_object.side_effect = ClientError(error_resp, "HeadObject")
        mock_cfg.return_value = (mock_client, self.bucket)

        with self.assertRaises(HTTPException) as ctx:
            storage.verify_upload(self.bucket, "uploads/key", 1024, "application/pdf")
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("ещё не загружен", ctx.exception.detail)

    @patch("backend.s3.storage.configuration")
    def test_delete_file_from_s3(self, mock_cfg):
        mock_client = MagicMock()
        mock_cfg.return_value = (mock_client, self.bucket)

        storage.delete_file_from_s3(self.bucket, "uploads/123/file.pdf")
        mock_client.delete_object.assert_called_once_with(Bucket=self.bucket, Key="uploads/123/file.pdf")

    @patch("backend.s3.storage.configuration")
    def test_ensure_bucket_exists_when_bucket_already_exists(self, mock_cfg):
        mock_client = MagicMock()
        mock_cfg.return_value = (mock_client, self.bucket)

        storage.ensure_bucket_exists(self.bucket)
        mock_client.head_bucket.assert_called_once_with(Bucket=self.bucket)
        mock_client.create_bucket.assert_not_called()

    @patch("backend.s3.storage.configuration")
    def test_ensure_bucket_exists_when_bucket_missing(self, mock_cfg):
        mock_client = MagicMock()
        error_resp = {"Error": {"Code": "404", "Message": "Not Found"}}
        mock_client.head_bucket.side_effect = ClientError(error_resp, "HeadBucket")
        mock_cfg.return_value = (mock_client, self.bucket)

        storage.ensure_bucket_exists(self.bucket)
        mock_client.head_bucket.assert_called_once_with(Bucket=self.bucket)
        mock_client.create_bucket.assert_called_once_with(Bucket=self.bucket)


class FilesAuthAndRouterTests(unittest.TestCase):
    """Интеграционные тесты обязательной авторизации и mock-зависимости get_current_user."""

    def setUp(self):
        self.client = TestClient(app)
        self.mock_user = {
            "id": uuid4(),
            "email": "teacher@pocket-lms.local",
            "name": "Тестовый Преподаватель",
            "role": "teacher",
            "is_admin": True,
            "is_active": True,
        }
        self.fake_conn = AsyncMock()
        app.dependency_overrides[get_connection] = lambda: self.fake_conn

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_all_file_endpoints_require_authorization(self):
        """Проверка требования: доступ ко всем эндпоинтам хранилища строго авторизован."""
        endpoints = [
            ("POST", "/create_file_upload", {"json": {"file_name": "test.pdf", "file_type": "document", "mime_type": "application/pdf", "size_bytes": 100}}),
            ("POST", "/complete_file_upload", {"params": {"file_id": str(uuid4())}}),
            ("GET", "/get_file", {"params": {"file_id": str(uuid4())}}),
            ("GET", "/get_file_download", {"params": {"file_id": str(uuid4())}}),
            ("DELETE", "/delete_file", {"params": {"file_id": str(uuid4())}}),
            ("POST", "/upload_file", {"json": {"file_name": "test.pdf", "file_type": "document", "mime_type": "application/pdf", "size_bytes": 100, "url": "https://example.com/test.pdf"}}),
        ]

        for method, url, kwargs in endpoints:
            with self.subTest(method=method, url=url):
                # Без заголовка Authorization должен возвращаться 401
                resp = self.client.request(method, url, **kwargs)
                self.assertEqual(resp.status_code, 401, f"{method} {url} вернул {resp.status_code} вместо 401")
                self.assertIn("WWW-Authenticate", resp.headers)

    def test_mock_get_current_user_with_dev_token(self):
        """Проверка изолированной заглушки: при передаче dev-токена возвращается mock-пользователь."""
        with patch("backend.api.routers.files.attachment_write_access"):
            with patch("backend.s3.storage.upload_url", return_value=("test-bucket", {"url": "http://minio/upload", "fields": {}})):
                with patch("backend.db.methods.create_file", return_value={"id": uuid4()}):
                    resp = self.client.post(
                        "/create_file_upload",
                        json={"file_name": "test.pdf", "file_type": "document", "mime_type": "application/pdf", "size_bytes": 100},
                        headers={"Authorization": "Bearer dev-token"},
                    )
                    self.assertEqual(resp.status_code, 201)
                    data = resp.json()
                    self.assertIn("upload_url", data)
                    self.assertIn("file_id", data)

    def test_delete_file_triggers_s3_deletion(self):
        """Проверка, что удаление файла в S3 очищает и объект из хранилища."""
        file_id = uuid4()
        fake_record = {
            "id": file_id,
            "uploader_id": DEFAULT_MOCK_USER["id"],
            "lesson_id": None,
            "submission_id": None,
            "meta": {"storage": "s3", "bucket": "test-bucket", "key": "uploads/user/file.pdf"},
        }
        with patch("backend.api.routers.files.file_access", return_value=fake_record):
            with patch("backend.db.methods.delete_file", return_value=True):
                with patch("backend.s3.storage.delete_file_from_s3") as mock_s3_del:
                    resp = self.client.delete(
                        "/delete_file",
                        params={"file_id": str(file_id)},
                        headers={"Authorization": "Bearer dev-token"},
                    )
                    self.assertEqual(resp.status_code, 200)
                    self.assertEqual(resp.json(), {"ok": True})
                    mock_s3_del.assert_called_once_with("test-bucket", "uploads/user/file.pdf")


if __name__ == "__main__":
    unittest.main()
