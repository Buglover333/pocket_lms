"""Исчерпывающие тесты S3 хранилища (storage.py), роутера файлов (files.py) и сквозной интеграции."""

import os
import re
import socket
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import boto3
from botocore.exceptions import BotoCoreError, ClientError, EndpointConnectionError
from fastapi import HTTPException
from fastapi.testclient import TestClient
import requests

from backend.api.dependencies import (
    DEFAULT_MOCK_USER,
    get_connection,
    get_current_user,
    get_mock_current_user,
)
from backend.api.main import app
from backend.services import storage


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class StorageServiceUnitTests(unittest.TestCase):
    """Модульные тесты сервисного слоя storage.py."""

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
            self.assertIn("S3_BUCKET не настроен", ctx.exception.detail)

    @patch("backend.services.storage.boto3.client")
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

    @patch("backend.services.storage.boto3.client")
    def test_configuration_empty_string_endpoint_fallback_to_none(self, mock_boto):
        with patch.dict(os.environ, {"S3_ENDPOINT_URL": "", "AWS_ACCESS_KEY_ID": "", "AWS_SECRET_ACCESS_KEY": ""}):
            storage.configuration()
            _, kwargs = mock_boto.call_args
            self.assertIsNone(kwargs["endpoint_url"])
            self.assertIsNone(kwargs["aws_access_key_id"])
            self.assertIsNone(kwargs["aws_secret_access_key"])

    @patch("backend.services.storage.configuration")
    def test_ensure_bucket_exists_when_bucket_already_exists(self, mock_cfg):
        mock_client = MagicMock()
        mock_cfg.return_value = (mock_client, self.bucket)

        storage.ensure_bucket_exists(self.bucket)
        mock_client.head_bucket.assert_called_once_with(Bucket=self.bucket)
        mock_client.create_bucket.assert_not_called()

    @patch("backend.services.storage.configuration")
    def test_ensure_bucket_exists_when_bucket_missing_us_east_1(self, mock_cfg):
        mock_client = MagicMock()
        error_resp = {"Error": {"Code": "404", "Message": "Not Found"}}
        mock_client.head_bucket.side_effect = ClientError(error_resp, "HeadBucket")
        mock_cfg.return_value = (mock_client, self.bucket)

        storage.ensure_bucket_exists(self.bucket)
        mock_client.head_bucket.assert_called_once_with(Bucket=self.bucket)
        mock_client.create_bucket.assert_called_once_with(Bucket=self.bucket)

    @patch("backend.services.storage.configuration")
    def test_ensure_bucket_exists_when_bucket_missing_other_region(self, mock_cfg):
        mock_client = MagicMock()
        error_resp = {"Error": {"Code": "NoSuchBucket", "Message": "Not Found"}}
        mock_client.head_bucket.side_effect = ClientError(error_resp, "HeadBucket")
        mock_cfg.return_value = (mock_client, self.bucket)

        with patch.dict(os.environ, {"AWS_DEFAULT_REGION": "eu-central-1"}):
            storage.ensure_bucket_exists(self.bucket)
            mock_client.head_bucket.assert_called_once_with(Bucket=self.bucket)
            mock_client.create_bucket.assert_called_once_with(
                Bucket=self.bucket,
                CreateBucketConfiguration={"LocationConstraint": "eu-central-1"},
            )

    @patch("backend.services.storage.configuration")
    def test_ensure_bucket_exists_permission_denied(self, mock_cfg):
        mock_client = MagicMock()
        error_resp = {"Error": {"Code": "403", "Message": "Forbidden"}}
        mock_client.head_bucket.side_effect = ClientError(error_resp, "HeadBucket")
        mock_cfg.return_value = (mock_client, self.bucket)

        with self.assertRaises(HTTPException) as ctx:
            storage.ensure_bucket_exists(self.bucket)
        self.assertEqual(ctx.exception.status_code, 503)
        self.assertIn("Ошибка инициализации S3 бакета", ctx.exception.detail)

    @patch("backend.services.storage.configuration")
    def test_ensure_bucket_exists_endpoint_connection_error(self, mock_cfg):
        mock_client = MagicMock()
        mock_client.head_bucket.side_effect = EndpointConnectionError(endpoint_url="http://bad-host:9000")
        mock_cfg.return_value = (mock_client, self.bucket)

        with self.assertRaises(HTTPException) as ctx:
            storage.ensure_bucket_exists(self.bucket)
        self.assertEqual(ctx.exception.status_code, 503)

    @patch("backend.services.storage.configuration")
    def test_upload_url_conditions_and_fields(self, mock_cfg):
        mock_client = MagicMock()
        mock_client.generate_presigned_post.return_value = {
            "url": "http://localhost:9000/test-bucket",
            "fields": {"key": "uploads/123/file.pdf", "Content-Type": "application/pdf"},
        }
        mock_cfg.return_value = (mock_client, self.bucket)

        bucket, result = storage.upload_url("uploads/123/file.pdf", "application/pdf")
        self.assertEqual(bucket, self.bucket)
        self.assertEqual(result["url"], "http://localhost:9000/test-bucket")
        mock_client.generate_presigned_post.assert_called_once_with(
            Bucket=self.bucket,
            Key="uploads/123/file.pdf",
            Fields={"Content-Type": "application/pdf"},
            Conditions=[{"Content-Type": "application/pdf"}, ["content-length-range", 1, storage.MAX_SIZE]],
            ExpiresIn=storage.TTL,
        )

    @patch("backend.services.storage.configuration")
    def test_upload_url_client_error_raises_503(self, mock_cfg):
        mock_client = MagicMock()
        mock_client.generate_presigned_post.side_effect = ClientError({"Error": {"Code": "500"}}, "Generate")
        mock_cfg.return_value = (mock_client, self.bucket)

        with self.assertRaises(HTTPException) as ctx:
            storage.upload_url("uploads/123/file.pdf", "application/pdf")
        self.assertEqual(ctx.exception.status_code, 503)
        self.assertEqual(ctx.exception.detail, "Хранилище недоступно")

    @patch("backend.services.storage.configuration")
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

    @patch("backend.services.storage.configuration")
    def test_download_url_no_filename(self, mock_cfg):
        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = "http://localhost:9000/signed-download"
        mock_cfg.return_value = (mock_client, self.bucket)

        url = storage.download_url(self.bucket, "uploads/123/file.pdf", filename=None)
        self.assertEqual(url, "http://localhost:9000/signed-download")
        mock_client.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": self.bucket, "Key": "uploads/123/file.pdf"},
            ExpiresIn=storage.TTL,
        )

    @patch("backend.services.storage.configuration")
    def test_download_url_escapes_quotes_and_special_chars(self, mock_cfg):
        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = "http://localhost:9000/signed-download"
        mock_cfg.return_value = (mock_client, self.bucket)

        storage.download_url(self.bucket, "uploads/123/file.pdf", filename='my "cool" file.pdf')
        _, kwargs = mock_client.generate_presigned_url.call_args
        self.assertEqual(
            kwargs["Params"]["ResponseContentDisposition"],
            'attachment; filename="my _cool_ file.pdf"; filename*=UTF-8\'\'my%20%22cool%22%20file.pdf',
        )

    @patch("backend.services.storage.configuration")
    def test_download_url_wrong_bucket_raises_403(self, mock_cfg):
        mock_cfg.return_value = (MagicMock(), "allowed-bucket")
        with self.assertRaises(HTTPException) as ctx:
            storage.download_url("foreign-bucket", "some-key")
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(ctx.exception.detail, "Недопустимое хранилище")

    @patch("backend.services.storage.configuration")
    def test_verify_upload_success(self, mock_cfg):
        mock_client = MagicMock()
        mock_client.head_object.return_value = {
            "ContentLength": 1024,
            "ContentType": "application/pdf",
        }
        mock_cfg.return_value = (mock_client, self.bucket)

        storage.verify_upload(self.bucket, "uploads/key", 1024, "application/pdf")
        mock_client.head_object.assert_called_once_with(Bucket=self.bucket, Key="uploads/key")

    @patch("backend.services.storage.configuration")
    def test_verify_upload_foreign_bucket_raises_403(self, mock_cfg):
        mock_cfg.return_value = (MagicMock(), "my-bucket")
        with self.assertRaises(HTTPException) as ctx:
            storage.verify_upload("alien-bucket", "uploads/key", 1024, "application/pdf")
        self.assertEqual(ctx.exception.status_code, 403)

    @patch("backend.services.storage.configuration")
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
        self.assertEqual(ctx.exception.detail, "Размер или тип загруженного файла не совпадает")

    @patch("backend.services.storage.configuration")
    def test_verify_upload_mime_mismatch(self, mock_cfg):
        mock_client = MagicMock()
        mock_client.head_object.return_value = {
            "ContentLength": 1024,
            "ContentType": "text/plain",
        }
        mock_cfg.return_value = (mock_client, self.bucket)

        with self.assertRaises(HTTPException) as ctx:
            storage.verify_upload(self.bucket, "uploads/key", 1024, "application/pdf")
        self.assertEqual(ctx.exception.status_code, 409)

    @patch("backend.services.storage.configuration")
    def test_verify_upload_not_found_404(self, mock_cfg):
        mock_client = MagicMock()
        error_resp = {"Error": {"Code": "404", "Message": "Not Found"}}
        mock_client.head_object.side_effect = ClientError(error_resp, "HeadObject")
        mock_cfg.return_value = (mock_client, self.bucket)

        with self.assertRaises(HTTPException) as ctx:
            storage.verify_upload(self.bucket, "uploads/key", 1024, "application/pdf")
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("ещё не загружен", ctx.exception.detail)

    @patch("backend.services.storage.configuration")
    def test_verify_upload_not_found_NoSuchKey(self, mock_cfg):
        mock_client = MagicMock()
        error_resp = {"Error": {"Code": "NoSuchKey", "Message": "Not Found"}}
        mock_client.head_object.side_effect = ClientError(error_resp, "HeadObject")
        mock_cfg.return_value = (mock_client, self.bucket)

        with self.assertRaises(HTTPException) as ctx:
            storage.verify_upload(self.bucket, "uploads/key", 1024, "application/pdf")
        self.assertEqual(ctx.exception.status_code, 409)

    @patch("backend.services.storage.configuration")
    def test_verify_upload_s3_error_500(self, mock_cfg):
        mock_client = MagicMock()
        error_resp = {"Error": {"Code": "500", "Message": "Internal Server Error"}}
        mock_client.head_object.side_effect = ClientError(error_resp, "HeadObject")
        mock_cfg.return_value = (mock_client, self.bucket)

        with self.assertRaises(HTTPException) as ctx:
            storage.verify_upload(self.bucket, "uploads/key", 1024, "application/pdf")
        self.assertEqual(ctx.exception.status_code, 503)

    @patch("backend.services.storage.configuration")
    def test_delete_file_from_s3_success(self, mock_cfg):
        mock_client = MagicMock()
        mock_cfg.return_value = (mock_client, self.bucket)

        storage.delete_file_from_s3(self.bucket, "uploads/123/file.pdf")
        mock_client.delete_object.assert_called_once_with(Bucket=self.bucket, Key="uploads/123/file.pdf")

    @patch("backend.services.storage.configuration")
    def test_delete_file_from_s3_foreign_bucket_raises_403(self, mock_cfg):
        mock_cfg.return_value = (MagicMock(), "my-bucket")
        with self.assertRaises(HTTPException) as ctx:
            storage.delete_file_from_s3("alien-bucket", "uploads/key")
        self.assertEqual(ctx.exception.status_code, 403)

    @patch("backend.services.storage.configuration")
    def test_delete_file_from_s3_error_raises_503(self, mock_cfg):
        mock_client = MagicMock()
        mock_client.delete_object.side_effect = ClientError({"Error": {"Code": "500"}}, "DeleteObject")
        mock_cfg.return_value = (mock_client, self.bucket)

        with self.assertRaises(HTTPException) as ctx:
            storage.delete_file_from_s3(self.bucket, "uploads/key")
        self.assertEqual(ctx.exception.status_code, 503)


