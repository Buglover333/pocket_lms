"""Интерактивный веб-интерфейс для ручного тестирования S3 в браузере.

Запуск:
    cd pocket_lms-main
    uv run --with "moto[server]" python scripts/s3_web_demo.py
Затем откройте в браузере:
    http://localhost:8080
"""

import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import boto3
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from moto.server import ThreadedMotoServer
import uvicorn

from backend.s3 import storage

S3_PORT = 9005
WEB_PORT = 8080
S3_ENDPOINT = f"http://127.0.0.1:{S3_PORT}"
BUCKET_NAME = "pocket-lms-media"

# Конфигурация окружения
os.environ["S3_BUCKET"] = BUCKET_NAME
os.environ["S3_ENDPOINT_URL"] = S3_ENDPOINT
os.environ["AWS_ACCESS_KEY_ID"] = "minioadmin"
os.environ["AWS_SECRET_ACCESS_KEY"] = "minioadmin"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

# Запуск локального S3
s3_server = ThreadedMotoServer(ip_address="127.0.0.1", port=S3_PORT)
s3_server.start()
time.sleep(1)

# Создание бакета
storage.ensure_bucket_exists(BUCKET_NAME)

app = FastAPI(title="Pocket LMS S3 Interactive Demo")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Простейшее хранилище файлов в памяти для демо-страницы
DB_FILES = {}


