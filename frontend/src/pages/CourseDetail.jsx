import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { fetchCourses, getAssignment } from '../api/client';
import { Icon } from '../components/Icons';
import { useApp } from '../context/AppContext';

export function CourseDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { showToast } = useApp();
  const [tab, setTab] = useState('description');
  const [course, setCourse] = useState(null);
  const [modalType, setModalType] = useState(null); // 'syllabus' | 'video' | 'materials'

  const assignment = getAssignment(1);

  useEffect(() => {
    fetchCourses().then((list) => {
      const found = list.find((c) => String(c.id) === String(id)) || list[0];
      setCourse(found);
    });
  }, [id]);

  if (!course) {
    return <div>Загрузка курса...</div>;
  }

  return (
    <div className="course-shell">
      <aside className="subnav">
        <button
          className={tab === 'description' ? 'active' : ''}
          onClick={() => setTab('description')}
        >
          Описание
        </button>
        <button
          className={tab === 'structure' ? 'active' : ''}
          onClick={() => setTab('structure')}
        >
          Структура
        </button>
        <button
          className={tab === 'grades' ? 'active' : ''}
          onClick={() => setTab('grades')}
        >
          Оценки
        </button>
      </aside>

      <section className="course-content">
        {tab === 'description' && (
          <div>
            <div className="hero" style={{ background: course.color }}>
              <Icon name="cover" size={110} />
            </div>
            <div className="description-text">
              <h2>{course.title}</h2>
              <p>
                {course.description} Курс сочетает теоретические материалы,
                практические занятия и сквозные проектные задачи в командах.
              </p>
            </div>
          </div>
        )}

        {tab === 'structure' && (
          <div>
            <div className="module">
              <h3>ТЕМАТИЧЕСКИЙ ПЛАН</h3>
              <div
                className="module-item"
                onClick={() => setModalType('syllabus')}
              >
                <Icon name="doc" size={23} />
                <div>
                  <b>Описание курса</b>
                  <small>Силлабус курса (PDF)</small>
                </div>
              </div>
            </div>

            <div className="module">
              <h3>ПАРА 1</h3>
              <div
                className="module-item"
                onClick={() => setModalType('video')}
              >
                <Icon name="doc" size={23} />
                <div>
                  <b>Материалы 1 пары</b>
                  <small>Видеозапись и конспект лекции</small>
                </div>
              </div>

              <div
                className="module-item"
                onClick={() => navigate(`/assignment/1`)}
              >
                <Icon name="doc" size={23} />
                <div>
                  <b>Домашняя работа 1 пара</b>
                  <small>Задание • 20 баллов • {assignment.submitted ? 'Сдано' : 'Не сдано'}</small>
                </div>
              </div>

              <div
                className="module-item"
                onClick={() => setModalType('materials')}
              >
                <Icon name="doc" size={23} />
                <div>
                  <b>Дополнительные материалы 1 пары</b>
                  <small>Презентация и список рекомендованной литературы</small>
                </div>
              </div>
            </div>
          </div>
        )}

        {tab === 'grades' && (
          <div className="card" style={{ padding: 24, maxWidth: 650 }}>
            <h2>Журнал оценок курса</h2>
            <div style={{ marginTop: 16 }}>
              <p>
                <b>Домашняя работа 1 пара:</b>{' '}
                {assignment.grade ? `${assignment.grade} / 20` : assignment.submitted ? 'На проверке' : 'Не сдано'}
              </p>
              <p>
                <b>Текущий процент выполнения:</b>{' '}
                {assignment.grade ? `${(assignment.grade / 20) * 100}%` : '—'}
              </p>
            </div>
          </div>
        )}
      </section>

      {/* Модальные окна материалов */}
      {modalType === 'syllabus' && (
        <div className="modal-bg" onClick={() => setModalType(null)}>
          <div
            className="document-wrap"
            style={{ maxWidth: 850, width: '90vw', maxHeight: '85vh', overflow: 'auto' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="filebar">
              <span>📄 Силлабус_{course.title}.pdf</span>
              <button
                className="btn primary"
                onClick={() => showToast('Силлабус скачан')}
              >
                Скачать
              </button>
            </div>
            <article className="document">
              <h2>Силлабус курса</h2>
              <p style={{ textAlign: 'center' }}>{course.title}</p>
              <h3>Краткое описание</h3>
              <p>
                Курс направлен на освоение современных подходов разработки и
                проектирования.
              </p>
              <h3>Тематический план</h3>
              <table className="plan">
                <thead>
                  <tr>
                    <th>Занятие</th>
                    <th>Тема</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Занятие 1</td>
                    <td>Введение в дисциплину и архитектуру</td>
                  </tr>
                  <tr>
                    <td>Занятие 2</td>
                    <td>Основные подходы и проектирование</td>
                  </tr>
                  <tr>
                    <td>Занятие 3</td>
                    <td>Командная практическая работа</td>
                  </tr>
                  <tr>
                    <td>Занятие 4</td>
                    <td>Итоговая защита проектов</td>
                  </tr>
                </tbody>
              </table>
            </article>
            <div style={{ textAlign: 'right', marginTop: 14 }}>
              <button className="btn" onClick={() => setModalType(null)}>
                Закрыть
              </button>
            </div>
          </div>
        </div>
      )}

      {modalType === 'video' && (
        <div className="modal-bg" onClick={() => setModalType(null)}>
          <div className="modal" style={{ width: 700 }} onClick={(e) => e.stopPropagation()}>
            <h2>Материалы 1 пары</h2>
            <p>Видеозапись лекции к первой паре:</p>
            <div className="video">
              <span className="play" onClick={() => showToast('Воспроизведение лекции')}>
                ▶
              </span>
            </div>
            <div className="modal-actions">
              <button className="btn" onClick={() => setModalType(null)}>
                Закрыть
              </button>
            </div>
          </div>
        </div>
      )}

      {modalType === 'materials' && (
        <div className="modal-bg" onClick={() => setModalType(null)}>
          <div className="modal" style={{ width: 600 }} onClick={(e) => e.stopPropagation()}>
            <h2>Дополнительные материалы</h2>
            <div className="resource-list">
              <div className="resource">📄 Конспект 1 пары (лекция)</div>
              <div className="resource">📊 Презентация 1 пары (слайды)</div>
              <div className="resource">📚 Список литературы и стандартов</div>
            </div>
            <div className="modal-actions">
              <button className="btn" onClick={() => setModalType(null)}>
                Закрыть
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
