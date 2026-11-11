import React from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { Icon } from './Icons';

export function Layout() {
  const { role, toggleRole, isSidebarCollapsed, toggleSidebar, backendOnline } = useApp();
  const location = useLocation();

  // Определение заголовка в зависимости от маршрута
  const getPageTitle = () => {
    const p = location.pathname;
    if (p === '/' || p === '/teacher/home') return 'Главная';
    if (p === '/profile') return 'Профиль';
    if (p === '/courses' || p === '/teacher/courses') return 'Курсы';
    if (p.startsWith('/course/')) return 'Курс';
    if (p === '/groups') return 'Группы (Студент)';
    if (p === '/teacher/groups') return 'Группы (Преподаватель)';
    if (p === '/teacher/grades') return 'Журнал оценок';
    if (p === '/calendar' || p === '/teacher/calendar') return 'Календарь';
    if (p === '/settings') return 'Настройки';
    return 'Учебный портал';
  };

  return (
    <div className="app">
      <aside className={`sidebar ${isSidebarCollapsed ? 'small' : ''}`} id="sidebar">
        <NavLink
          to="/profile"
          className={({ isActive }) => `side-btn profile ${isActive ? 'active' : ''}`}
        >
          <Icon name="person" size={38} />
          <span className="side-label">Профиль</span>
        </NavLink>

        <nav className="side-nav">
          {role === 'student' ? (
            <>
              <NavLink
                to="/"
                end
                className={({ isActive }) => `side-btn ${isActive ? 'active' : ''}`}
              >
                <Icon name="dash" />
                <span className="side-label">Главная</span>
              </NavLink>
              <NavLink
                to="/courses"
                className={({ isActive }) => `side-btn ${isActive ? 'active' : ''}`}
              >
                <Icon name="book" />
                <span className="side-label">Курсы</span>
              </NavLink>
              <NavLink
                to="/groups"
                className={({ isActive }) => `side-btn ${isActive ? 'active' : ''}`}
              >
                <Icon name="users" />
                <span className="side-label">Группы</span>
              </NavLink>
              <NavLink
                to="/calendar"
                className={({ isActive }) => `side-btn ${isActive ? 'active' : ''}`}
              >
                <Icon name="calendar" />
                <span className="side-label">Календарь</span>
              </NavLink>
              <NavLink
                to="/settings"
                className={({ isActive }) => `side-btn ${isActive ? 'active' : ''}`}
              >
                <Icon name="gear" />
                <span className="side-label">Настройки</span>
              </NavLink>
            </>
          ) : (
            <>
              <NavLink
                to="/teacher/home"
                className={({ isActive }) => `side-btn ${isActive ? 'active' : ''}`}
              >
                <Icon name="dash" />
                <span className="side-label">Главная</span>
              </NavLink>
              <NavLink
                to="/teacher/courses"
                className={({ isActive }) => `side-btn ${isActive ? 'active' : ''}`}
              >
                <Icon name="book" />
                <span className="side-label">Курсы</span>
              </NavLink>
              <NavLink
                to="/teacher/groups"
                className={({ isActive }) => `side-btn ${isActive ? 'active' : ''}`}
              >
                <Icon name="users" />
                <span className="side-label">Группы</span>
              </NavLink>
              <NavLink
                to="/teacher/grades"
                className={({ isActive }) => `side-btn ${isActive ? 'active' : ''}`}
              >
                <Icon name="grades" />
                <span className="side-label">Оценки</span>
              </NavLink>
              <NavLink
                to="/teacher/calendar"
                className={({ isActive }) => `side-btn ${isActive ? 'active' : ''}`}
              >
                <Icon name="calendar" />
                <span className="side-label">Календарь</span>
              </NavLink>
              <NavLink
                to="/settings"
                className={({ isActive }) => `side-btn ${isActive ? 'active' : ''}`}
              >
                <Icon name="gear" />
                <span className="side-label">Настройки</span>
              </NavLink>
            </>
          )}
        </nav>

        {/* Переключатель роли для удобной демонстрации */}
        <div className="role-toggle">
          <button
            className="role-badge"
            onClick={toggleRole}
            title="Нажмите, чтобы переключить роль"
          >
            <span>Роль: </span>
            {role === 'student' ? 'Студент' : 'Препод'}
          </button>
        </div>

        <button className="side-btn collapse" onClick={toggleSidebar}>
          {isSidebarCollapsed ? '→' : '←'}
        </button>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <h1 id="pageTitle">{getPageTitle()}</h1>
          <div className="topbar-actions">
            <div className="backend-pill" title={backendOnline ? 'Бэкенд FastAPI доступен' : 'Работает в демо-режиме (FastAPI оффлайн)'}>
              <span className={`backend-dot ${backendOnline ? '' : 'offline'}`} />
              <span>{backendOnline ? 'FastAPI 0.5.0' : 'Demo Mock'}</span>
            </div>
          </div>
        </header>

        <div className="view">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
