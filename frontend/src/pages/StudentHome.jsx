import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchCourses } from '../api/client';

export function StudentHome() {
  const navigate = useNavigate();
  const [courses, setCourses] = useState([]);

  useEffect(() => {
    fetchCourses().then(setCourses);
  }, []);

  const deadlines = [
    { id: 1, course: 'Курс 1', title: 'Дедлайн 1', date: '10 ноября, 23:59' },
    { id: 2, course: 'Курс 2', title: 'Дедлайн 2', date: '11 ноября, 23:59' },
    { id: 3, course: 'Курс 3', title: 'Дедлайн 3', date: '12 ноября, 23:59' },
    { id: 4, course: 'Курс 4', title: 'Дедлайн 4', date: '13 ноября, 23:59' },
    { id: 5, course: 'Курс 5', title: 'Дедлайн 5', date: '14 ноября, 23:59' },
  ];

  const events = [
    { id: 1, course: 'Курс 1', text: 'Вам выставлена оценка за задание курса 1', score: '18 из 20' },
    { id: 2, course: 'Курс 2', text: 'Вам выставлена оценка за задание курса 2', score: '16 из 20' },
    { id: 3, course: 'Курс 3', text: 'Вам выставлена оценка за задание курса 3', score: '20 из 20' },
  ];

  return (
    <div className="home">
      <section>
        <div className="course-grid">
          {courses.map((c) => (
            <article
              key={c.id}
              className="course-card"
              onClick={() => navigate(`/course/${c.id}`)}
            >
              <div className="cover" style={{ background: c.color }} />
              <div className="course-info">
                <strong>{c.title}</strong>
                <span>{c.description}</span>
              </div>
            </article>
          ))}
        </div>
      </section>

      <aside className="rail">
        <h2>Задачи</h2>
        <div className="rail-list">
          {deadlines.map((d) => (
            <div key={d.id} className="rail-item">
              <button
                className="link deadline"
                onClick={() => navigate(`/assignment/${d.id}`)}
              >
                {d.title}
              </button>
              <small>
                {d.course} • {d.date}
              </small>
            </div>
          ))}
        </div>

        <h2 style={{ marginMounted: '26px', marginTop: '26px' }}>События</h2>
        <div className="rail-list">
          {events.map((e) => (
            <div key={e.id} className="rail-item">
              <button
                className="link event-link graded"
                onClick={() => navigate(`/assignment/${e.id}`)}
              >
                {e.text}
              </button>
              <small>{e.score}</small>
            </div>
          ))}
        </div>
      </aside>
    </div>
  );
}
