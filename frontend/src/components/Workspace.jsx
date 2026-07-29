import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getProjects, createProject, deleteProject } from '../api/client';
import './Workspace.css';

const Workspace = () => {
  const [projects, setProjects] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isCreating, setIsCreating] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    fetchProjects();
  }, []);

  const fetchProjects = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getProjects();
      setProjects(data || []);
    } catch (err) {
      setError('Failed to load projects. Please try again later.');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateProject = async () => {
    setIsCreating(true);
    setError(null);
    try {
      const newProject = await createProject(`Untitled Project ${projects.length + 1}`);
      if (newProject && newProject.id) {
        navigate(`/projects/${newProject.id}`);
      }
    } catch (err) {
      setError('Failed to create a new project.');
      console.error(err);
    } finally {
      setIsCreating(false);
    }
  };

  const handleDeleteProject = async (e, projectId) => {
    e.stopPropagation();
    if (!window.confirm('Delete this project? This cannot be undone.')) return;
    try {
      await deleteProject(projectId);
      setProjects((prev) => prev.filter((p) => String(p.id) !== String(projectId)));
    } catch (err) {
      console.error('Failed to delete project:', err);
    }
  };

  const renderProjects = () => {
    if (isLoading) {
      return (
        <div className="workspace-loading">
          <div className="spinner"></div>
          <p>Loading your projects...</p>
        </div>
      );
    }

    if (error) {
      return (
        <div className="workspace-error">
          <p>{error}</p>
          <button onClick={fetchProjects}>Retry</button>
        </div>
      );
    }

    if (projects.length === 0) {
      return (
        <div className="empty-state">
          <div className="empty-state-icon">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18"></rect>
              <line x1="7" y1="2" x2="7" y2="22"></line>
              <line x1="17" y1="2" x2="17" y2="22"></line>
              <line x1="2" y1="12" x2="22" y2="12"></line>
              <line x1="2" y1="7" x2="7" y2="7"></line>
              <line x1="2" y1="17" x2="7" y2="17"></line>
              <line x1="17" y1="17" x2="22" y2="17"></line>
              <line x1="17" y1="7" x2="22" y2="7"></line>
            </svg>
          </div>
          <h2 className="empty-state-title">No projects yet</h2>
          <p className="empty-state-desc">Get started by creating a new video editing project.</p>
          <button className="btn-primary" onClick={handleCreateProject} disabled={isCreating}>
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
            {isCreating ? 'Creating...' : 'Create Project'}
          </button>
        </div>
      );
    }

    return (
      <div className="projects-grid">
        {projects.map((project) => (
          <div
            key={project.id}
            className="project-card"
            onClick={() => navigate(`/projects/${project.id}`)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') navigate(`/projects/${project.id}`); }}
          >
            <h3>{project.title || 'Untitled Project'}</h3>
            <p>
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"></circle>
                <polyline points="12 6 12 12 16 14"></polyline>
              </svg>
              {new Date(project.created_at || Date.now()).toLocaleDateString()}
            </p>
            <button
              className="project-card-delete"
              onClick={(e) => handleDeleteProject(e, project.id)}
              title="Delete project"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="3 6 5 6 21 6"></polyline>
                <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path>
                <path d="M10 11v6"></path>
                <path d="M14 11v6"></path>
              </svg>
            </button>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="workspace-container animate-fade-in">

      <header className="workspace-header">
        <div>
          <h1 className="workspace-title">Projects</h1>
          <p className="workspace-subtitle">Manage and edit your video editing projects.</p>
        </div>
        {projects.length > 0 && !isLoading && !error && (
          <button className="btn-primary" onClick={handleCreateProject} disabled={isCreating}>
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
            {isCreating ? 'Creating...' : 'New Project'}
          </button>
        )}
      </header>

      <div className="projects-section">
        <h2 className="section-heading">
          <span className="section-heading-icon">🎬</span>
          Your Projects
        </h2>
        <div className="projects-scroll-area">
          {renderProjects()}
        </div>
      </div>

    </div>
  );
};

export default Workspace;
