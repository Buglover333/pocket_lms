import React, { createContext, useContext, useState, useEffect } from 'react';
import { checkBackendHealth, fetchUserProfile, saveUserProfile } from '../api/client';

const AppContext = createContext(null);

export function AppProvider({ children }) {
  const [role, setRole] = useState(() => localStorage.getItem('pocket_lms_role') || 'student');
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [toastMessage, setToastMessage] = useState('');
  const [toastVisible, setToastVisible] = useState(false);
  const [backendOnline, setBackendOnline] = useState(false);
  const [profile, setProfile] = useState({
    first_name: 'Роман',
    last_name: 'Шепелев',
    email: 'roman@example.ru',
    nick: '@shepelev_dev',
    photo: null,
  });

  const showToast = (text) => {
    setToastMessage(text);
    setToastVisible(true);
    setTimeout(() => {
      setToastVisible(false);
    }, 2200);
  };

  const toggleRole = () => {
    const next = role === 'student' ? 'teacher' : 'student';
    setRole(next);
    localStorage.setItem('pocket_lms_role', next);
    showToast(`Переключено на роль: ${next === 'student' ? 'Студент' : 'Преподаватель'}`);
  };

  const toggleSidebar = () => {
    setIsSidebarCollapsed((prev) => !prev);
  };

  const handleUpdateProfile = async (newData) => {
    const updated = await saveUserProfile(newData);
    setProfile((prev) => ({ ...prev, ...updated }));
    showToast('Профиль сохранён');
  };

  useEffect(() => {
    checkBackendHealth().then((online) => setBackendOnline(online));
    fetchUserProfile().then((p) => {
      if (p) setProfile((prev) => ({ ...prev, ...p }));
    });
  }, []);

  return (
    <AppContext.Provider
      value={{
        role,
        setRole,
        toggleRole,
        isSidebarCollapsed,
        toggleSidebar,
        toastMessage,
        toastVisible,
        showToast,
        backendOnline,
        profile,
        updateProfile: handleUpdateProfile,
      }}
    >
      {children}
      <div className={`toast ${toastVisible ? 'show' : ''}`}>{toastMessage}</div>
    </AppContext.Provider>
  );
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used inside AppProvider');
  return ctx;
}
