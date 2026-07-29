import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { getProject, getVideos, uploadVideo, deleteVideo, updateVideo } from '../api/client';
import './ProjectDetail.css';

const ProjectDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [project, setProject] = useState(null);
  const [videos, setVideos] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const fileInputRef = useRef(null);

  const [editingVideoId, setEditingVideoId] = useState(null);
  const [editName, setEditName] = useState('');
  const [renameError, setRenameError] = useState(null);

  useEffect(() => {
    const fetchProjectData = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const [projectData, videosData] = await Promise.all([
          getProject(id),
          getVideos(id)
        ]);
        setProject(projectData);
        setVideos(videosData || []);
      } catch (err) {
        setError('Failed to load project details.');
        console.error(err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchProjectData();
  }, [id]);

  const retryFetch = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [projectData, videosData] = await Promise.all([
        getProject(id),
        getVideos(id)
      ]);
      setProject(projectData);
      setVideos(videosData || []);
    } catch (err) {
      setError('Failed to load project details.');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith('video/')) {
      setUploadError('Please select a valid video file.');
      return;
    }

    setIsUploading(true);
    setUploadError(null);
    try {
      const result = await uploadVideo(file, id);
      if (result && result.id) {
        // Automatically navigate to the editor with the new video
        navigate(`/editor/${result.id}`);
      }
    } catch (err) {
      setUploadError(err.message || 'Failed to upload video.');
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleDelete = async (videoId, e) => {
    e.stopPropagation();
    if (!confirm('Delete this video? This action cannot be undone.')) return;
    try {
      await deleteVideo(videoId);
      setVideos(prev => prev.filter(v => v.id !== videoId));
    } catch (err) {
      console.error('Delete failed:', err);
    }
  };

  const handleEditClick = (video, e) => {
    e.stopPropagation();
    setEditingVideoId(video.id);
    setEditName(video.original_filename || video.filename || '');
    setRenameError(null);
  };

  const handleCancelEdit = (e) => {
    e?.stopPropagation();
    setEditingVideoId(null);
    setEditName('');
    setRenameError(null);
  };

  const handleRename = async (videoId, e) => {
    e?.stopPropagation();
    const trimmed = editName.trim();
    if (!trimmed) {
      setRenameError('Name cannot be empty');
      return;
    }
    try {
      const updated = await updateVideo(videoId, { original_filename: trimmed });
      setVideos(prev => prev.map(v => v.id === videoId ? { ...v, ...updated } : v));
      setEditingVideoId(null);
      setEditName('');
      setRenameError(null);
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Failed to rename';
      console.error('Rename failed:', err);
      setRenameError(msg);
    }
  };

  if (isLoading) {
    return (
      <div className="project-detail-container loading">
        <div className="spinner"></div>
        <p>Loading project...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="project-detail-container error">
        <p>{error}</p>
        <div className="error-actions">
          <button className="btn-secondary" onClick={() => navigate('/dashboard')}>Back to Dashboard</button>
          <button className="btn-primary" onClick={retryFetch}>Retry</button>
        </div>
      </div>
    );
  }

  return (
    <div className="project-detail-container animate-fade-in">
      <header className="project-header">
        <div className="header-left">
          <Link to="/dashboard" className="back-link">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="19" y1="12" x2="5" y2="12"></line>
              <polyline points="12 19 5 12 12 5"></polyline>
            </svg>
            Dashboard
          </Link>
          <span className="header-divider"></span>
          <h1 className="project-title">{project?.title || 'Project Details'}</h1>
        </div>
      </header>

      {uploadError && (
        <div className="upload-error-alert">
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="12" y1="8" x2="12" y2="12"></line>
            <line x1="12" y1="16" x2="12.01" y2="16"></line>
          </svg>
          {uploadError}
          <button className="close-alert" onClick={() => setUploadError(null)}>&times;</button>
        </div>
      )}

      <div className="project-content">
        <div className="upload-section">
          <input 
            type="file" 
            accept="video/*" 
            ref={fileInputRef} 
            onChange={handleFileUpload} 
            style={{ display: 'none' }} 
            id="video-upload-input"
          />
          <label 
            htmlFor="video-upload-input" 
            className={`upload-dropzone ${isUploading ? 'uploading' : ''}`}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') document.getElementById('video-upload-input').click(); }}
            tabIndex={0}
            role="button"
          >
            {isUploading ? (
              <div className="upload-progress">
                <div className="spinner"></div>
                <h3>Uploading Video...</h3>
                <p>Please do not close this page.</p>
              </div>
            ) : (
              <>
                <div className="upload-icon">
                  <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
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
                <h3>Upload Raw Video</h3>
                <p>Click or drag a video file here to start editing.</p>
                <span className="btn-primary" style={{ marginTop: '16px' }}>Select File</span>
              </>
            )}
          </label>
        </div>

        {videos.length > 0 && (
          <div className="videos-list-section">
            <h2 className="section-title">Project Media</h2>
            <div className="videos-grid">
{videos.map((video) => (
                <div
                  key={video.id}
                  className="video-card"
                  onClick={() => navigate(`/editor/${video.id}`)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') navigate(`/editor/${video.id}`) }}
                >
                  <div className="video-thumbnail">
                    <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      <polygon points="5 3 19 12 5 21 5 3"></polygon>
                    </svg>
                  </div>
                  <div className="video-info">
                    {editingVideoId === video.id ? (
                      <div className="rename-inline" onClick={e => e.stopPropagation()}>
                        <input
                          type="text"
                          className="rename-input"
                          value={editName}
                          onChange={e => setEditName(e.target.value)}
                          onKeyDown={e => {
                            e.stopPropagation();
                            if (e.key === 'Enter') handleRename(video.id, e);
                            if (e.key === 'Escape') handleCancelEdit(e);
                          }}
                          autoFocus
                        />
                        {renameError && <span className="rename-error">{renameError}</span>}
                        <div className="rename-actions">
                          <button className="rename-btn save" onClick={e => handleRename(video.id, e)}>Save</button>
                          <button className="rename-btn cancel" onClick={handleCancelEdit}>Cancel</button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <h4>{video.original_filename || video.filename || 'Untitled Video'}</h4>
                        <p>{new Date(video.created_at || Date.now()).toLocaleDateString()}</p>
                      </>
                    )}
                  </div>
                  <div className="video-card-actions">
                    <button
                      className="video-card-action edit"
                      onClick={e => handleEditClick(video, e)}
                      title="Rename Video"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                      </svg>
                    </button>
                    <button
                      className="video-card-action delete"
                      onClick={e => handleDelete(video.id, e)}
                      title="Delete Video"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="3 6 5 6 21 6"></polyline>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                      </svg>
                    </button>
                  </div>
</div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ProjectDetail;
