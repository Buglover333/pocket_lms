import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AppProvider } from './context/AppContext';
import { Layout } from './components/Layout';

// Student Pages
import { StudentHome } from './pages/StudentHome';
import { StudentCourses } from './pages/StudentCourses';
import { CourseDetail } from './pages/CourseDetail';
import { AssignmentPage } from './pages/AssignmentPage';
import { StudentGroups } from './pages/StudentGroups';
import { StudentCalendar } from './pages/StudentCalendar';
import { ProfilePage } from './pages/ProfilePage';
import { SettingsPage } from './pages/SettingsPage';

// Teacher Pages
import { TeacherGroups } from './pages/TeacherGroups';
import { TeacherHome, TeacherCourses, TeacherGrades } from './pages/TeacherViews';

export default function App() {
  return (
    <AppProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            {/* Студенческие маршруты */}
            <Route index element={<StudentHome />} />
            <Route path="courses" element={<StudentCourses />} />
            <Route path="course/:id" element={<CourseDetail />} />
            <Route path="assignment/:id" element={<AssignmentPage />} />
            <Route path="groups" element={<StudentGroups />} />
            <Route path="calendar" element={<StudentCalendar />} />
            <Route path="profile" element={<ProfilePage />} />
            <Route path="settings" element={<SettingsPage />} />

            {/* Преподавательские маршруты */}
            <Route path="teacher/home" element={<TeacherHome />} />
            <Route path="teacher/courses" element={<TeacherCourses />} />
            <Route path="teacher/groups" element={<TeacherGroups />} />
            <Route path="teacher/grades" element={<TeacherGrades />} />
            <Route path="teacher/calendar" element={<StudentCalendar />} />

            {/* Fallback */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AppProvider>
  );
}
