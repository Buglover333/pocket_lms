import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchCourses, getAllStudents } from '../api/client';
import { useApp } from '../context/AppContext';

export function TeacherHome() {
  const navigate = useNavigate();
  const [courses, setCourses] = useState([]);

  useEffect(() => {
    fetchCourses().then(setCourses);
  }, []);

  return (
    <div>
      <h2>Кабинет преподавателя</h2>
      <p style={{ color: 'var(--muted)', marginBottom: 24 }}>
        Управление учебными курсами, проектными группами и проверка домашних заданий.
      </p>

      <div className="course-grid">
        {courses.slice(0, 4).map((c) => (
          <article
            key={c.id}
            className="course-card"
            onClick={() => navigate('/teacher/groups')}
          >
            <div className="cover" style={{ background: c.color }} />
            <div className="course-info">
              <strong>{c.title}</strong>
              <span>Управление командами курса →</span>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

export function TeacherCourses() {
  const navigate = useNavigate();
  const [courses, setCourses] = useState([]);

  useEffect(() => {
    fetchCourses().then(setCourses);
  }, []);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 20 }}>
        <h2>Дисциплины преподавателя</h2>
        <button
          className="btn primary"
          onClick={() => navigate('/teacher/groups')}
        >
          Управление группами
        </button>
      </div>
      <table className="table">
        <thead>
          <tr>
            <th>Дисциплина</th>
            <th>Статус</th>
            <th>Студентов</th>
            <th>Действия</th>
          </tr>
        </thead>
        <tbody>
          {courses.map((c) => (
            <tr key={c.id}>
              <td>
                <span className="dot" style={{ background: c.color }} />
                <b>{c.title}</b>
              </td>
              <td>Активный семестр</td>
              <td>6 чел.</td>
              <td>
                <button
                  className="link"
                  onClick={() => navigate('/teacher/groups')}
                >
                  Группы курса →
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function TeacherGrades() {
  const { showToast } = useApp();
  const students = getAllStudents();

  return (
    <div>
      <h2>Журнал оценивания работ</h2>
      <table className="table" style={{ marginTop: 20 }}>
        <thead>
          <tr>
            <th>Студент</th>
            <th>Задание</th>
            <th>Статус</th>
            <th>Оценка</th>
            <th>Действие</th>
          </tr>
        </thead>
        <tbody>
          {students.map((s, idx) => (
            <tr key={s.id}>
              <td>{s.name}</td>
              <td>Домашняя работа 1 пара</td>
              <td>
                {idx === 0 ? (
                  <span style={{ color: '#2e7d32' }}>Сдано (файл прикреплен)</span>
                ) : idx === 1 ? (
                  <span style={{ color: '#0b5fae' }}>Оценено</span>
                ) : (
                  <span style={{ color: 'var(--muted)' }}>Ожидает сдачи</span>
                )}
              </td>
              <td>
                {idx === 1 ? '18 / 20' : idx === 0 ? '—' : '—'}
              </td>
              <td>
                {idx === 0 ? (
                  <button
                    className="btn primary"
                    style={{ minHeight: 32, padding: '0 10px', fontSize: 13 }}
                    onClick={() => showToast(`Оценка выставлена студенту ${s.name}`)}
                  >
                    Оценить
                  </button>
                ) : (
                  <button
                    className="link"
                    onClick={() => showToast(`Просмотр работы: ${s.name}`)}
                  >
                    Просмотр
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
