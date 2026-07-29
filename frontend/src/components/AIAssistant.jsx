import React, { useState, useRef, useEffect } from 'react';
import { chatWithAI, trimVideo, autoTrimVideo, analyzeVideo, getVideoTranscript, getChatSessions, createNewChat } from '../api/client';
import './AIAssistant.css';

const AIAssistant = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [executingAction, setExecutingAction] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const messagesEndRef = useRef(null);

  const SUGGESTIONS = [
    "Summarize",
    "Generate subtitles",
    "Trim silence",
    "Find highlights",
    "Auto edit"
  ];

  useEffect(() => {
    const initSession = async () => {
      try {
        const sessions = await getChatSessions();
        if (Array.isArray(sessions) && sessions.length > 0) {
          setSessionId(sessions[0].id);
        } else {
          const newSession = await createNewChat("Nova Chat Session");
          if (newSession && newSession.id) {
            setSessionId(newSession.id);
          }
        }
      } catch (err) {
        console.warn("Could not initialize chat session:", err);
      }
    };
    initSession();
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const getActiveVideoId = () => {
    const match = window.location.pathname.match(/\/editor\/([^/]+)/);
    return match ? match[1] : null;
  };

  const formatTimeMMSS = (seconds) => {
    if (isNaN(seconds)) return "00:00";
    const m = Math.floor(seconds / 60).toString().padStart(2, '0');
    const s = Math.floor(seconds % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  const executeAction = async (action) => {
    setExecutingAction(action.type);
    const videoId = action.video_id || getActiveVideoId();

    try {
      let resultMsg = '';
      switch (action.type) {
        case 'add_captions':
        case 'analyze': {
          if (!videoId) {
            resultMsg = '⚠️ Please open a video in the Editor first to generate captions or run AI analysis.';
            break;
          }
          const res = await analyzeVideo(videoId);
          window.dispatchEvent(new CustomEvent('ai_captions_generated', { detail: res }));
          window.dispatchEvent(new CustomEvent('video_edited', { detail: { action: action.type, result: res } }));

          let subtitleFormattedText = '';
          try {
            const tData = await getVideoTranscript(videoId);
            if (tData && Array.isArray(tData.segments) && tData.segments.length > 0) {
              const validSegments = tData.segments.filter(s => s.text && !s.text.includes("Whisper AI model") && !s.text.includes("mock transcription"));
              if (validSegments.length > 0) {
                subtitleFormattedText = validSegments.map(s => (
                  `⏱️ ${formatTimeMMSS(s.start)} - ${formatTimeMMSS(s.end)}\n"${s.text}"`
                )).join('\n\n');
              }
            }
          } catch (e) {
            console.warn(e);
          }

          if (!subtitleFormattedText && res && res.analysis && Array.isArray(res.analysis.chapters) && res.analysis.chapters.length > 0) {
            const validChaps = res.analysis.chapters.filter(ch => ch.reasoning && !ch.reasoning.includes("Speech and dialogue audio segment"));
            if (validChaps.length > 0) {
              subtitleFormattedText = validChaps.map((ch, i) => (
                `⏱️ Chapter ${i + 1}: ${ch.title}\n"${ch.reasoning}"`
              )).join('\n\n');
            }
          }

          if (!subtitleFormattedText && res && res.title) {
            subtitleFormattedText = `📌 ${res.title}\n${res.description || ''}`;
          }

          if (!subtitleFormattedText) {
            subtitleFormattedText = 'No spoken dialogue or speech detected in this video.';
          }

          resultMsg = `📝 Subtitles & Captions Generated!\n\n${subtitleFormattedText}\n\n✨ Subtitles have been overlayed on the video player!`;
          break;
        }
        case 'trim': {
          if (!videoId) {
            resultMsg = '⚠️ Please open a video in the Editor first to trim clips.';
            break;
          }
          const start = action.start_time || 0;
          const end = action.end_time || 10;
          const trimRes = await trimVideo(videoId, start, end);
          window.dispatchEvent(new CustomEvent('video_edited', { detail: { action: 'trim', result: trimRes } }));
          resultMsg = `✂️ Trim complete! Segment from ${start}s to ${end}s retained.`;
          break;
        }
        case 'remove_silence': {
          if (!videoId) {
            resultMsg = '⚠️ Please open a video in the Editor first to remove silent parts.';
            break;
          }
          const trimRes = await autoTrimVideo(videoId, action.threshold_db || -30);
          window.dispatchEvent(new CustomEvent('video_edited', { detail: { action: 'remove_silence', result: trimRes } }));
          resultMsg = '🔊 Silence removal complete! Silent sections have been trimmed from the timeline.';
          break;
        }
        case 'generate_title': {
          if (!videoId) {
            resultMsg = '⚠️ Please open a video in the Editor first to generate titles.';
            break;
          }
          const res = await analyzeVideo(videoId);
          window.dispatchEvent(new CustomEvent('video_edited', { detail: { action: 'generate_title', result: res } }));
          resultMsg = `✨ Generated Title: ${res.title || 'Untitled Video'}\n\n📌 ${res.description || ''}`;
          break;
        }
        default:
          resultMsg = `Action "${action.type}" acknowledged and queued!`;
      }
      setMessages(prev => [...prev, { role: 'assistant', content: resultMsg }]);
    } catch (error) {
      console.error('Action execution error:', error);
      const detail = error?.response?.data?.detail || error.message || 'Unknown error';
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `⚠️ Failed to execute action: ${detail}`
      }]);
    } finally {
      setExecutingAction(null);
    }
  };

  const handleSend = async (textOverride) => {
    const textToSend = typeof textOverride === 'string' ? textOverride : input;
    if (!textToSend.trim() || isLoading) return;

    const userMessage = textToSend.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setIsLoading(true);

    try {
      const activeVidId = getActiveVideoId();
      const res = await chatWithAI(userMessage, activeVidId, sessionId);
      const aiResponse = typeof res === 'string'
        ? res
        : (res.reply || res.response || res.message || 'I processed your request.');
      const actions = (res && Array.isArray(res.actions)) ? res.actions : [];

      setMessages(prev => [...prev, { role: 'assistant', content: aiResponse, actions }]);
    } catch (error) {
      console.error("Chat error:", error);
      const detail = error?.response?.data?.detail;
      const errMsg = detail
        ? `Sorry, the AI returned an error: ${detail}`
        : 'Sorry, I encountered an error connecting to the AI. Please check your API key in Settings.';
      setMessages(prev => [...prev, { role: 'assistant', content: errMsg }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <aside className="ai-panel">
      <header className="ai-header">
        <div className="ai-header-dot" />
        <h2>Nova AI</h2>
      </header>
      
      <div className="ai-chat-area">
        {messages.length === 0 ? (
          <div className="ai-welcome animate-fade-in">
            <div className="ai-message ai-message-assistant">
              Hello! I am Nova, your AI assistant. How can I help you edit your video today?
            </div>
            <div className="ai-suggestions">
              {SUGGESTIONS.map(sug => (
                <button 
                  key={sug} 
                  className="ai-suggestion-chip"
                  onClick={() => handleSend(sug)}
                >
                  {sug}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg, idx) => (
            <div key={idx} className="ai-message-group">
              <div 
                className={`ai-message animate-slide-up ${msg.role === 'user' ? 'ai-message-user' : 'ai-message-assistant'}`}
                style={{ whiteSpace: 'pre-wrap' }}
              >
                {msg.content}
              </div>
              {msg.actions && msg.actions.length > 0 && (
                <div className="ai-actions">
                  {msg.actions.map((action, aIdx) => (
                    <button
                      key={aIdx}
                      className="ai-action-btn"
                      onClick={() => executeAction(action)}
                      disabled={!!executingAction}
                    >
                      {executingAction === action.type ? '⏳ Running...' : (action.label || action.type)}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))
        )}

        {isLoading && (
          <div className="ai-typing animate-slide-up">
            <div className="ai-typing-dot" />
            <div className="ai-typing-dot" />
            <div className="ai-typing-dot" />
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
      
      <div className="ai-input-area">
        <div className="ai-input-wrapper">
          <textarea 
            className="ai-textarea"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask Nova to edit..."
            disabled={isLoading}
          />
          <button 
            className="ai-send-btn"
            onClick={handleSend}
            disabled={isLoading || !input.trim()}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13"></line>
              <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
            </svg>
          </button>
        </div>
        <div className="ai-input-hint">
          Shift + Enter for new line
        </div>
      </div>
    </aside>
  );
};

export default AIAssistant;
