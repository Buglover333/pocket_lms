import React, { useState } from 'react';
import { useApp } from '../context/AppContext';
import { Icon } from '../components/Icons';

export function ProfilePage() {
  const { profile, updateProfile } = useApp();
  const [isModalOpen, setIsModalOpen] = useState(false);

  const [formData, setFormData] = useState({
    first_name: profile.first_name,
    last_name: profile.last_name,
    email: profile.email,
    nick: profile.nick,
    photo: profile.photo,
  });

  const handleOpenModal = () => {
    setFormData({
      first_name: profile.first_name,
      last_name: profile.last_name,
      email: profile.email,
      nick: profile.nick,
      photo: profile.photo,
    });
    setIsModalOpen(true);
  };

  const handleAvatarChange = (e) => {
    const file = e.target.files && e.target.files[0];
    if (file) {
      setFormData((prev) => ({
        ...prev,
        photo: URL.createObjectURL(file),
      }));
    }
  };

  const handleSave = (e) => {
    e.preventDefault();
    updateProfile(formData);
    setIsModalOpen(false);
  };

  return (
    <div>
      <section className="profile-layout card" style={{ background: '#fff' }}>
        <div className="photo" id="profilePhoto">
          {profile.photo ? (
            <img src={profile.photo} alt="Аватар" />
          ) : (
            <Icon name="person" size={65} />
          )}
        </div>

        <div>
          <h2 className="profile-name">
            {profile.first_name} {profile.last_name}
          </h2>

          <div className="contacts">
            <h2>Контакты</h2>
            <div className="contact">
              <b>Почта:</b> {profile.email}
            </div>
            <div className="contact">
              <b>Социальная сеть:</b> {profile.nick}
            </div>
            <div className="contact">
              <b>Роль в системе:</b> Обучающийся / Разработчик
            </div>
          </div>
        </div>

        <button className="btn edit-profile" onClick={handleOpenModal}>
          Редактировать профиль
        </button>
      </section>

      {/* Модальное окно редактирования */}
      {isModalOpen && (
        <div className="modal-bg" onClick={() => setIsModalOpen(false)}>
          <form
            className="modal"
            onSubmit={handleSave}
            onClick={(e) => e.stopPropagation()}
          >
            <h2>Редактировать профиль</h2>

            <div className="field wide">
              <label>Аватар пользователя</label>
              <input
                type="file"
                accept="image/*"
                onChange={handleAvatarChange}
              />
            </div>

            <div className="form-grid" style={{ marginTop: 15 }}>
              <div className="field">
                <label>Имя</label>
                <input
                  value={formData.first_name}
                  onChange={(e) =>
                    setFormData({ ...formData, first_name: e.target.value })
                  }
                  required
                />
              </div>

              <div className="field">
                <label>Фамилия</label>
                <input
                  value={formData.last_name}
                  onChange={(e) =>
                    setFormData({ ...formData, last_name: e.target.value })
                  }
                  required
                />
              </div>

              <div className="field wide">
                <label>Почта (Email)</label>
                <input
                  type="email"
                  value={formData.email}
                  onChange={(e) =>
                    setFormData({ ...formData, email: e.target.value })
                  }
                  required
                />
              </div>

              <div className="field wide">
                <label>Никнейм в соцсети / Telegram</label>
                <input
                  value={formData.nick}
                  onChange={(e) =>
                    setFormData({ ...formData, nick: e.target.value })
                  }
                  required
                />
              </div>
            </div>

            <div className="modal-actions">
              <button
                type="button"
                className="btn"
                onClick={() => setIsModalOpen(false)}
              >
                Отмена
              </button>
              <button type="submit" className="btn primary">
                Сохранить
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