@app.get("/", response_class=HTMLResponse)
def index():
    return """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pocket LMS — Тестирование S3</title>
    <style>
        :root {
            --bg: #0f172a;
            --card-bg: #1e293b;
            --accent: #38bdf8;
            --accent-hover: #0284c7;
            --success: #22c55e;
            --danger: #ef4444;
            --text: #f8fafc;
            --text-muted: #94a3b8;
            --border: #334155;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
        body { background: var(--bg); color: var(--text); padding: 2rem 1rem; display: flex; justify-content: center; }
        .container { max-width: 800px; width: 100%; }
        h1 { font-size: 1.8rem; margin-bottom: 0.5rem; color: var(--accent); }
        p.subtitle { color: var(--text-muted); margin-bottom: 2rem; font-size: 0.95rem; }
        .card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; }
        .dropzone {
            border: 2px dashed var(--border); border-radius: 8px; padding: 2.5rem 1rem;
            text-align: center; cursor: pointer; transition: all 0.2s; background: rgba(255,255,255,0.02);
        }
        .dropzone:hover, .dropzone.dragover { border-color: var(--accent); background: rgba(56, 189, 248, 0.05); }
        .dropzone svg { width: 48px; height: 48px; fill: var(--text-muted); margin-bottom: 0.75rem; }
        input[type="file"] { display: none; }
        .file-info { margin-top: 1rem; padding: 0.75rem 1rem; background: rgba(0,0,0,0.2); border-radius: 6px; display: none; }
        button {
            background: var(--accent); color: #0f172a; border: none; border-radius: 6px;
            padding: 0.75rem 1.5rem; font-size: 0.95rem; font-weight: 600; cursor: pointer; transition: 0.2s;
            margin-top: 1rem; display: inline-flex; align-items: center; gap: 0.5rem;
        }
        button:hover { background: var(--accent-hover); }
        button:disabled { opacity: 0.5; cursor: not-allowed; }
        .btn-danger { background: var(--danger); color: white; }
        .btn-danger:hover { background: #dc2626; }
        .btn-success { background: var(--success); color: white; }
        .btn-success:hover { background: #16a34a; }
        .progress-bar-wrap { height: 8px; background: var(--border); border-radius: 4px; overflow: hidden; margin-top: 1rem; display: none; }
        .progress-bar { height: 100%; width: 0%; background: var(--accent); transition: width 0.1s; }
        .log-box {
            background: #090d16; border: 1px solid var(--border); border-radius: 8px;
            padding: 1rem; font-family: 'Consolas', 'Monaco', monospace; font-size: 0.85rem;
            max-height: 250px; overflow-y: auto; color: #a5f3fc; line-height: 1.4;
        }
        .log-entry { margin-bottom: 0.35rem; }
        .log-time { color: var(--text-muted); margin-right: 0.5rem; }
        .table-wrap { overflow-x: auto; margin-top: 1rem; }
        table { width: 100%; border-collapse: collapse; text-align: left; font-size: 0.9rem; }
        th, td { padding: 0.75rem 1rem; border-bottom: 1px solid var(--border); }
        th { color: var(--text-muted); font-weight: 600; }
        .badge { display: inline-block; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }
        .badge-ready { background: rgba(34, 197, 94, 0.2); color: #4ade80; }
        .badge-pending { background: rgba(234, 179, 8, 0.2); color: #facc15; }
    </style>
</head>
<body>
<div class="container">
    <h1>📦 Тестирование S3 хранилища</h1>
    <p class="subtitle">Интерактивная загрузка через presigned POST, верификация HEAD и скачивание через presigned GET</p>

    <div class="card">
        <h3>1. Выбор и загрузка файла</h3>
        <div class="dropzone" id="dropzone" onclick="document.getElementById('fileInput').click()">
            <svg viewBox="0 0 24 24"><path d="M19.35 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.35 8.04 2.34 8.36 0 10.91 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96zM14 13v4h-4v-4H7l5-5 5 5h-3z"/></svg>
            <div id="dropzoneText">Нажмите для выбора файла или перетащите файл сюда (поддерживаются русские имена!)</div>
            <input type="file" id="fileInput" onchange="handleFileSelect(this.files[0])">
        </div>
        
        <div class="file-info" id="fileInfo">
            <div><strong>Файл:</strong> <span id="infoName"></span></div>
            <div><strong>Размер:</strong> <span id="infoSize"></span> байт</div>
            <div><strong>MIME-тип:</strong> <span id="infoType"></span></div>
        </div>

        <div class="progress-bar-wrap" id="progressWrap">
            <div class="progress-bar" id="progressBar"></div>
        </div>

        <button id="uploadBtn" onclick="startUpload()" disabled>Загрузить в S3 (Presigned POST)</button>
    </div>

    <div class="card">
        <h3>2. Загруженные файлы в S3</h3>
        <div class="table-wrap">
            <table>
                <thead>
                    <tr>
                        <th>Имя файла</th>
                        <th>Размер</th>
                        <th>Статус</th>
                        <th>Действия</th>
                    </tr>
                </thead>
                <tbody id="filesList">
                    <tr><td colspan="4" style="text-align:center; color:var(--text-muted);">Файлы ещё не загружены</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <div class="card">
        <h3>3. Журнал сетевых запросов (LMS & S3)</h3>
        <div class="log-box" id="logBox">
            <div class="log-entry"><span class="log-time">[Система]</span> Локальный S3-сервер запущен на port 9005. Бакет pocket-lms-media готов.</div>
        </div>
    </div>
</div>

<script>
let selectedFile = null;

function log(msg) {
    const box = document.getElementById('logBox');
    const time = new Date().toLocaleTimeString();
    box.innerHTML += `<div class="log-entry"><span class="log-time">[${time}]</span> ${msg}</div>`;
    box.scrollTop = box.scrollHeight;
}

const dropzone = document.getElementById('dropzone');
['dragenter', 'dragover'].forEach(e => dropzone.addEventListener(e, (ev) => { ev.preventDefault(); dropzone.classList.add('dragover'); }));
['dragleave', 'drop'].forEach(e => dropzone.addEventListener(e, (ev) => { ev.preventDefault(); dropzone.classList.remove('dragover'); }));
dropzone.addEventListener('drop', (ev) => {
    ev.preventDefault();
    if (ev.dataTransfer.files.length) handleFileSelect(ev.dataTransfer.files[0]);
});

function handleFileSelect(file) {
    if (!file) return;
    selectedFile = file;
    document.getElementById('infoName').textContent = file.name;
    document.getElementById('infoSize').textContent = file.size.toLocaleString();
    document.getElementById('infoType').textContent = file.type || 'application/octet-stream';
    document.getElementById('fileInfo').style.display = 'block';
    document.getElementById('uploadBtn').disabled = false;
    log(`Выбран файл: <b>${file.name}</b> (${file.size} байт, ${file.type || 'octet-stream'})`);
}

async function startUpload() {
    if (!selectedFile) return;
    const btn = document.getElementById('uploadBtn');
    btn.disabled = true;
    const pWrap = document.getElementById('progressWrap');
    const pBar = document.getElementById('progressBar');
    pWrap.style.display = 'block';
    pBar.style.width = '0%';

    try {
        // Шаг 1: Инициализация в LMS
        log(`1. Запрос к API: <code>POST /api/create_upload</code>...`);
        const initResp = await fetch('/api/create_upload', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                file_name: selectedFile.name,
                mime_type: selectedFile.type || 'application/octet-stream',
                size_bytes: selectedFile.size
            })
        });
        if (!initResp.ok) throw new Error(await initResp.text());
        const initData = await initResp.json();
        log(`[+] LMS вернул Presigned POST форму (file_id: ${initData.file_id})`);

        // Шаг 2: Отправка формы напрямую в S3
        log(`2. Отправка multipart/form-data напрямую в S3: <code>${initData.upload_url}</code>`);
        const formData = new FormData();
        for (const [k, v] of Object.entries(initData.fields)) {
            formData.append(k, v);
        }
        formData.append('file', selectedFile);

        await new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            xhr.open('POST', initData.upload_url);
            xhr.upload.onprogress = (e) => {
                if (e.lengthComputable) {
                    const pct = Math.round((e.loaded / e.total) * 100);
                    pBar.style.width = pct + '%';
                }
            };
            xhr.onload = () => {
                if (xhr.status >= 200 && xhr.status < 300) resolve();
                else reject(new Error('S3 upload rejected: ' + xhr.status + ' ' + xhr.responseText));
            };
            xhr.onerror = () => reject(new Error('Сетевая ошибка при отправке в S3'));
            xhr.send(formData);
        });
        log(`[+] Файл успешно загружен в S3!`);

        // Шаг 3: Подтверждение на сервере
        log(`3. Вызов <code>POST /api/complete_upload</code> (LMS проверяет S3 HEAD)...`);
        const compResp = await fetch(`/api/complete_upload?file_id=${initData.file_id}`, { method: 'POST' });
        if (!compResp.ok) throw new Error(await compResp.text());
        log(`[+] Верификация успешна! Размер и MIME совпали, статус 'ready'.`);

        pBar.style.width = '100%';
        await refreshFiles();
    } catch (err) {
        log(`<span style="color:var(--danger)">[-] Ошибка: ${err.message}</span>`);
        alert('Ошибка: ' + err.message);
    } finally {
        btn.disabled = false;
        setTimeout(() => { pWrap.style.display = 'none'; }, 1000);
    }
}

async function refreshFiles() {
    const res = await fetch('/api/list_files');
    const files = await res.json();
    const tbody = document.getElementById('filesList');
    if (!files.length) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; color:var(--text-muted);">Файлы ещё не загружены</td></tr>';
        return;
    }
    tbody.innerHTML = files.map(f => `
        <tr>
            <td><strong>${f.file_name}</strong></td>
            <td>${f.size_bytes.toLocaleString()} Б</td>
            <td><span class="badge badge-${f.status}">${f.status}</span></td>
            <td>
                <button class="btn-success" style="padding:0.4rem 0.8rem; font-size:0.8rem; margin:0;" onclick="downloadFile('${f.file_id}', '${f.file_name}')">Скачать</button>
                <button class="btn-danger" style="padding:0.4rem 0.8rem; font-size:0.8rem; margin:0 0 0 0.5rem;" onclick="deleteFile('${f.file_id}')">Удалить</button>
            </td>
        </tr>
    `).join('');
}

async function downloadFile(id, name) {
    try {
        log(`Запрос ссылки скачивания: <code>GET /api/download_url?file_id=${id}</code>`);
        const res = await fetch(`/api/download_url?file_id=${id}`);
        const data = await res.json();
        log(`[+] Получен Signed GET URL (действует 300с). Начинаем скачивание...`);
        const a = document.createElement('a');
        a.href = data.download_url;
        a.download = name;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    } catch (e) {
        log(`<span style="color:var(--danger)">[-] Ошибка скачивания: ${e.message}</span>`);
    }
}

async function deleteFile(id) {
    if (!confirm('Удалить файл из S3 и базы данных?')) return;
    try {
        log(`Удаление: <code>DELETE /api/delete_file?file_id=${id}</code>`);
        await fetch(`/api/delete_file?file_id=${id}`, { method: 'DELETE' });
        log(`[+] Файл физически удалён из S3 хранилища.`);
        await refreshFiles();
    } catch (e) {
        log(`<span style="color:var(--danger)">[-] Ошибка удаления: ${e.message}</span>`);
    }
}

refreshFiles();
</script>
</body>
</html>
"""


