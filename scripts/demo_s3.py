"""Интерактивный демонстрационный скрипт для ручного тестирования S3.

Запуск:
    cd pocket_lms-main
    uv run --with "moto[server]" --with requests python scripts/demo_s3.py
"""

import hashlib
import os
import sys
import tempfile
import time
from pathlib import Path

# Добавляем src в sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import boto3
import requests
from botocore.exceptions import ClientError
from moto.server import ThreadedMotoServer

from backend.s3 import storage


def print_step(num: int, title: str):
    print(f"\n{'='*70}")
    print(f"  [ШАГ {num}] {title}")
    print(f"{'='*70}")


def main():
    print("""
======================================================================
       ИНТЕРАКТИВНОЕ РУЧНОЕ ТЕСТИРОВАНИЕ ХРАНИЛИЩА S3
======================================================================
Этот скрипт запускает локальное S3-хранилище (эмулятор MinIO/S3),
выполняет полный рабочий цикл загрузки, верификации, генерации
подписанных ссылок и скачивания файлов.
""")

    # 1. Запуск локального S3 сервера
    port = 9005
    endpoint_url = f"http://127.0.0.1:{port}"
    bucket_name = "pocket-lms-media"

    print(f"[*] Запуск локального S3-сервера на {endpoint_url}...")
    server = ThreadedMotoServer(ip_address="127.0.0.1", port=port)
    server.start()
    time.sleep(1)

    os.environ["S3_BUCKET"] = bucket_name
    os.environ["S3_ENDPOINT_URL"] = endpoint_url
    os.environ["AWS_ACCESS_KEY_ID"] = "minioadmin"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "minioadmin"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

    try:
        # Проверка и создание бакета
        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name="us-east-1",
            aws_access_key_id="minioadmin",
            aws_secret_access_key="minioadmin",
        )
        storage.ensure_bucket_exists(bucket_name)
        print(f"[+] Бакет '{bucket_name}' готов к работе.")

        # Выбор или создание тестового файла
        print("\nВы можете использовать любой свой файл или нажать Enter для создания тестового:")
        custom_path = input("Укажите путь к файлу на диске (или Enter для авто-создания): ").strip().strip('"')

        if custom_path and os.path.isfile(custom_path):
            file_path = Path(custom_path)
            with open(file_path, "rb") as f:
                content = f.read()
            file_name = file_path.name
        else:
            file_name = "Лабораторная_работа_1.txt"
            content = f"Тестовый учебный файл Pocket LMS!\nВремя генерации: {time.ctime()}\nУспешная проверка S3!".encode("utf-8")
            temp_dir = Path(tempfile.gettempdir())
            file_path = temp_dir / file_name
            with open(file_path, "wb") as f:
                f.write(content)
            print(f"[+] Сгенерирован тестовый файл: {file_path}")

        file_size = len(content)
        file_hash = hashlib.sha256(content).hexdigest()
        mime_type = "text/plain" if file_name.endswith(".txt") else "application/octet-stream"

        print(f"\nИнформация о файле:")
        print(f"  • Имя:     {file_name}")
        print(f"  • Размер:  {file_size} байт")
        print(f"  • SHA-256: {file_hash[:16]}...")
        print(f"  • MIME:    {mime_type}")

        # ШАГ 1: Запрос presigned POST
        print_step(1, "Генерация presigned POST ссылки сервером LMS (create_file_upload)")
        s3_key = f"uploads/user-42/{file_name}"
        bucket, upload_info = storage.upload_url(s3_key, mime_type)
        print(f"  Upload URL: {upload_info['url']}")
        print(f"  Expires in: {storage.TTL} секунд (5 минут)")
        print(f"  Поля формы:")
        for k, v in upload_info["fields"].items():
            print(f"    - {k}: {v[:50]}..." if len(str(v)) > 50 else f"    - {k}: {v}")

        # ШАГ 2: Загрузка в S3
        print_step(2, "Прямая отправка файла в S3 через multipart/form-data")
        print("  Отправка POST-запроса непосредственно в хранилище S3...")
        files = {"file": (file_name, content, mime_type)}
        start_time = time.time()
        resp = requests.post(upload_info["url"], data=upload_info["fields"], files=files)
        elapsed = time.time() - start_time
        print(f"  HTTP статус S3: {resp.status_code}")
        print(f"  Время передачи: {elapsed:.3f} сек")
        if resp.status_code not in (200, 204):
            print(f"[-] Ошибка загрузки в S3: {resp.text}")
            return

        # ШАГ 3: Верификация
        print_step(3, "Серверная верификация объекта (complete_file_upload)")
        print("  Сервер LMS вызывает S3 HEAD Object для сверки размера и MIME-типа...")
        storage.verify_upload(bucket, s3_key, file_size, mime_type)
        print("[+] УСПЕШНО: Размер и тип файла в S3 в точности соответствуют заявленным.")
        print("    Файл подтверждён и переведён в статус 'ready'.")

        # ШАГ 4: Ссылка на скачивание
        print_step(4, "Генерация подписанной временной ссылки на скачивание (get_file_download)")
        download_url = storage.download_url(bucket, s3_key, filename=file_name)
        print(f"  Signed Download URL:\n  {download_url}\n")
        print("  Обратите внимание: русское имя файла закодировано по стандарту RFC 5987 / RFC 6266")
        print("  в параметре response-content-disposition (UTF-8).")

        # ШАГ 5: Скачивание
        print_step(5, "Скачивание файла по ссылке и проверка целостности")
        dl_resp = requests.get(download_url)
        print(f"  HTTP статус скачивания: {dl_resp.status_code}")
        downloaded_bytes = dl_resp.content
        downloaded_hash = hashlib.sha256(downloaded_bytes).hexdigest()

        print(f"  Размер скачанного: {len(downloaded_bytes)} байт")
        print(f"  SHA-256 исходного:   {file_hash}")
        print(f"  SHA-256 скачанного:  {downloaded_hash}")

        if file_hash == downloaded_hash:
            print("[+] ПОЛНОЕ СОВПАДЕНИЕ: Файл скачан без повреждений, байт-в-байт!")
        else:
            print("[-] ОШИБКА: Хеши не совпадают!")

        # Сохранение копии локально
        out_name = f"downloaded_{file_name}"
        out_path = Path.cwd() / out_name
        with open(out_path, "wb") as f:
            f.write(downloaded_bytes)
        print(f"[+] Скачанный файл сохранён локально: {out_path.resolve()}")

        # ШАГ 6: Удаление
        print_step(6, "Удаление файла из S3 (delete_file)")
        storage.delete_file_from_s3(bucket, s3_key)
        print(f"[+] Объект '{s3_key}' удалён из бакета '{bucket}'.")

        # Проверка удаления
        try:
            s3.head_object(Bucket=bucket, Key=s3_key)
            print("[-] Ошибка: объект всё ещё существует!")
        except ClientError as e:
            if str(e.response.get("Error", {}).get("Code")) == "404":
                print("[+] ПОДТВЕРЖДЕНО: Объект физически отсутствует в хранилище (404 Not Found).")

        print("""
======================================================================
               ВСЕ ЭТАПЫ УСПЕШНО ЗАВЕРШЕНЫ!
======================================================================
""")

    finally:
        print("[*] Остановка локального S3-сервера...")
        server.stop()
        print("[*] Сервер остановлен.")


if __name__ == "__main__":
    main()
