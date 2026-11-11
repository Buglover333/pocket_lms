import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchCourses } from '../api/client';

export function StudentCourses() {
  const navigate = useNavigate();
  const [courses, setCourses] = useState([]);
  const [favorites, setFavorites] = useState([2, 4]);

  useEffect(() => {
    fetchCourses().then(setCourses);
  }, []);

  const toggleFavorite = (e, id) => {
    e.stopPropagation();
    setFavorites((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  return (
    <div>
      <table className="table">
        <thead>
          <tr>
            <th style={{ width: 50 }}></th>
            <th>Курс</th>
            <th>Дата</th>
            <th>Роль</th>
          </tr>
        </thead>
        <tbody>
          {courses.map((c, i) => (
            <tr key={c.id}>
              <td>
                <button
                  className={`star ${favorites.includes(c.id) ? 'on' : ''}`}
                  onClick={(e) => toggleFavorite(e, c.id)}
                  title="Добавить в избранное"
                >
                  ★
                </button>
              </td>
              <td>
                <button
                  className="link course-link"
                  onClick={() => navigate(`/course/${c.id}`)}
                >
                  <span className="dot" style={{ background: c.color }} />
                  {c.title}
                </button>
              </td>
              <td>{i + 1} ноября 2026</td>
              <td>Студент</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
