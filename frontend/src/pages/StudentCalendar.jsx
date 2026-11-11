import React, { useState } from 'react';
import { getCalendarEvents } from '../api/client';
import { useApp } from '../context/AppContext';

export function StudentCalendar() {
  const { showToast } = useApp();
  const [mode, setMode] = useState('month'); // 'month' | 'agenda'
  const [format, setFormat] = useState('ICS');
  const [selectedCourses, setSelectedCourses] = useState([1, 2, 3, 4, 5]);

  const calEvents = getCalendarEvents();

  const toggleCourseFilter = (courseId) => {
    setSelectedCourses((prev) =>
      prev.includes(courseId)
        ? prev.filter((id) => id !== courseId)
        : [...prev, courseId]
    );
  };

  const handleExport = () => {
    const f = format.toLowerCase();
    let content = '';

    if (f === 'csv') {
      content =
        'Дата,Курс,Событие\n' +
        calEvents
          .map((e) => `${e.date},Курс ${e.courseId},${e.title}`)
          .join('\n');
    } else {
      content = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        ...calEvents.flatMap((e, i) => [
          'BEGIN:VEVENT',
          `UID:${i}@pocketlms`,
          `DTSTART;VALUE=DATE:${e.date.replaceAll('-', '')}`,
          `SUMMARY:${e.title} — Курс ${e.courseId}`,
          'END:VEVENT',
        ]),
        'END:VCALENDAR',
      ].join('\r\n');
    }

    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `calendar.${f}`;
    link.click();
    URL.revokeObjectURL(url);
    showToast(`Календарь успешно экспортирован в .${f}`);
  };

  // Сетка 42 дня для октября 2026 (начиная с Пн 28 сентября)
  const start = new Date(2026, 8, 28);
  const daysArray = Array.from({ length: 42 }, (_, i) => {
    const d = new Date(start);
    d.setDate(start.getDate() + i);
    const iso = d.toISOString().slice(0, 10);
    return {
      date: d.getDate(),
      iso: iso,
      events: calEvents.filter(
        (e) => e.date === iso && selectedCourses.includes(e.courseId)
      ),
    };
  });

  return (
    <div>
      <div className="calendar-tools">
        <button
          className="btn"
          onClick={() => showToast('Переход к текущему дню')}
        >
          Сегодня
        </button>
        <div className="month-title">Октябрь 2026</div>
        <button
          className={`btn ${mode === 'month' ? 'primary' : ''}`}
          onClick={() => setMode('month')}
        >
          Месяц
        </button>
        <button
          className={`btn ${mode === 'agenda' ? 'primary' : ''}`}
          onClick={() => setMode('agenda')}
        >
          Сводка
        </button>

        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <select
            value={format}
            onChange={(e) => setFormat(e.target.value)}
            style={{
              padding: '0 12px',
              borderRadius: 6,
              border: '1px solid #bcc5ca',
            }}
          >
            <option value="ICS">Формат ICS (iCalendar)</option>
            <option value="CSV">Формат CSV</option>
          </select>
          <button className="btn primary" onClick={handleExport}>
            Скачать календарь
          </button>
        </div>
      </div>

      <div className="calendar-layout">
        <section>
          {mode === 'month' ? (
            <div id="month">
              <div className="weekdays">
                {['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'].map((x) => (
                  <div key={x} className="weekday">
                    {x}
                  </div>
                ))}
              </div>
              <div className="days">
                {daysArray.map((day, i) => (
                  <div key={i} className="day">
                    <b>{day.date}</b>
                    {day.events.map((e, eIdx) => (
                      <button
                        key={eIdx}
                        className={`cal-event ${e.done ? 'done' : ''}`}
                        onClick={() => showToast(`${e.title} (Курс ${e.courseId})`)}
                      >
                        {e.title}
                      </button>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="agenda">
              {calEvents
                .filter((e) => selectedCourses.includes(e.courseId))
                .map((e, idx) => (
                  <div
                    key={idx}
                    className="agenda-row"
                    onClick={() => showToast(e.title)}
                  >
                    <b>{e.date}</b> — {e.title} (Курс {e.courseId}){' '}
                    {e.done ? '✅ Сдано' : '⏳ В работе'}
                  </div>
                ))}
            </div>
          )}
        </section>

        <aside className="card filters">
          <h3 style={{ marginTop: 0 }}>Фильтр курсов</h3>
          {[1, 2, 3, 4, 5].map((i) => (
            <label key={i} className="filter">
              <input
                type="checkbox"
                checked={selectedCourses.includes(i)}
                onChange={() => toggleCourseFilter(i)}
              />{' '}
              Курс {i}
            </label>
          ))}
        </aside>
      </div>
    </div>
  );
}
