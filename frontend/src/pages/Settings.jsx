import React, { useState, useEffect } from 'react';
import { getAIStatus, saveAIConfig, getUserProfile, logoutUser } from '../api/client';
import './Settings.css';

const Settings = () => {
  const [profile, setProfile] = useState(null);
  const [geminiKey, setGeminiKey] = useState('');
  const [groqKey, setGroqKey] = useState('');
  const [status, setStatus] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadProfile();
    loadStatus();
  }, []);

  const loadProfile = async () => {
    try {
      const data = await getUserProfile();
      setProfile(data);
    } catch (err) {
      console.error("Failed to load user profile", err);
    }
  };

  const loadStatus = async () => {
    try {
      const data = await getAIStatus();
      setStatus(data);
    } catch (err) {
      console.error("Failed to load AI status", err);
    }
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await saveAIConfig(geminiKey, groqKey);
      setGeminiKey('');
      setGroqKey('');
      await loadStatus();
    } catch (err) {
      console.error("Save failed", err);
    } finally {
      setSaving(false);
    }
  };

  const handleLogout = () => {
    logoutUser();
    window.dispatchEvent(new Event('auth_error'));
  };

  return (
    <div className="settings-container animate-fade-in">
      <header className="workspace-header">
        <div>
          <h1 className="workspace-title">Settings</h1>
          <p className="workspace-subtitle">Manage preferences and AI configuration.</p>
        </div>
      </header>

      <section className="settings-card">
        <h2 className="settings-section-title">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
            <circle cx="12" cy="7" r="4"></circle>
          </svg>
          Account
        </h2>
        <div className="profile-info">
          <div className="profile-avatar">
            {(profile?.full_name || profile?.email || 'U').charAt(0).toUpperCase()}
          </div>
          <div className="profile-details">
            <div className="profile-name">{profile?.full_name || '—'}</div>
            <div className="profile-email">{profile?.email || '—'}</div>
          </div>
        </div>
        <div className="settings-divider" />
        <button 
          onClick={handleLogout} 
          className="btn-primary logout-btn"
        >
          Log Out
        </button>
      </section>

      <section className="settings-card">
        <h2 className="settings-section-title">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2v20"></path>
            <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path>
          </svg>
          AI Configuration
        </h2>
        
        {status && (
          <div style={{ display: 'flex', gap: 'var(--space-12)', marginBottom: 'var(--space-32)' }}>
            <div className="status-badge">
              <div className={`status-dot ${status.gemini_configured ? 'active' : 'inactive'}`} />
              Gemini
            </div>
            <div className="status-badge">
              <div className={`status-dot ${status.groq_configured ? 'active' : 'inactive'}`} />
              Groq
            </div>
          </div>
        )}

        <form className="settings-form" onSubmit={handleSave}>
          <div className="form-group">
            <label className="form-label">Gemini API Key</label>
            <input 
              type="password" 
              className="form-input"
              value={geminiKey}
              onChange={(e) => setGeminiKey(e.target.value)}
              placeholder="Enter new key to update..."
            />
          </div>
          
          <div className="form-group">
            <label className="form-label">Groq API Key</label>
            <input 
              type="password" 
              className="form-input"
              value={groqKey}
              onChange={(e) => setGroqKey(e.target.value)}
              placeholder="Enter new key to update..."
            />
          </div>

          <div className="form-actions">
            <button 
              type="submit" 
              className="btn-primary"
              disabled={saving || (!geminiKey && !groqKey)}
              style={{ opacity: (saving || (!geminiKey && !groqKey)) ? 0.5 : 1 }}
            >
              {saving ? 'Saving...' : 'Save Configuration'}
            </button>
          </div>
        </form>
      </section>


    </div>
  );
};

export default Settings;
