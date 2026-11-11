import React, { useState } from 'react';
import { useApp } from '../context/AppContext';

export function SettingsPage() {
  const { showToast } = useApp();
  const [oldPass, setOldPass] = useState('');
  const [newPass, setNewPass] = useState('');
  const [repeatPass, setRepeatPass] = useState('');

  const [notifications, setNotifications] = useState({
    assignments: true,
    grades: true,
    events: false,
  });
  const [showContacts, setShowContacts] = useState(true);

  const handlePasswordChange = (e) => {
    e.preventDefault();
    if (!newPass || !repeatPass) {
      showToast('Заполните поля нового пароля');
      return;
    }
    if (newPass !== repeatPass) {
      showToast('Новые пароли не совпадают');
      return;
    }
    if (newPass.length < 6) {
      showToast('Пароль должен содержать минимум 6 символов');
      return;
    }
    showToast('Пароль успешно изменён');
    setOldPass('');
    setNewPass('');
    setRepeatPass('');
  };

  return (
    <div className="settings">
      <section className="card settings-card">
        <h2>Уведомления</h2>
        <div className="setting">
          <span>Новые задания и приближение дедлайнов</span>
          <input
            className="switch"
            type="checkbox"
            checked={notifications.assignments}
            onChange={(e) =>
              setNotifications({ ...notifications, assignments: e.target.checked })
            }
          />
        </div>
        <div className="setting">
          <span>Оценки и комментарии преподавателя</span>
          <input
            className="switch"
            type="checkbox"
            checked={notifications.grades}
            onChange={(e) =>
              setNotifications({ ...notifications, grades: e.target.checked })
            }
          />
        </div>
        <div className="setting">
          <span>События и изменения расписания курса</span>
          <input
            className="switch"
            type="checkbox"
            checked={notifications.events}
            onChange={(e) =>
              setNotifications({ ...notifications, events: e.target.checked })
            }
          />
        </div>
      </section>

      <section className="card settings-card">
        <h2>Приватность</h2>
        <div className="setting">
          <span>Показывать мою контактную информацию сокомандникам</span>
          <input
            className="switch"
            type="checkbox"
            checked={showContacts}
            onChange={(e) => setShowContacts(e.target.checked)}
          />
        </div>
      </section>

      <section className="card settings-card">
        <h2>Безопасность и смена пароля</h2>
        <form onSubmit={handlePasswordChange}>
          <div className="form-grid">
            <div className="field wide">
              <label>Текущий пароль</label>
              <input
                type="password"
                value={oldPass}
                onChange={(e) => setOldPass(e.target.value)}
                placeholder="••••••••"
              />
            </div>
            <div className="field">
              <label>Новый пароль</label>
              <input
                type="password"
                value={newPass}
                onChange={(e) => setNewPass(e.target.value)}
                placeholder="Минимум 6 символов"
              />
            </div>
            <div className="field">
              <label>Повторите новый пароль</label>
              <input
                type="password"
                value={repeatPass}
                onChange={(e) => setRepeatPass(e.target.value)}
                placeholder="Повтор пароля"
              />
            </div>
          </div>
          <button
            type="submit"
            className="btn primary"
            style={{ marginTop: 18 }}
          >
            Изменить пароль
          </button>
        </form>
      </section>
    </div>
  );
}
