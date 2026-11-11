import axios from 'axios';

// Используем относительный путь /api благодаря proxy в vite.config.js или прямой адрес
export const API_BASE_URL = 'http://127.0.0.1:8000';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 4000,
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('pocket_lms_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Флаг доступности бэкенда
export let isBackendOnline = false;

export async function checkBackendHealth() {
  try {
    // Делаем легкий запрос к корню или docs
    const res = await axios.get(`${API_BASE_URL}/docs`, { timeout: 2000 });
    isBackendOnline = res.status === 200;
  } catch (e) {
    isBackendOnline = false;
  }
  return isBackendOnline;
}

// -------------------------------------------------------------
// Резервное локальное хранилище (Mock State) на случай,
// если Docker/FastAPI локально временно не запущены.
// Это гарантирует, что на парах интерфейс НИКОГДА не упадет.
// -------------------------------------------------------------
const mockColors = [
  '#63aaa5', '#d96b5f', '#586b50', '#71965f', '#5898c2',
  '#c98365', '#6d83a8', '#9b7aa6', '#6f9b8b', '#a9855c'
];

let mockState = {
  profile: {
    first_name: 'Роман',
    last_name: 'Шепелев',
    email: 'roman@example.ru',
    nick: '@shepelev_dev',
    photo: null,
  },
  courses: [
    { id: 1, title: 'Курс 1', description: 'Краткое описание курса 1. Веб-разработка и основы архитектуры.', color: mockColors[0] },
    { id: 2, title: 'Курс 2', description: 'Краткое описание курса 2. Проектирование баз данных.', color: mockColors[1] },
    { id: 3, title: 'Курс 3', description: 'Краткое описание курса 3. Операционные системы и сети.', color: mockColors[2] },
    { id: 4, title: 'Курс 4', description: 'Краткое описание курса 4. UI/UX дизайн веб-сервисов.', color: mockColors[3] },
    { id: 5, title: 'Курс 5', description: 'Краткое описание курса 5. Управление программными проектами.', color: mockColors[4] },
    { id: 6, title: 'Курс 6', description: 'Краткое описание курса 6. Разработка на React и FastAPI.', color: mockColors[5] },
  ],
  students: [
    { id: 1, name: 'Петров Пётр', email: 'petrov@example.ru', nick: '@petrov' },
    { id: 2, name: 'Иванов Иван', email: 'ivanov@example.ru', nick: '@ivanov' },
    { id: 3, name: 'Сидоров Сергей', email: 'sidorov@example.ru', nick: '@sidorov' },
    { id: 4, name: 'Смирнова Анна', email: 'smirnova@example.ru', nick: '@smirnova' },
    { id: 5, name: 'Кузнецова Мария', email: 'kuznetsova@example.ru', nick: '@kuznetsova' },
    { id: 6, name: 'Волков Алексей', email: 'volkov@example.ru', nick: '@volkov' },
  ],
  groupsByCourse: {
    1: [
      { id: 11, name: 'Команда 1', members: [1, 2] },
      { id: 12, name: 'Команда 2', members: [3] },
    ],
    2: [
      { id: 21, name: 'Проектная группа', members: [2, 4, 5] },
    ],
    3: [
      { id: 31, name: 'Группа А', members: [1, 3] },
      { id: 32, name: 'Группа Б', members: [4, 6] },
    ],
  },
  assignments: {
    1: {
      id: 1,
      title: 'Домашняя работа 1 пара',
      dueDate: '10 ноября, 23:59',
      maxScore: 20,
      description: 'Домашняя работа пара 1. Разработка архитектуры и прототипирование интерфейса.',
      submitted: false,
      grade: null,
      feedback: null,
      fileName: null,
    },
  },
  calendarEvents: [
    { date: '2026-10-10', courseId: 1, title: 'Дедлайн 1', done: false },
    { date: '2026-10-12', courseId: 2, title: 'Дедлайн 2', done: false },
    { date: '2026-10-14', courseId: 1, title: 'Сдано: домашняя работа', done: true },
    { date: '2026-10-15', courseId: 3, title: 'Дедлайн 3', done: false },
    { date: '2026-10-18', courseId: 4, title: 'Дедлайн 4', done: false },
    { date: '2026-10-20', courseId: 5, title: 'Дедлайн 5', done: false },
  ],
};

// -------------------------------------------------------------
// Сервисные методы API (с fallback на mock)
// -------------------------------------------------------------

export async function fetchUserProfile() {
  if (isBackendOnline) {
    try {
      const res = await apiClient.get('/get_user_info');
      return res.data;
    } catch (e) {
      console.warn('Backend fetchUserProfile failed, using mock', e);
    }
  }
  return mockState.profile;
}

export async function saveUserProfile(data) {
  if (isBackendOnline) {
    try {
      const res = await apiClient.patch('/update_settings', {
        first_name: data.first_name,
        last_name: data.last_name,
      });
      return res.data;
    } catch (e) {
      console.warn('Backend saveUserProfile failed, saving to mock', e);
    }
  }
  mockState.profile = { ...mockState.profile, ...data };
  return mockState.profile;
}

export async function fetchCourses() {
  if (isBackendOnline) {
    try {
      const res = await apiClient.get('/get_courses');
      if (res.data?.items?.length) {
        return res.data.items.map((c, i) => ({
          id: c.id,
          title: c.title || `Курс ${i + 1}`,
          description: c.description || 'Курс учебной программы',
          color: mockColors[i % mockColors.length],
        }));
      }
    } catch (e) {
      console.warn('Backend fetchCourses failed, using mock', e);
    }
  }
  return mockState.courses;
}

export async function fetchGroupsForCourse(courseId) {
  if (isBackendOnline) {
    try {
      const res = await apiClient.get(`/get_groups?course_id=${courseId}`);
      if (res.data?.items) {
        return res.data.items;
      }
    } catch (e) {
      console.warn('Backend fetchGroups failed, using mock', e);
    }
  }
  return mockState.groupsByCourse[courseId] || [];
}

export async function createGroup(courseId, name) {
  if (isBackendOnline) {
    try {
      const res = await apiClient.post('/create_group', {
        discipline_id: courseId,
        name: name,
      });
      return res.data;
    } catch (e) {
      console.warn('Backend createGroup failed, using mock', e);
    }
  }
  const newGroup = {
    id: Date.now(),
    name: name,
    members: [],
  };
  if (!mockState.groupsByCourse[courseId]) {
    mockState.groupsByCourse[courseId] = [];
  }
  mockState.groupsByCourse[courseId].push(newGroup);
  return newGroup;
}

export async function renameGroup(courseId, groupId, newName) {
  if (isBackendOnline) {
    try {
      const res = await apiClient.patch(`/update_group?team_id=${groupId}`, {
        name: newName,
      });
      return res.data;
    } catch (e) {
      console.warn('Backend renameGroup failed, using mock', e);
    }
  }
  const groups = mockState.groupsByCourse[courseId] || [];
  const g = groups.find((item) => item.id === groupId);
  if (g) g.name = newName;
  return g;
}

export async function deleteGroup(courseId, groupId) {
  if (isBackendOnline) {
    try {
      await apiClient.delete(`/delete_group?team_id=${groupId}`);
      return true;
    } catch (e) {
      console.warn('Backend deleteGroup failed, using mock', e);
    }
  }
  if (mockState.groupsByCourse[courseId]) {
    mockState.groupsByCourse[courseId] = mockState.groupsByCourse[courseId].filter(
      (g) => g.id !== groupId
    );
  }
  return true;
}

export async function assignStudentToGroup(courseId, groupId, studentId) {
  const groups = mockState.groupsByCourse[courseId] || [];
  const g = groups.find((item) => item.id === groupId);
  if (g && !g.members.includes(studentId)) {
    g.members.push(studentId);
  }
  return g;
}

export async function removeStudentFromGroup(courseId, groupId, studentId) {
  const groups = mockState.groupsByCourse[courseId] || [];
  const g = groups.find((item) => item.id === groupId);
  if (g) {
    g.members = g.members.filter((id) => id !== studentId);
  }
  return g;
}

export function getAllStudents() {
  return mockState.students;
}

export function getCalendarEvents() {
  return mockState.calendarEvents;
}

export function getAssignment(id = 1) {
  return mockState.assignments[id];
}

export function submitAssignmentMock(id = 1, fileName = 'homework.pdf') {
  mockState.assignments[id] = {
    ...mockState.assignments[id],
    submitted: true,
    fileName: fileName,
  };
  return mockState.assignments[id];
}

export function resubmitAssignmentMock(id = 1) {
  mockState.assignments[id] = {
    ...mockState.assignments[id],
    submitted: false,
    fileName: null,
    grade: null,
  };
  return mockState.assignments[id];
}
