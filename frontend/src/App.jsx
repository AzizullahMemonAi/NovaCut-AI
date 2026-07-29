import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import MainLayout from './layout/MainLayout';
import Auth from './components/Auth';
import ProtectedRoute from './components/ProtectedRoute';
import Workspace from './components/Workspace';
import ProjectDetail from './pages/ProjectDetail';
import Editor from './pages/Editor';
import Settings from './pages/Settings';
import MediaLibrary from './pages/MediaLibrary';
import AITools from './pages/AITools';
import { logoutUser } from './api/client';

function App() {
  useEffect(() => {
    const handleAuthError = () => {
      logoutUser();
      // We will handle redirecting using React Router or just reload if needed.
      // For now, reloading ensures we clear out of protected memory state,
      // but ideally we just let the ProtectedRoute catch the missing token on re-render.
      window.location.href = '/login';
    };

    window.addEventListener('auth_error', handleAuthError);

    return () => {
      window.removeEventListener('auth_error', handleAuthError);
    };
  }, []);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Auth />} />
        <Route path="/register" element={<Auth />} />

        {/* Protected Routes wrapped in MainLayout for now */}
        <Route element={<ProtectedRoute />}>
          <Route element={<MainLayout />}>
            <Route path="/dashboard" element={<Workspace />} />
            <Route path="/ai-tools" element={<AITools />} />
            <Route path="/media" element={<MediaLibrary />} />
            <Route path="/projects/:id" element={<ProjectDetail />} />
            <Route path="/editor/:videoId" element={<Editor />} />
            <Route path="/settings" element={<Settings />} />
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
