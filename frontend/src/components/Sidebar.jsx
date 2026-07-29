import React from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import logo from '../assets/logo.png';
import './Sidebar.css';

// SVG Icons inline to avoid external dependencies
const Icons = {
  Projects: (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7"></rect>
      <rect x="14" y="3" width="7" height="7"></rect>
      <rect x="14" y="14" width="7" height="7"></rect>
      <rect x="3" y="14" width="7" height="7"></rect>
    </svg>
  ),
  MediaLibrary: (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18"></rect>
      <line x1="7" y1="2" x2="7" y2="22"></line>
      <line x1="17" y1="2" x2="17" y2="22"></line>
      <line x1="2" y1="12" x2="22" y2="12"></line>
      <line x1="2" y1="7" x2="7" y2="7"></line>
      <line x1="2" y1="17" x2="7" y2="17"></line>
      <line x1="17" y1="17" x2="22" y2="17"></line>
      <line x1="17" y1="7" x2="22" y2="7"></line>
    </svg>
  ),
  AITools: (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2v4M5 6l2.3 2.3M19 6l-2.3 2.3"></path>
      <rect x="3" y="10" width="18" height="11" rx="2" ry="2"></rect>
      <circle cx="8.5" cy="14.5" r="1"></circle>
      <circle cx="15.5" cy="14.5" r="1"></circle>
      <path d="M9 18h6"></path>
    </svg>
  ),
  Settings: (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3"></circle>
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
    </svg>
  )
};

const SidebarItem = ({ label, icon, isActive, to }) => {
  return (
    <Link
      to={to}
      className={`sidebar-item ${isActive ? 'active' : ''}`}
      aria-current={isActive ? 'page' : undefined}
      style={{ textDecoration: 'none' }}
    >
      <div className="sidebar-item-icon">
        {icon}
      </div>
      <span className="sidebar-item-label">{label}</span>
    </Link>
  );
};

const Sidebar = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const currentPath = location.pathname;

  const handleLogoClick = () => {
    navigate('/dashboard');
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div 
          className="sidebar-brand-logo-container" 
          onClick={handleLogoClick}
          style={{ cursor: 'pointer' }}
          title="Go to Home"
        >
          <img src={logo} alt="NovaCut AI logo" className="sidebar-logo-img" />
        </div>
        <span className="sidebar-brand-name">NovaCut AI</span>
      </div>

      <div className="sidebar-section-label">Workspace</div>

      <nav className="sidebar-nav">
        <SidebarItem
          label="Projects"
          icon={Icons.Projects}
          isActive={currentPath.startsWith('/dashboard') || currentPath.startsWith('/projects')}
          to="/dashboard"
        />
        <SidebarItem
          label="AI Tools"
          icon={Icons.AITools}
          isActive={currentPath.startsWith('/ai-tools')}
          to="/ai-tools"
        />
        <SidebarItem
          label="Media Library"
          icon={Icons.MediaLibrary}
          isActive={currentPath.startsWith('/media')}
          to="/media"
        />
      </nav>

      <div className="sidebar-nav-bottom">
        <SidebarItem
          label="Settings"
          icon={Icons.Settings}
          isActive={currentPath.startsWith('/settings')}
          to="/settings"
        />
      </div>
    </aside>
  );
};

export default Sidebar;
