import React from 'react';
import { useNavigate } from 'react-router-dom';
import { getVideos } from '../api/client';
import './AITools.css';

const AITools = () => {
    const navigate = useNavigate();

    const tools = [
        {
            id: 'captions',
            title: 'AI Auto Captions',
            desc: 'Instantly generate accurate subtitles, transcripts, and lower thirds for your speech.',
            icon: '📝',
            tag: 'Popular',
            color: '#5B7FFF'
        },
        {
            id: 'analysis',
            title: 'AI Video Analysis',
            desc: 'Analyze visual content, identify objects, and get smart editing suggestions automatically.',
            icon: '🔍',
            tag: 'Experimental',
            color: '#A78BFA'
        },
        {
            id: 'audio',
            title: 'AI Audio Cleanup',
            desc: 'Remove background noise, echoes, and auto-enhance voice clarity in one click.',
            icon: '🔊',
            tag: 'New',
            color: '#34D399'
        },
        {
            id: 'highlights',
            title: 'AI Highlights',
            desc: 'Automatically extract the most engaging moments to create short-form viral clips.',
            icon: '🌟',
            tag: 'Beta',
            color: '#FBBF24'
        }
    ];

    const handleLaunchTool = async (toolId) => {
        try {
            const videos = await getVideos();
            if (Array.isArray(videos) && videos.length > 0) {
                navigate(`/editor/${videos[0].id}?tool=${toolId}`);
            } else {
                navigate('/media');
            }
        } catch (err) {
            navigate('/media');
        }
    };

    return (
        <div className="ai-tools-container animate-fade-in">
            <header className="ai-tools-header">
                <div className="header-text">
                    <h1 className="workspace-title">AI Tools</h1>
                    <p className="workspace-subtitle">Supercharge your editing process with next-generation artificial intelligence.</p>
                </div>
            </header>

            <div className="ai-tools-page-grid">
                {tools.map(tool => (
                    <div 
                        key={tool.id} 
                        className="ai-tools-page-card" 
                        style={{ '--accent-color': tool.color, cursor: 'pointer' }}
                        onClick={() => handleLaunchTool(tool.id)}
                        role="button"
                        tabIndex={0}
                        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleLaunchTool(tool.id); }}
                    >
                        <div className="card-top">
                            <div className="ai-tools-page-icon">{tool.icon}</div>
                            {tool.tag && <span className="ai-tools-badge">{tool.tag}</span>}
                        </div>
                        <div className="ai-tools-page-info">
                            <h3>{tool.title}</h3>
                            <p>{tool.desc}</p>
                        </div>
                        <div className="card-action">
                            <span className="action-text">Launch Tool</span>
                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="action-arrow">
                                <line x1="5" y1="12" x2="19" y2="12"></line>
                                <polyline points="12 5 19 12 12 19"></polyline>
                            </svg>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default AITools;
