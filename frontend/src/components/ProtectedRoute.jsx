import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { getToken } from '../api/client';

const ProtectedRoute = () => {
  const isAuthenticated = !!getToken();
  
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
};

export default ProtectedRoute;