@app.post("/api/create_upload")
def create_upload(payload: dict):
    from uuid import uuid4

    file_id = str(uuid4())
    file_name = payload["file_name"]
    mime_type = payload.get("mime_type") or "application/octet-stream"
    size_bytes = payload["size_bytes"]

    key = f"uploads/user-web/{uuid4().hex}_{file_name}"
    bucket, signed = storage.upload_url(key, mime_type)

    DB_FILES[file_id] = {
        "file_id": file_id,
        "file_name": file_name,
        "mime_type": mime_type,
        "size_bytes": size_bytes,
        "bucket": bucket,
        "key": key,
        "status": "pending",
    }

    return {
        "file_id": file_id,
        "upload_url": signed["url"],
        "fields": signed["fields"],
        "expires_in": storage.TTL,
    }


@app.post("/api/complete_upload")
def complete_upload(file_id: str = Query(...)):
    if file_id not in DB_FILES:
        raise HTTPException(404, "Файл не найден")
    rec = DB_FILES[file_id]
    storage.verify_upload(rec["bucket"], rec["key"], rec["size_bytes"], rec["mime_type"])
    rec["status"] = "ready"
    return {"ok": True, "file": rec}


@app.get("/api/download_url")
def get_download_url(file_id: str = Query(...)):
    if file_id not in DB_FILES:
        raise HTTPException(404, "Файл не найден")
    rec = DB_FILES[file_id]
    if rec["status"] != "ready":
        raise HTTPException(409, "Файл ещё не готов")
    url = storage.download_url(rec["bucket"], rec["key"], filename=rec["file_name"])
    return {"download_url": url, "expires_in": storage.TTL}


@app.delete("/api/delete_file")
def delete_file(file_id: str = Query(...)):
    if file_id not in DB_FILES:
        raise HTTPException(404, "Файл не найден")
    rec = DB_FILES.pop(file_id)
    storage.delete_file_from_s3(rec["bucket"], rec["key"])
    return {"ok": True}


@app.get("/api/list_files")
def list_files():
    return list(DB_FILES.values())


if __name__ == "__main__":
    print(f"\n==================================================================")
    print(f"  ВЕБ-СТЕНД ДЛЯ ТЕСТИРОВАНИЯ S3 ЗАПУЩЕН!")
    print(f"  Откройте в браузере: http://localhost:{WEB_PORT}")
    print(f"  Локальный S3 сервер: {S3_ENDPOINT}")
    print(f"  Для остановки нажмите Ctrl+C")
    print(f"==================================================================\n")
    try:
        uvicorn.run(app, host="127.0.0.1", port=WEB_PORT)
    finally:
        s3_server.stop()