class FilesRouterAccessAndValidationTests(unittest.TestCase):
    """Тесты роутера файлов: права доступа, валидация схем, обработка ошибок."""

    def setUp(self):
        self.client = TestClient(app)
        self.fake_conn = AsyncMock()
        app.dependency_overrides[get_connection] = lambda: self.fake_conn
        self.user_id = uuid4()
        self.other_user_id = uuid4()

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_all_file_endpoints_require_authorization(self):
        """Неавторизованный запрос возвращает 401 на всех путях."""
        endpoints = [
            ("POST", "/create_file_upload", {"json": {"file_name": "a.pdf", "file_type": "document", "mime_type": "application/pdf", "size_bytes": 100}}),
            ("POST", "/complete_file_upload", {"params": {"file_id": str(uuid4())}}),
            ("GET", "/get_file", {"params": {"file_id": str(uuid4())}}),
            ("GET", "/get_file_download", {"params": {"file_id": str(uuid4())}}),
            ("DELETE", "/delete_file", {"params": {"file_id": str(uuid4())}}),
            ("POST", "/upload_file", {"json": {"file_name": "a.pdf", "file_type": "document", "mime_type": "application/pdf", "size_bytes": 100, "url": "https://example.com/a.pdf"}}),
        ]
        for method, url, kwargs in endpoints:
            with self.subTest(method=method, url=url):
                resp = self.client.request(method, url, **kwargs)
                self.assertEqual(resp.status_code, 401)
                self.assertIn("WWW-Authenticate", resp.headers)

    def test_upload_file_rejects_s3_scheme_or_s3_meta(self):
        """POST /upload_file отклоняет s3: схему и метаданные S3."""
        # Попытка передать s3: схему
        resp = self.client.post(
            "/upload_file",
            json={"file_name": "doc.pdf", "file_type": "document", "url": "s3://my-bucket/key", "size_bytes": 100},
            headers={"Authorization": "Bearer dev-token"},
        )
        self.assertEqual(resp.status_code, 422)
        self.assertIn("Для S3 используйте /create_file_upload", resp.json()["detail"])

        # Попытка подделать s3 метаданные
        resp2 = self.client.post(
            "/upload_file",
            json={
                "file_name": "doc.pdf",
                "file_type": "document",
                "url": "https://example.com/doc.pdf",
                "meta": {"storage": "s3", "bucket": "b"},
            },
            headers={"Authorization": "Bearer dev-token"},
        )
        self.assertEqual(resp2.status_code, 422)

        # Не-HTTP(S) ссылка (например, ftp://)
        resp3 = self.client.post(
            "/upload_file",
            json={"file_name": "doc.pdf", "file_type": "document", "url": "ftp://files.example.com/doc.pdf"},
            headers={"Authorization": "Bearer dev-token"},
        )
        self.assertEqual(resp3.status_code, 422)
        self.assertIn("Ожидается внешняя HTTP-ссылка", resp3.json()["detail"])

    def test_create_file_upload_input_validation(self):
        """POST /create_file_upload валидирует размер, mime_type, имя."""
        headers = {"Authorization": "Bearer dev-token"}

        # Размер 0
        resp = self.client.post(
            "/create_file_upload",
            json={"file_name": "doc.pdf", "file_type": "document", "mime_type": "application/pdf", "size_bytes": 0},
            headers=headers,
        )
        self.assertEqual(resp.status_code, 422)

        # Отрицательный размер
        resp = self.client.post(
            "/create_file_upload",
            json={"file_name": "doc.pdf", "file_type": "document", "mime_type": "application/pdf", "size_bytes": -10},
            headers=headers,
        )
        self.assertEqual(resp.status_code, 422)

        # Размер больше 50MB
        resp = self.client.post(
            "/create_file_upload",
            json={"file_name": "doc.pdf", "file_type": "document", "mime_type": "application/pdf", "size_bytes": 50 * 1024 * 1024 + 1},
            headers=headers,
        )
        self.assertEqual(resp.status_code, 422)

        # Недопустимый MIME-тип
        resp = self.client.post(
            "/create_file_upload",
            json={"file_name": "doc.pdf", "file_type": "document", "mime_type": "not-a-mime", "size_bytes": 100},
            headers=headers,
        )
        self.assertEqual(resp.status_code, 422)

        # Пустое имя файла
        resp = self.client.post(
            "/create_file_upload",
            json={"file_name": "", "file_type": "document", "mime_type": "application/pdf", "size_bytes": 100},
            headers=headers,
        )
        self.assertEqual(resp.status_code, 422)

        # Оба ID (lesson_id и submission_id) одновременно
        resp = self.client.post(
            "/create_file_upload",
            json={
                "file_name": "doc.pdf",
                "file_type": "document",
                "mime_type": "application/pdf",
                "size_bytes": 100,
                "lesson_id": str(uuid4()),
                "submission_id": str(uuid4()),
            },
            headers=headers,
        )
        self.assertEqual(resp.status_code, 422)
        self.assertIn("только к одному объекту", resp.json()["detail"])

    def test_complete_file_upload_forbidden_for_other_user(self):
        """Подтвердить загрузку в S3 может только отправитель."""
        file_id = uuid4()
        fake_record = {
            "id": file_id,
            "uploader_id": uuid4(),  # Другой пользователь
            "lesson_id": None,
            "submission_id": None,
            "size_bytes": 100,
            "mime_type": "application/pdf",
            "meta": {"storage": "s3", "bucket": "test-bucket", "key": "uploads/other/file.pdf"},
        }
        with patch("backend.api.routers.files.file_access", return_value=fake_record):
            resp = self.client.post(
                "/complete_file_upload",
                params={"file_id": str(file_id)},
                headers={"Authorization": "Bearer dev-token"},
            )
            self.assertEqual(resp.status_code, 403)
            self.assertIn("только отправитель", resp.json()["detail"])

    def test_complete_file_upload_rejects_non_s3_file(self):
        """Нельзя вызвать complete_file_upload для внешнего файла."""
        file_id = uuid4()
        fake_record = {
            "id": file_id,
            "uploader_id": DEFAULT_MOCK_USER["id"],
            "lesson_id": None,
            "submission_id": None,
            "meta": {"storage": "external"},
        }
        with patch("backend.api.routers.files.file_access", return_value=fake_record):
            resp = self.client.post(
                "/complete_file_upload",
                params={"file_id": str(file_id)},
                headers={"Authorization": "Bearer dev-token"},
            )
            self.assertEqual(resp.status_code, 422)
            self.assertIn("не загрузка S3", resp.json()["detail"])

    def test_get_file_download_pending_raises_409(self):
        """GET /get_file_download для неподтверждённого S3 файла возвращает 409."""
        file_id = uuid4()
        fake_record = {
            "id": file_id,
            "uploader_id": DEFAULT_MOCK_USER["id"],
            "lesson_id": None,
            "submission_id": None,
            "meta": {"storage": "s3", "bucket": "test-bucket", "key": "key", "upload_status": "pending"},
        }
        with patch("backend.api.routers.files.file_access", return_value=fake_record):
            resp = self.client.get(
                "/get_file_download",
                params={"file_id": str(file_id)},
                headers={"Authorization": "Bearer dev-token"},
            )
            self.assertEqual(resp.status_code, 409)
            self.assertIn("ещё не подтверждена", resp.json()["detail"])

    def test_get_file_download_external_url_returns_directly(self):
        """GET /get_file_download для внешнего файла возвращает прямую ссылку без expires_in."""
        file_id = uuid4()
        fake_record = {
            "id": file_id,
            "uploader_id": DEFAULT_MOCK_USER["id"],
            "lesson_id": None,
            "submission_id": None,
            "url": "https://cdn.example.com/doc.pdf",
            "meta": None,
        }
        with patch("backend.api.routers.files.file_access", return_value=fake_record):
            resp = self.client.get(
                "/get_file_download",
                params={"file_id": str(file_id)},
                headers={"Authorization": "Bearer dev-token"},
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data["download_url"], "https://cdn.example.com/doc.pdf")
            self.assertIsNone(data["expires_in"])


