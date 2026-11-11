import React, { useState, useEffect } from 'react';
import {
  fetchCourses,
  fetchGroupsForCourse,
  createGroup,
  renameGroup,
  deleteGroup,
  assignStudentToGroup,
  removeStudentFromGroup,
  getAllStudents,
} from '../api/client';
import { useApp } from '../context/AppContext';

export function TeacherGroups() {
  const { showToast } = useApp();
  const [courses, setCourses] = useState([]);
  const [activeCourseId, setActiveCourseId] = useState(1);
  const [groups, setGroups] = useState([]);
  const [allStudents] = useState(() => getAllStudents());

  // Состояние модального окна (создание / переименование)
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingGroup, setEditingGroup] = useState(null);
  const [groupNameInput, setGroupNameInput] = useState('');

  // Локальный выбор студента для каждой карточки группы
  const [selectedStudentForGroup, setSelectedStudentForGroup] = useState({});

  useEffect(() => {
    fetchCourses().then((data) => {
      setCourses(data);
      if (data.length && !activeCourseId) {
        setActiveCourseId(data[0].id);
      }
    });
  }, []);

  const loadGroups = async (courseId) => {
    const list = await fetchGroupsForCourse(courseId);
    setGroups([...list]);
  };

  useEffect(() => {
    if (activeCourseId) {
      loadGroups(activeCourseId);
    }
  }, [activeCourseId]);

  const currentCourse = courses.find((c) => c.id === activeCourseId) || {
    id: activeCourseId,
    title: `Курс ${activeCourseId}`,
  };

  // Расчёт нераспределённых студентов
  const getUnassignedStudents = () => {
    const assignedIds = new Set(groups.flatMap((g) => g.members));
    return allStudents.filter((s) => !assignedIds.has(s.id));
  };

  const unassigned = getUnassignedStudents();

  const handleOpenCreateModal = () => {
    setEditingGroup(null);
    setGroupNameInput('');
    setIsModalOpen(true);
  };

  const handleOpenRenameModal = (group) => {
    setEditingGroup(group);
    setGroupNameInput(group.name);
    setIsModalOpen(true);
  };

  const handleModalSubmit = async (e) => {
    e.preventDefault();
    const trimmed = groupNameInput.trim();
    if (!trimmed) return;

    if (editingGroup) {
      await renameGroup(activeCourseId, editingGroup.id, trimmed);
      showToast('Группа успешно переименована');
    } else {
      await createGroup(activeCourseId, trimmed);
      showToast('Группа успешно создана');
    }

    setIsModalOpen(false);
    setEditingGroup(null);
    setGroupNameInput('');
    loadGroups(activeCourseId);
  };

  const handleDeleteGroup = async (groupId) => {
    if (window.confirm('Вы уверены, что хотите удалить эту группу?')) {
      await deleteGroup(activeCourseId, groupId);
      showToast('Группа удалена');
      loadGroups(activeCourseId);
    }
  };

  const handleAssignStudent = async (groupId) => {
    const studentId = Number(selectedStudentForGroup[groupId]);
    if (!studentId) {
      showToast('Выберите студента из списка');
      return;
    }
    await assignStudentToGroup(activeCourseId, groupId, studentId);
    showToast('Студент добавлен в группу');
    setSelectedStudentForGroup((prev) => ({ ...prev, [groupId]: '' }));
    loadGroups(activeCourseId);
  };

  const handleRemoveStudent = async (groupId, studentId) => {
    await removeStudentFromGroup(activeCourseId, groupId, studentId);
    showToast('Студент убран из группы');
    loadGroups(activeCourseId);
  };

  const getInitials = (name) => {
    return name
      .split(' ')
      .map((x) => x[0])
      .join('')
      .slice(0, 2);
  };

  return (
    <div className="groups-content">
      {/* Панель выбора курса и добавления группы */}
      <div className="course-toolbar">
        <label htmlFor="courseSelect">Дисциплина:</label>
        <select
          id="courseSelect"
          className="course-select"
          value={activeCourseId}
          onChange={(e) => setActiveCourseId(Number(e.target.value))}
        >
          {courses.map((c) => (
            <option key={c.id} value={c.id}>
              {c.title}
            </option>
          ))}
        </select>

        <button className="btn primary" onClick={handleOpenCreateModal}>
          ＋ Создать группу
        </button>
      </div>

      {/* Сводная плашка распределения */}
      <div className="summary">
        <b>{currentCourse.title}:</b> создано {groups.length} групп(ы), распределено{' '}
        {allStudents.length - unassigned.length} из {allStudents.length} студентов курса.
        {unassigned.length > 0 ? (
          <span style={{ color: '#d96b5f', marginLeft: 8 }}>
            (Осталось распределить: {unassigned.length})
          </span>
        ) : (
          <span style={{ color: '#2e7d32', marginLeft: 8 }}>
            (Все студенты распределены по командам ✅)
          </span>
        )}
      </div>

      {/* Сетка групп курса */}
      {groups.length === 0 ? (
        <div className="empty card">
          В этом курсе ещё не сформированы группы. Нажмите «Создать группу», чтобы начать.
        </div>
      ) : (
        <div className="groups-grid">
          {groups.map((group) => (
            <section key={group.id} className="card group-card">
              <header className="group-head">
                <h2>{group.name}</h2>
                <div className="group-actions">
                  <button
                    className="icon-btn"
                    onClick={() => handleOpenRenameModal(group)}
                  >
                    Переименовать
                  </button>
                  <button
                    className="icon-btn danger"
                    onClick={() => handleDeleteGroup(group.id)}
                  >
                    Удалить
                  </button>
                </div>
              </header>

              <div className="members">
                {group.members.length === 0 ? (
                  <div className="empty">В группе пока нет студентов</div>
                ) : (
                  group.members.map((studentId) => {
                    const student = allStudents.find((s) => s.id === studentId);
                    if (!student) return null;

                    return (
                      <div key={studentId} className="member">
                        <span className="avatar">{getInitials(student.name)}</span>
                        <span className="member-name">{student.name}</span>
                        <button
                          className="remove"
                          onClick={() => handleRemoveStudent(group.id, studentId)}
                          title="Исключить студента из группы"
                        >
                          Убрать
                        </button>
                      </div>
                    );
                  })
                )}
              </div>

              {/* Нижняя строка добавления нераспределённого студента */}
              <div className="assign-row">
                <select
                  className="assign-select"
                  value={selectedStudentForGroup[group.id] || ''}
                  onChange={(e) =>
                    setSelectedStudentForGroup({
                      ...selectedStudentForGroup,
                      [group.id]: e.target.value,
                    })
                  }
                >
                  <option value="">Выберите свободного студента</option>
                  {unassigned.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
                <button
                  className="btn"
                  onClick={() => handleAssignStudent(group.id)}
                  disabled={unassigned.length === 0}
                >
                  Добавить
                </button>
              </div>
            </section>
          ))}
        </div>
      )}

      {/* Модальное окно создания / переименования группы */}
      {isModalOpen && (
        <div className="modal-bg" onClick={() => setIsModalOpen(false)}>
          <form
            className="modal"
            onSubmit={handleModalSubmit}
            onClick={(e) => e.stopPropagation()}
          >
            <h2>{editingGroup ? 'Переименовать группу' : 'Создать группу'}</h2>

            <div className="field">
              <label htmlFor="groupName">Название группы</label>
              <input
                id="groupName"
                required
                placeholder="Например, Команда 1 (Frontend)"
                value={groupNameInput}
                onChange={(e) => setGroupNameInput(e.target.value)}
                autoFocus
              />
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
