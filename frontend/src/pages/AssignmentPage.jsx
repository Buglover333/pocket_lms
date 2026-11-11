import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getAssignment, submitAssignmentMock, resubmitAssignmentMock } from '../api/client';
import { useApp } from '../context/AppContext';

export function AssignmentPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { showToast } = useApp();

  const [assignment, setAssignment] = useState(() => getAssignment(id || 1));
  const [selectedFile, setSelectedFile] = useState(null);
  const [isUploadOpen, setIsUploadOpen] = useState(false);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setSelectedFile(e.dataTransfer.files[0]);
    }
  };

  const handleSubmit = () => {
    if (assignment.submitted) {
      // Режим пересдачи
      const updated = resubmitAssignmentMock(id || 1);
      setAssignment(updated);
      setSelectedFile(null);
      setIsUploadOpen(true);
      showToast('Задание открыто для повторной сдачи');
      return;
    }

    if (!selectedFile) {
      showToast('Сначала прикрепите файл с решением');
      return;
    }

    const updated = submitAssignmentMock(id || 1, selectedFile.name);
    setAssignment(updated);
    setIsUploadOpen(false);
    showToast('Задание успешно отправлено преподавателю!');
  };

  return (
    <div>
      <button
        className="btn"
        style={{ marginBottom: 20 }}
        onClick={() => navigate(-1)}
      >
        ← Назад к курсу
      </button>

      <section className="assignment-layout">
        <article>
          <h2>{assignment.title}</h2>
          <div className="assignment-meta">
            <span>
              <b>Срок:</b> {assignment.dueDate}
            </span>
            <span>
              <b>Баллы:</b> {assignment.maxScore}
            </span>
            <span>
              <b>Формат:</b> файл (PDF / ZIP / код)
            </span>
          </div>

          <h3>Описание задания</h3>
          <p style={{ lineHeight: 1.6, color: '#444' }}>
            {assignment.description}
          </p>
          <div style={{ marginTop: 20, padding: 16, background: '#f8f9fa', borderRadius: 8 }}>
            <h4>Критерии оценивания:</h4>
            <ul style={{ paddingLeft: 20, marginTop: 8, lineHeight: 1.6 }}>
              <li>Корректность структуры и чистота архитектуры — 10 баллов</li>
              <li>Интеграция с API и обработка краевых случаев — 5 баллов</li>
              <li>Качество пользовательского интерфейса (UX) — 5 баллов</li>
            </ul>
          </div>
        </article>

        <aside>
          <section className="side-card">
            <div className="side-head">
              <h3>Моё задание</h3>
              <b>{assignment.submitted ? 'Сдано' : 'Не сдано'}</b>
            </div>

            {assignment.grade != null && (
              <div className="grade">
                <span>Оценка</span>
                <b>{assignment.grade} / {assignment.maxScore}</b>
              </div>
            )}

            {!assignment.submitted && (
              <button
                className="btn primary"
                style={{ width: '100%', marginBottom: 12 }}
                onClick={() => setIsUploadOpen(!isUploadOpen)}
              >
                ＋ {isUploadOpen ? 'Скрыть выбор' : 'Добавить файл'}
              </button>
            )}

            {isUploadOpen && !assignment.submitted && (
              <div style={{ marginBottom: 14 }}>
                <input
                  type="file"
                  id="workFile"
                  hidden
                  onChange={handleFileChange}
                />
                <div
                  className="drop"
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={handleDrop}
                  onClick={() => document.getElementById('workFile').click()}
                >
                  {selectedFile ? (
                    <div>
                      <b>Выбран файл:</b>
                      <div style={{ color: 'var(--blue)', marginTop: 4 }}>
                        {selectedFile.name}
                      </div>
                    </div>
                  ) : (
                    <div>
                      Перетащите файл сюда
                      <br />
                      <small>или нажмите для выбора</small>
                    </div>
                  )}
                </div>
              </div>
            )}

            {assignment.submitted && assignment.fileName && (
              <div
                style={{
                  padding: '10px 14px',
                  background: '#fff',
                  borderRadius: 6,
                  border: '1px solid var(--line)',
                  marginBottom: 14,
                  fontSize: 14,
                }}
              >
                📎 Прикреплено: <b>{assignment.fileName}</b>
              </div>
            )}

            <button
              className={`btn primary submit ${assignment.submitted ? 'resubmit' : ''}`}
              onClick={handleSubmit}
            >
              {assignment.submitted ? 'Пересдать задание' : 'Сдать задание'}
            </button>
          </section>

          <section className="side-card">
            <h3>Комментарий преподавателя</h3>
            <p className="feedback">
              {assignment.submitted
                ? assignment.feedback || 'Преподаватель пока проверяет работу'
                : 'Работа ещё не сдана на проверку'}
            </p>
          </section>
        </aside>
      </section>
    </div>
  );
}