class LiveS3EndToEndHttpTests(unittest.TestCase):
    """Сквозные тесты полного цикла с настоящим HTTP S3 сервером (ThreadedMotoServer)."""

    @classmethod
    def setUpClass(cls):
        from moto.server import ThreadedMotoServer

        cls.port = find_free_port()
        cls.endpoint_url = f"http://127.0.0.1:{cls.port}"
        cls.bucket = "pocket-lms-media"
        cls.server = ThreadedMotoServer(ip_address="127.0.0.1", port=cls.port)
        cls.server.start()

        # Создаём тестовый бакет в S3
        cls.s3_client = boto3.client(
            "s3",
            endpoint_url=cls.endpoint_url,
            region_name="us-east-1",
            aws_access_key_id="minioadmin",
            aws_secret_access_key="minioadmin",
        )
        cls.s3_client.create_bucket(Bucket=cls.bucket)

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def setUp(self):
        self.env_patcher = patch.dict(
            os.environ,
            {
                "S3_BUCKET": self.bucket,
                "S3_ENDPOINT_URL": self.endpoint_url,
                "AWS_ACCESS_KEY_ID": "minioadmin",
                "AWS_SECRET_ACCESS_KEY": "minioadmin",
                "AWS_DEFAULT_REGION": "us-east-1",
            },
        )
        self.env_patcher.start()

        self.client = TestClient(app)
        self.fake_conn = AsyncMock()
        app.dependency_overrides[get_connection] = lambda: self.fake_conn

    def tearDown(self):
        self.env_patcher.stop()
        app.dependency_overrides.clear()

    def test_full_s3_upload_complete_download_delete_lifecycle(self):
        """Полный сквозной цикл:
        1. create_file_upload -> получение presigned POST формы
        2. Реальный HTTP POST multipart запрос файла в S3
        3. complete_file_upload -> реальный S3 HEAD и подтверждение
        4. get_file_download -> получение presigned GET URL
        5. Реальный HTTP GET скачивание и побайтовое совпадение
        6. delete_file -> реальный DELETE в S3 и проверка отсутствия объекта
        """
        file_payload = b"Sample assignment solution binary payload 2026 \x00\x01\x02\xff"
        payload_size = len(file_payload)
        file_name = "homework_solution.pdf"
        mime_type = "application/pdf"
        file_id = uuid4()
        user_id = DEFAULT_MOCK_USER["id"]

        db_storage = {}

        async def mock_create_file(conn, req):
            rec = {
                "id": file_id,
                "uploader_id": user_id,
                "lesson_id": req.lesson_id,
                "submission_id": req.submission_id,
                "file_type": req.file_type,
                "url": req.url,
                "file_name": req.file_name,
                "size_bytes": req.size_bytes,
                "mime_type": req.mime_type,
                "meta": req.meta,
                "created_at": "2026-10-29T10:00:00Z",
            }
            db_storage[file_id] = rec
            return rec

        async def mock_get_file_by_id(conn, fid):
            return db_storage.get(fid)

        async def mock_complete_file_upload(conn, fid):
            if fid in db_storage:
                db_storage[fid]["meta"]["upload_status"] = "ready"
                return db_storage[fid]
            return None

        async def mock_delete_file(conn, fid):
            return db_storage.pop(fid, None) is not None

        with patch("backend.db.methods.create_file", side_effect=mock_create_file), \
             patch("backend.db.methods.get_file_by_id", side_effect=mock_get_file_by_id), \
             patch("backend.db.methods.complete_file_upload", side_effect=mock_complete_file_upload), \
             patch("backend.db.methods.delete_file", side_effect=mock_delete_file):

            # Шаг 1: Запрос presigned POST
            create_resp = self.client.post(
                "/create_file_upload",
                json={
                    "file_name": file_name,
                    "file_type": "document",
                    "mime_type": mime_type,
                    "size_bytes": payload_size,
                },
                headers={"Authorization": "Bearer dev-token"},
            )
            self.assertEqual(create_resp.status_code, 201)
            upload_data = create_resp.json()
            self.assertEqual(upload_data["file_id"], str(file_id))
            self.assertIn("upload_url", upload_data)
            self.assertIn("fields", upload_data)
            self.assertEqual(upload_data["expires_in"], 300)

            # Проверяем, что до загрузки файл находится в статусе pending и не может быть скачан
            dl_pending = self.client.get(
                "/get_file_download",
                params={"file_id": str(file_id)},
                headers={"Authorization": "Bearer dev-token"},
            )
            self.assertEqual(dl_pending.status_code, 409)

            # Шаг 2: Реальный HTTP multipart/form-data upload в S3
            form_fields = upload_data["fields"]
            files = {"file": (file_name, file_payload, mime_type)}
            s3_post_resp = requests.post(upload_data["upload_url"], data=form_fields, files=files)
            self.assertIn(s3_post_resp.status_code, (200, 204), f"S3 upload failed: {s3_post_resp.text}")

            # Шаг 3: Подтверждение загрузки на сервере LMS
            complete_resp = self.client.post(
                "/complete_file_upload",
                params={"file_id": str(file_id)},
                headers={"Authorization": "Bearer dev-token"},
            )
            self.assertEqual(complete_resp.status_code, 200)
            completed_file = complete_resp.json()
            self.assertEqual(completed_file["meta"]["upload_status"], "ready")

            # Шаг 4: Получение presigned GET ссылки
            dl_resp = self.client.get(
                "/get_file_download",
                params={"file_id": str(file_id)},
                headers={"Authorization": "Bearer dev-token"},
            )
            self.assertEqual(dl_resp.status_code, 200)
            dl_data = dl_resp.json()
            self.assertIn("download_url", dl_data)
            self.assertEqual(dl_data["expires_in"], 300)

            # Шаг 5: Реальное скачивание файла из S3 по подписанной ссылке
            get_resp = requests.get(dl_data["download_url"])
            self.assertEqual(get_resp.status_code, 200)
            self.assertEqual(get_resp.content, file_payload, "Содержимое скачанного файла не совпадает с отправленным!")

            # Шаг 6: Удаление файла через /delete_file
            del_resp = self.client.delete(
                "/delete_file",
                params={"file_id": str(file_id)},
                headers={"Authorization": "Bearer dev-token"},
            )
            self.assertEqual(del_resp.status_code, 200)
            self.assertEqual(del_resp.json(), {"ok": True})

            # Проверяем в S3, что объект действительно физически удалён
            s3_key = form_fields["key"]
            with self.assertRaises(ClientError) as ctx:
                self.s3_client.head_object(Bucket=self.bucket, Key=s3_key)
            self.assertEqual(str(ctx.exception.response.get("Error", {}).get("Code")), "404")

    def test_e2e_tampered_file_size_rejected_by_verification(self):
        """Если размер реально загруженного файла отличается от заявленного, verify_upload возвращает 409."""
        declared_size = 500
        actual_payload = b"Much smaller payload"
        actual_size = len(actual_payload)
        file_id = uuid4()
        user_id = DEFAULT_MOCK_USER["id"]

        db_storage = {}

        async def mock_create_file(conn, req):
            rec = {
                "id": file_id,
                "uploader_id": user_id,
                "lesson_id": None,
                "submission_id": None,
                "file_type": req.file_type,
                "url": req.url,
                "file_name": req.file_name,
                "size_bytes": req.size_bytes,
                "mime_type": req.mime_type,
                "meta": req.meta,
                "created_at": "2026-10-29T10:00:00Z",
            }
            db_storage[file_id] = rec
            return rec

        async def mock_get_file_by_id(conn, fid):
            return db_storage.get(fid)

        with patch("backend.db.methods.create_file", side_effect=mock_create_file), \
             patch("backend.db.methods.get_file_by_id", side_effect=mock_get_file_by_id):

            create_resp = self.client.post(
                "/create_file_upload",
                json={
                    "file_name": "tampered.pdf",
                    "file_type": "document",
                    "mime_type": "application/pdf",
                    "size_bytes": declared_size,
                },
                headers={"Authorization": "Bearer dev-token"},
            )
            upload_data = create_resp.json()

            # Загружаем файл неверного размера в S3
            form_fields = upload_data["fields"]
            files = {"file": ("tampered.pdf", actual_payload, "application/pdf")}
            requests.post(upload_data["upload_url"], data=form_fields, files=files)

            # Попытка подтвердить загрузку должна вернуть 409
            complete_resp = self.client.post(
                "/complete_file_upload",
                params={"file_id": str(file_id)},
                headers={"Authorization": "Bearer dev-token"},
            )
            self.assertEqual(complete_resp.status_code, 409)
            self.assertIn("не совпадает", complete_resp.json()["detail"])
            # Статус в БД остаётся pending
            self.assertEqual(db_storage[file_id]["meta"]["upload_status"], "pending")

    def test_e2e_tampered_mime_type_rejected(self):
        """Проверка защиты от подмены MIME-типа:
        1. В presigned POST политике строго прописано условие {'Content-Type': 'application/pdf'}.
        2. Если в хранилище каким-либо образом окажется файл с другим MIME-типом,
           серверная верификация /complete_file_upload отклоняет его со статусом 409.
        """
        import base64
        import json

        file_id = uuid4()
        user_id = DEFAULT_MOCK_USER["id"]
        db_storage = {}

        async def mock_create_file(conn, req):
            rec = {
                "id": file_id,
                "uploader_id": user_id,
                "lesson_id": None,
                "submission_id": None,
                "file_type": req.file_type,
                "url": req.url,
                "file_name": req.file_name,
                "size_bytes": req.size_bytes,
                "mime_type": req.mime_type,
                "meta": req.meta,
                "created_at": "2026-10-29T10:00:00Z",
            }
            db_storage[file_id] = rec
            return rec

        async def mock_get_file_by_id(conn, fid):
            return db_storage.get(fid)

        with patch("backend.db.methods.create_file", side_effect=mock_create_file), \
             patch("backend.db.methods.get_file_by_id", side_effect=mock_get_file_by_id):
            create_resp = self.client.post(
                "/create_file_upload",
                json={
                    "file_name": "document.pdf",
                    "file_type": "document",
                    "mime_type": "application/pdf",
                    "size_bytes": 100,
                },
                headers={"Authorization": "Bearer dev-token"},
            )
            upload_data = create_resp.json()

            # 1. Проверяем условие в сгенерированной S3 POST policy
            policy_bytes = base64.b64decode(upload_data["fields"]["policy"])
            policy_doc = json.loads(policy_bytes.decode("utf-8"))
            self.assertIn({"Content-Type": "application/pdf"}, policy_doc["conditions"])

            # 2. Загружаем в S3 файл с поддельным типом
            form_fields = upload_data["fields"].copy()
            form_fields["Content-Type"] = "text/html"
            files = {"file": ("document.pdf", b"x" * 100, "text/html")}
            requests.post(upload_data["upload_url"], data=form_fields, files=files)

            # 3. Серверная верификация complete_file_upload обязана отклонить (409)
            comp_resp = self.client.post(
                "/complete_file_upload",
                params={"file_id": str(file_id)},
                headers={"Authorization": "Bearer dev-token"},
            )
            self.assertEqual(comp_resp.status_code, 409)
            self.assertIn("не совпадает", comp_resp.json()["detail"])
            self.assertEqual(db_storage[file_id]["meta"]["upload_status"], "pending")

    def test_e2e_cyrillic_filename_download(self):
        """Проверка работы с кириллическими именами файлов при формировании ссылки скачивания."""
        payload = b"Russian content: \xd0\xbf\xd1\x80\xd0\xb8\xd0\xb2\xd0\xb5\xd1\x82"
        file_name = "Лабораторная_работа_1.docx"
        file_id = uuid4()
        user_id = DEFAULT_MOCK_USER["id"]

        db_storage = {}

        async def mock_create_file(conn, req):
            rec = {
                "id": file_id,
                "uploader_id": user_id,
                "lesson_id": None,
                "submission_id": None,
                "file_type": req.file_type,
                "url": req.url,
                "file_name": req.file_name,
                "size_bytes": req.size_bytes,
                "mime_type": req.mime_type,
                "meta": req.meta,
                "created_at": "2026-10-29T10:00:00Z",
            }
            db_storage[file_id] = rec
            return rec

        async def mock_get_file_by_id(conn, fid):
            return db_storage.get(fid)

        async def mock_complete_file_upload(conn, fid):
            db_storage[fid]["meta"]["upload_status"] = "ready"
            return db_storage[fid]

        with patch("backend.db.methods.create_file", side_effect=mock_create_file), \
             patch("backend.db.methods.get_file_by_id", side_effect=mock_get_file_by_id), \
             patch("backend.db.methods.complete_file_upload", side_effect=mock_complete_file_upload):

            create_resp = self.client.post(
                "/create_file_upload",
                json={
                    "file_name": file_name,
                    "file_type": "document",
                    "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "size_bytes": len(payload),
                },
                headers={"Authorization": "Bearer dev-token"},
            )
            self.assertEqual(create_resp.status_code, 201)
            upload_data = create_resp.json()

            # Upload to S3
            form_fields = upload_data["fields"]
            files = {"file": (file_name, payload, form_fields["Content-Type"])}
            requests.post(upload_data["upload_url"], data=form_fields, files=files)

            # Complete upload
            self.client.post(
                "/complete_file_upload",
                params={"file_id": str(file_id)},
                headers={"Authorization": "Bearer dev-token"},
            )

            # Get download url
            dl_resp = self.client.get(
                "/get_file_download",
                params={"file_id": str(file_id)},
                headers={"Authorization": "Bearer dev-token"},
            )
            self.assertEqual(dl_resp.status_code, 200)
            dl_url = dl_resp.json()["download_url"]

            # Download via HTTP GET
            get_resp = requests.get(dl_url, timeout=5)
            self.assertEqual(get_resp.status_code, 200)
            self.assertEqual(get_resp.content, payload)

    def test_e2e_storage_down_returns_503(self):
        """Если хранилище S3 недоступно (сеть упала / упал MinIO), возвращается 503."""
        file_id = uuid4()
        fake_record = {
            "id": file_id,
            "uploader_id": DEFAULT_MOCK_USER["id"],
            "lesson_id": None,
            "submission_id": None,
            "size_bytes": 100,
            "mime_type": "application/pdf",
            "meta": {"storage": "s3", "bucket": self.bucket, "key": "uploads/user/file.pdf"},
        }
        with patch("backend.services.storage.configuration") as mock_cfg:
            mock_client = MagicMock()
            mock_client.head_object.side_effect = EndpointConnectionError(endpoint_url="http://s3.local")
            mock_client.delete_object.side_effect = EndpointConnectionError(endpoint_url="http://s3.local")
            mock_cfg.return_value = (mock_client, self.bucket)

            with patch("backend.api.routers.files.file_access", return_value=fake_record):
                # complete_file_upload при падении S3
                comp_resp = self.client.post(
                    "/complete_file_upload",
                    params={"file_id": str(file_id)},
                    headers={"Authorization": "Bearer dev-token"},
                )
                self.assertEqual(comp_resp.status_code, 503)
                self.assertIn("Хранилище недоступно", comp_resp.json()["detail"])

                # delete_file при падении S3
                with patch("backend.db.methods.delete_file", return_value=True):
                    del_resp = self.client.delete(
                        "/delete_file",
                        params={"file_id": str(file_id)},
                        headers={"Authorization": "Bearer dev-token"},
                    )
                    self.assertEqual(del_resp.status_code, 503)
                    self.assertIn("Хранилище недоступно", del_resp.json()["detail"])


if __name__ == "__main__":
    unittest.main()
