import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { getAllStudents } from '../api/client';
import { Icon } from '../components/Icons';

export function StudentGroups() {
  const navigate = useNavigate();
  const { profile } = useApp();
  const allStudents = getAllStudents();

  const [selectedMember, setSelectedMember] = useState(null);

  const teamData = [
    {
      courseTitle: 'Курс 1 — Веб-разработка',
      teamName: 'Команда 1 (Frontend & UX)',
      members: [
        { name: `${profile.first_name} ${profile.last_name}`, email: profile.email, nick: profile.nick, isMe: true },
        allStudents[0],
        allStudents[1],
      ],
      hasTask: true,
      taskName: 'Домашняя работа 1 пара',
    },
    {
      courseTitle: 'Курс 2 — Базы данных',
      teamName: 'Команда 2 (SQL & Schema)',
      members: [
        { name: `${profile.first_name} ${profile.last_name}`, email: profile.email, nick: profile.nick, isMe: true },
        allStudents[2],
        allStudents[3],
      ],
      hasTask: true,
      taskName: 'Проектирование ERD и DDL схемы',
    },
    {
      courseTitle: 'Курс 3 — Архитектура ПО',
      teamName: 'Группа 3 (Backend & API)',
      members: [
        { name: `${profile.first_name} ${profile.last_name}`, email: profile.email, nick: profile.nick, isMe: true },
        allStudents[4],
      ],
      hasTask: false,
    },
  ];

  return (
    <div>
      <div className="group-list">
        {teamData.map((t, idx) => (
          <article key={idx} className="group card">
            <header className="group-head">
              <b>{t.courseTitle}</b>
              <div style={{ color: 'var(--muted)', marginTop: 4 }}>{t.teamName}</div>
            </header>

            <div className="group-body">
              <section className="members">
                <h3>Состав команды</h3>
                <div style={{ display: 'grid', gap: 6 }}>
                  {t.members.map((m, mIdx) => {
                    const initials = m.isMe
                      ? 'ВЫ'
                      : m.name
                          .split(' ')
                          .map((x) => x[0])
                          .join('')
                          .slice(0, 2);

                    return (
                      <button
                        key={mIdx}
                        className="member"
                        onClick={() => setSelectedMember(m)}
                      >
                        <span className="avatar">{initials}</span>
                        <span>
                          {m.name} {m.isMe ? '(Вы)' : ''}
                        </span>
                        <div className="hover-card">
                          <b>{m.name}</b>
                          <br />
                          {m.email}
                          <br />
                          {m.nick}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </section>

              <section className="team-tasks">
                <h3>Командные задания</h3>
                {t.hasTask ? (
                  <button
                    className="team-task"
                    onClick={() => navigate('/assignment/1')}
                  >
                    <b>{t.taskName}</b>
                    <br />
                    <small style={{ color: 'var(--blue)' }}>Нужно сдать в команде</small>
                  </button>
                ) : (
                  <div style={{ color: 'var(--muted)', padding: '10px 0' }}>
                    Новых командных заданий нет
                  </div>
                )}
              </section>
            </div>
          </article>
        ))}
      </div>

      {/* Модальное окно просмотра участника команды */}
      {selectedMember && (
        <div className="modal-bg" onClick={() => setSelectedMember(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Карточка участника</h2>
            <div className="profile-layout" style={{ padding: '10px 0' }}>
              <div className="photo">
                <Icon name="person" size={60} />
              </div>
              <div>
                <h3 style={{ margin: '0 0 14px' }}>{selectedMember.name}</h3>
                <div className="contacts">
                  <div className="contact">Почта: {selectedMember.email}</div>
                  <div className="contact">Социальная сеть: {selectedMember.nick}</div>
                </div>
              </div>
            </div>
            <div className="modal-actions">
              <button className="btn" onClick={() => setSelectedMember(null)}>
                Закрыть
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
