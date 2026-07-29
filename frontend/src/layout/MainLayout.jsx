import React from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from '../components/Sidebar';
import AIAssistant from '../components/AIAssistant';
import ParticleBackground from '../components/ParticleBackground';
import './MainLayout.css';

const MainLayout = () => {
  return (
    <>
      <ParticleBackground />
      <div className="main-layout">
        <Sidebar />
        <main className="workspace-area">
          <Outlet />
        </main>
        <AIAssistant />
      </div>
    </>
  );
};

export default MainLayout;
