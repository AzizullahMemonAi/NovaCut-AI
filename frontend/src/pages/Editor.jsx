import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import VideoPlayer from '../components/VideoPlayer';
import Timeline from '../components/Timeline';
import { getVideos, analyzeVideo, getVideoTranscript, burnSubtitles, exportViralShort, exportTimeline, getServerOrigin } from '../api/client';
import './Editor.css';

const Editor = () => {
  const { videoId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [video, setVideo] = useState(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisData, setAnalysisData] = useState(null);
  const [viralShorts, setViralShorts] = useState([]);
  const [exportingShortIdx, setExportingShortIdx] = useState(null);
  const [showInsights, setShowInsights] = useState(false);
  const [showExportModal, setShowExportModal] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [exportResult, setExportResult] = useState(null);
  const [trimStartTime, setTrimStartTime] = useState(0);
  const [trimEndTime, setTrimEndTime] = useState(0);
  const [burnSubtitles, setBurnSubtitles] = useState(true);
  const [clips, setClips] = useState([]);
  const [selectedClipId, setSelectedClipId] = useState(null);
  const [actualDuration, setActualDuration] = useState(null);
  const timelineRef = useRef(null);

  const fetchVideoDetails = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const allVideos = await getVideos();
      const currentVideo = allVideos.find(v => v.id === parseInt(videoId) || v.id === videoId || v.stored_filename?.includes(videoId));

      if (currentVideo) {
        setVideo(currentVideo);
        if (currentVideo.ai_analysis) {
          try {
            const parsed = typeof currentVideo.ai_analysis === 'string' ? JSON.parse(currentVideo.ai_analysis) : currentVideo.ai_analysis;
            setAnalysisData(parsed);
          } catch (e) { }
        }
      } else {
        setVideo({ id: videoId, stored_filename: 'dummy.mp4', original_filename: 'Video Not Found', duration: 60 });
      }
    } catch (err) {
      setError('Failed to load video.');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchVideoDetails();
  }, [videoId]);

  const applyAnalysisCaptions = async (resData, targetVideo) => {
    const v = targetVideo || video;
    if (!v) return;

    let subtitleClips = [];

    // 1. Try to fetch real transcript segments from backend
    try {
      const transcriptData = await getVideoTranscript(v.id);
      if (transcriptData && Array.isArray(transcriptData.segments) && transcriptData.segments.length > 0) {
        const validSegments = transcriptData.segments.filter(s => s.text && !s.text.includes("Whisper AI model") && !s.text.includes("mock transcription"));
        if (validSegments.length > 0) {
          subtitleClips = validSegments.map((seg, idx) => ({
            id: `cap-clip-${idx}`,
            track: 'c1',
            startTime: seg.start,
            endTime: seg.end || (seg.start + 2.5),
            text: seg.text,
            name: `💬 ${seg.text}`
          }));
        }
      }
    } catch (e) {
      console.warn("Could not fetch transcript segments:", e);
    }

    // 2. If no audio speech segments, generate visual scene caption clips
    if (subtitleClips.length === 0) {
      const dur = v.duration || actualDuration || 60;
      const analysisObj = resData?.analysis || (v.ai_analysis ? (typeof v.ai_analysis === 'string' ? JSON.parse(v.ai_analysis) : v.ai_analysis) : null);
      
      // Filter out placeholder fallback strings
      const validChapters = (analysisObj?.chapters || []).filter(ch => 
        ch.reasoning && 
        !ch.reasoning.includes("Speech and dialogue audio segment") &&
        !ch.title.includes("00:00 - Main Content")
      );

      if (validChapters.length > 0) {
        const chapCount = validChapters.length;
        const interval = dur / chapCount;
        subtitleClips = validChapters.map((ch, idx) => ({
          id: `cap-clip-${idx}`,
          track: 'c1',
          startTime: Math.round(idx * interval * 100) / 100,
          endTime: Math.round((idx + 1) * interval * 100) / 100,
          text: ch.reasoning || ch.title,
          name: `💬 ${ch.title}`
        }));
      } else if (v.ai_description && v.ai_description.includes("Video transcript:")) {
        const cleanSpeech = v.ai_description.replace(/^Video transcript:\s*/, '');
        subtitleClips = [{
          id: 'cap-clip-0',
          track: 'c1',
          startTime: 0,
          endTime: dur,
          text: cleanSpeech,
          name: `💬 ${cleanSpeech.slice(0, 20)}`
        }];
      }
    }

    setClips(prev => {
      const filtered = prev.filter(c => c.track !== 'c1');
      return [...filtered, ...subtitleClips];
    });

    if (resData && resData.analysis) {
      setAnalysisData(resData.analysis);
      setShowInsights(true);
    }
    if (resData && resData.retention_edits) {
      applyRetentionEdits(resData.retention_edits);
    }
  };

  const applyRetentionEdits = (edits) => {
    if (!edits || !Array.isArray(edits)) return;
    
    const newClips = edits.map((item, idx) => {
      if (item.type === 'b_roll') {
        return {
          id: `v2-clip-${idx}`,
          track: 'v2',
          startTime: item.start,
          endTime: item.end,
          name: `📹 B-Roll: ${item.search_query || 'Stock Footage'}`,
          video_url: item.video_url,
          query: item.search_query,
          reason: item.reasoning
        };
      } else {
        return {
          id: `zoom-clip-${idx}`,
          track: 'v1',
          type: 'zoom_in',
          startTime: item.start,
          endTime: item.end,
          scale: item.scale || 1.25,
          name: `🔍 Punch-in Zoom (1.25x)`
        };
      }
    });

    setClips(prev => {
      const filtered = prev.filter(c => c.track !== 'v2' && c.type !== 'zoom_in');
      return [...filtered, ...newClips];
    });
  };

  // Initialize tracks V1 and A1 when video is loaded
  useEffect(() => {
    if (video) {
      const dur = video.duration || actualDuration || 60;
      const initialClips = [
        {
          id: 'v-clip-1',
          track: 'v1',
          startTime: 0,
          endTime: dur,
          sourceStart: 0,
          sourceEnd: dur,
          name: video.original_filename || 'Video Track V1'
        },
        {
          id: 'a-clip-1',
          track: 'a1',
          startTime: 0,
          endTime: dur,
          sourceStart: 0,
          sourceEnd: dur,
          name: `Audio Track A1`
        }
      ];

      setSelectedClipId('v-clip-1');

      // Asynchronously fetch transcript segments and combine cleanly
      getVideoTranscript(video.id).then((transcriptData) => {
        let subtitleClips = [];
        if (transcriptData && Array.isArray(transcriptData.segments) && transcriptData.segments.length > 0) {
          const validSegments = transcriptData.segments.filter(s => s.text && !s.text.includes("Whisper AI model") && !s.text.includes("mock transcription"));
          subtitleClips = validSegments.map((seg, idx) => ({
            id: `cap-clip-${idx}`,
            track: 'c1',
            startTime: seg.start,
            endTime: seg.end || (seg.start + 2.5),
            text: seg.text,
            name: `💬 ${seg.text}`
          }));
        }
        setClips([...initialClips, ...subtitleClips]);
      }).catch(() => {
        setClips(initialClips);
      });
    }
  }, [video, actualDuration]);

  useEffect(() => {
    const handleCaptionsGenerated = (e) => {
      if (e.detail) {
        applyAnalysisCaptions(e.detail);
      }
    };

    const handleVideoEdited = (e) => {
      const detail = e.detail;
      if (detail && detail.result && detail.result.video) {
        setVideo(prev => ({ ...prev, ...detail.result.video, output_filename: detail.result.output_filename }));
      }
      fetchVideoDetails();
    };

    window.addEventListener('ai_captions_generated', handleCaptionsGenerated);
    window.addEventListener('video_edited', handleVideoEdited);
    return () => {
      window.removeEventListener('ai_captions_generated', handleCaptionsGenerated);
      window.removeEventListener('video_edited', handleVideoEdited);
    };
  }, [video]);

  // Auto-trigger AI tool when launched from AITools page
  const launchTool = searchParams.get('tool');
  useEffect(() => {
    if (launchTool && video && video.id && !isAnalyzing && !analysisData) {
      const timer = setTimeout(() => {
        runAnalysis();
        setShowInsights(true);
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [launchTool, video]);

  const handleTimeUpdate = (time) => {
    setCurrentTime(time);
  };

  const handleDurationChange = (dur) => {
    if (dur > 0) {
      setActualDuration(dur);
      if (video && (!video.duration || video.duration <= 0 || Math.abs(video.duration - dur) > 1)) {
        setVideo(prev => prev ? { ...prev, duration: dur } : prev);
      }
    }
  };

  const handleHistoryChange = (canUndo, canRedo) => {
    // Update button states based on undo/redo availability
  };

  // NOTE: Keyboard shortcuts (Ctrl+Z / Ctrl+Shift+Z / Ctrl+Y) for undo/redo
  // are handled inside the Timeline component via its own keydown listener.
  // No duplicate listener here — having two would cause double-undo.


  const handleExportShort = async (shortItem, idx) => {
    if (!video) return;
    setExportingShortIdx(idx);
    try {
      const res = await exportViralShort(video.id, shortItem.start_time, shortItem.end_time, shortItem.viral_hook_title);
      if (res && res.download_url) {
        const link = document.createElement('a');
        link.href = res.download_url;
        link.setAttribute('download', res.output_filename || 'viral_short.mp4');
        document.body.appendChild(link);
        link.click();
        link.remove();
      } else {
        alert(`Short rendered successfully: ${res.output_filename || 'Done'}`);
      }
    } catch (e) {
      console.error(e);
      alert(`Failed to export viral short: ${e?.response?.data?.detail || e.message || e}`);
    } finally {
      setExportingShortIdx(null);
    }
  };

  const runAnalysis = async () => {
    if (!video) return;
    setIsAnalyzing(true);
    try {
      const result = await analyzeVideo(video.id);
      await applyAnalysisCaptions(result);
      if (result.analysis) {
        setAnalysisData(result.analysis);
        setShowInsights(true);
      }
      if (result.viral_shorts && Array.isArray(result.viral_shorts)) {
        setViralShorts(result.viral_shorts);
      }
    } catch (err) {
      console.error(err);
      const detail = err?.response?.data?.detail || err.message || 'Unknown error';
      alert(`AI Analysis Error: ${detail}`);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleExport = async () => {
    setIsExporting(true);
    setExportResult(null);

    const captionClips = clips.filter(c => c.track === 'c1' || c.isCaption);

    // Build SRT string from caption clips
    let srtString = "";
    captionClips.forEach((c, idx) => {
      const sSec = c.startTime;
      const eSec = c.endTime;
      const sH = String(Math.floor(sSec / 3600)).padStart(2, '0');
      const sM = String(Math.floor((sSec % 3600) / 60)).padStart(2, '0');
      const sS = String(Math.floor(sSec % 60)).padStart(2, '0');
      const sMS = String(Math.floor((sSec % 1) * 1000)).padStart(3, '0');
      const eH = String(Math.floor(eSec / 3600)).padStart(2, '0');
      const eM = String(Math.floor((eSec % 3600) / 60)).padStart(2, '0');
      const eS = String(Math.floor(eSec % 60)).padStart(2, '0');
      const eMS = String(Math.floor((eSec % 1) * 1000)).padStart(3, '0');
      srtString += `${idx + 1}\n${sH}:${sM}:${sS},${sMS} --> ${eH}:${eM}:${eS},${eMS}\n${c.text || c.name}\n\n`;
    });

    try {
      const outputFilename = `exported_${video.id}_${Date.now()}.mp4`;
      const outputSettings = { filename: outputFilename };

      // Attach SRT only when the user chose "Burn Subtitles"
      if (burnSubtitles && srtString.trim()) {
        outputSettings.burn_srt = srtString;
      }

      // Build operations — always use the /render endpoint for all export types
      let operations = [];
      const videoDuration = actualDuration || video?.duration || 0;

      if (trimStartTime > 0 || trimEndTime > 0) {
        // Manual trim: one explicit trim operation
        operations = [{
          type: 'trim',
          start: trimStartTime > 0 ? trimStartTime : 0,
          end: trimEndTime > 0 ? trimEndTime : videoDuration
        }];
      } else {
        // Full export: use v1 timeline clips (trimmed on timeline), or copy whole video
        const v1Clips = clips.filter(c => c.track === 'v1').sort((a, b) => a.startTime - b.startTime);
        if (v1Clips.length > 0) {
          operations = v1Clips.map(c => ({
            type: 'trim',
            start: c.sourceStart !== undefined ? c.sourceStart : (c.startTime || 0),
            end: c.sourceEnd !== undefined ? c.sourceEnd : (c.endTime || (c.startTime + 1))
          }));
        }
        // If no operations provided, backend copies the full video
      }

      const res = await exportTimeline(video.id, operations, outputSettings);
      if (res && res.output_filename) {
        const downloadUrl = res.download_url || `${getServerOrigin()}/outputs/${res.output_filename}`;
        setExportResult({
          url: downloadUrl,
          filename: res.output_filename,
          message: burnSubtitles ? "🔥 Video with burned subtitles ready!" : "✅ Export ready!"
        });
        window.dispatchEvent(new CustomEvent('video_edited', { detail: { action: 'render', result: res } }));
      } else {
        throw new Error('Export failed — no output file returned from server.');
      }
    } catch (err) {
      console.error("Export error:", err);
      const detail = err?.response?.data?.detail || err?.message || 'Unknown error';
      alert(`Export failed: ${detail}`);
    } finally {
      setIsExporting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="editor-container loading">
        <div className="spinner"></div>
        <p>Loading Editor...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="editor-container error">
        <p>{error}</p>
        <button className="btn-primary" onClick={() => navigate('/dashboard')}>Back to Dashboard</button>
      </div>
    );
  }

  return (
    <div className="editor-container animate-fade-in">
      <header className="editor-header">
        <div className="header-left">
          <button className="back-btn" onClick={() => navigate(-1)}>
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="19" y1="12" x2="5" y2="12"></line>
              <polyline points="12 19 5 12 12 5"></polyline>
            </svg>
          </button>
          <div className="video-title">
            <h2>{video?.original_filename || 'Untitled Video'}</h2>
            <span className="status-badge saved">Saved</span>
          </div>
        </div>

        <div className="header-actions">
          <button className="btn-secondary" onClick={runAnalysis} disabled={isAnalyzing}>
            {isAnalyzing ? '✨ Analyzing...' : '✨ Run AI Analysis'}
          </button>
          {analysisData && (
            <button className="btn-secondary" onClick={() => setShowInsights(!showInsights)}>
              {showInsights ? ' Hide Insights' : '📊 AI Insights'}
            </button>
          )}
          <button className="btn-primary export-btn" onClick={() => setShowExportModal(true)}>
            Export Video
          </button>
        </div>
      </header>

      {/* AI Insights Bar */}
      {showInsights && analysisData && (
        <div className="ai-insights-panel animate-slide-down" style={{ background: 'rgba(15, 23, 42, 0.95)', borderBottom: '1px solid rgba(255,255,255,0.1)', padding: '16px 24px', color: '#e2e8f0' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <h3 style={{ margin: 0, fontSize: '1rem', color: '#38bdf8', display: 'flex', alignItems: 'center', gap: '8px' }}>
              ✨ AI Video Analysis Insights
            </h3>
            <button style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', fontSize: '1.2rem' }} onClick={() => setShowInsights(false)}>&times;</button>
          </div>
          {analysisData.summary && (
            <div style={{ marginBottom: '12px' }}>
              <strong style={{ color: '#cbd5e1' }}>Summary:</strong>
              <p style={{ margin: '4px 0 0 0', fontSize: '0.9rem', color: '#94a3b8' }}>{analysisData.summary}</p>
            </div>
          )}
          {analysisData.keywords && analysisData.keywords.length > 0 && (
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '12px' }}>
              <strong style={{ color: '#cbd5e1', alignSelf: 'center' }}>Keywords:</strong>
              {analysisData.keywords.map((kw, i) => (
                <span key={i} style={{ background: 'rgba(56, 189, 248, 0.15)', color: '#38bdf8', padding: '2px 10px', borderRadius: '12px', fontSize: '0.8rem' }}>
                  #{kw}
                </span>
              ))}
            </div>
          )}
          {analysisData.chapters && analysisData.chapters.length > 0 && (
            <div>
              <strong style={{ color: '#cbd5e1' }}>Chapters:</strong>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '8px', marginTop: '6px' }}>
                {analysisData.chapters.map((ch, idx) => (
                  <div key={idx} style={{ background: 'rgba(255,255,255,0.05)', padding: '8px 12px', borderRadius: '6px', fontSize: '0.85rem' }}>
                    <div style={{ fontWeight: 600, color: '#f1f5f9' }}>{ch.title}</div>
                    <div style={{ color: '#94a3b8', fontSize: '0.75rem' }}>{ch.reasoning}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* OpusClip Viral Shorts Extractor Cards */}
          {viralShorts && viralShorts.length > 0 && (
            <div style={{ marginTop: '16px', paddingTop: '16px', borderTop: '1px solid rgba(255,255,255,0.1)' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
                <strong style={{ color: '#fbbf24', fontSize: '0.95rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  🔥 Viral Shorts Extractor (OpusClip AI Recommendations)
                </strong>
                <span style={{ fontSize: '0.75rem', color: '#94a3b8', background: 'rgba(251,191,36,0.1)', padding: '2px 8px', borderRadius: '4px', border: '1px solid rgba(251,191,36,0.2)' }}>
                  Top {viralShorts.length} Clips Selected
                </span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '12px' }}>
                {viralShorts.map((short, idx) => (
                  <div key={idx} style={{ background: 'linear-gradient(135deg, rgba(30,41,59,0.8), rgba(15,23,42,0.9))', border: '1px solid rgba(251,191,36,0.25)', padding: '12px 14px', borderRadius: '10px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                        <span style={{ fontWeight: 700, color: '#f8fafc', fontSize: '0.9rem' }}>{short.viral_hook_title || `Short #${idx + 1}`}</span>
                        <span style={{ background: '#f59e0b', color: '#000', fontWeight: 800, fontSize: '0.75rem', padding: '2px 6px', borderRadius: '6px' }}>
                          ⚡ {short.virality_score || 95}/100
                        </span>
                      </div>
                      <div style={{ fontSize: '0.75rem', color: '#38bdf8', marginBottom: '6px', fontWeight: 600 }}>
                        ⏱️ {short.start_time}s – {short.end_time}s ({Math.round(short.end_time - short.start_time)}s duration)
                      </div>
                      <p style={{ margin: '0 0 10px 0', fontSize: '0.8rem', color: '#94a3b8', lineHeight: 1.3 }}>
                        {short.reason}
                      </p>
                    </div>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <button
                        onClick={() => {
                          setCurrentTime(short.start_time);
                          const v = document.querySelector('video');
                          if (v) {
                            v.currentTime = short.start_time;
                            v.play().catch(() => {});
                          }
                        }}
                        style={{ flex: 1, padding: '6px 8px', background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.15)', color: '#e2e8f0', borderRadius: '6px', fontSize: '0.75rem', cursor: 'pointer', fontWeight: 600 }}
                      >
                        ✂️ Preview
                      </button>
                      <button
                        onClick={() => handleExportShort(short, idx)}
                        disabled={exportingShortIdx === idx}
                        style={{ flex: 1.4, padding: '6px 8px', background: 'linear-gradient(135deg, #6366f1, #3b82f6)', border: 'none', color: '#fff', borderRadius: '6px', fontSize: '0.75rem', cursor: 'pointer', fontWeight: 700, boxShadow: '0 2px 8px rgba(99,102,241,0.4)' }}
                      >
                        {exportingShortIdx === idx ? '🚀 Rendering...' : '🚀 Export Short'}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Export Modal */}
      {showExportModal && (
        <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.75)', zIndex: 999, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ background: '#1e293b', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '12px', width: '90%', maxWidth: '520px', padding: '24px', color: '#fff', maxHeight: '90vh', overflowY: 'auto' }}>
            <h3 style={{ margin: '0 0 16px 0', fontSize: '1.25rem' }}>🎬 Export Video</h3>
            <p style={{ color: '#94a3b8', fontSize: '0.9rem', marginBottom: '20px' }}>
              Render your video project. Choose options below.
            </p>

            {/* Trim Options */}
            <div style={{ marginBottom: '16px', padding: '16px', background: 'rgba(255,255,255,0.05)', borderRadius: '8px' }}>
              <h4 style={{ margin: '0 0 12px 0', fontSize: '1rem', color: '#e2e8f0' }}>✂️ Trim Video (Optional)</h4>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.85rem', color: '#94a3b8', marginBottom: '4px' }}>Start Time (sec)</label>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    value={trimStartTime || ''}
                    onChange={(e) => setTrimStartTime(parseFloat(e.target.value) || 0)}
                    placeholder="0"
                    style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.2)', background: '#0f172a', color: '#fff', fontSize: '0.9rem' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '0.85rem', color: '#94a3b8', marginBottom: '4px' }}>End Time (sec)</label>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    value={trimEndTime || ''}
                    onChange={(e) => setTrimEndTime(parseFloat(e.target.value) || 0)}
                    placeholder={actualDuration ? actualDuration.toFixed(1) : 'duration'}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.2)', background: '#0f172a', color: '#fff', fontSize: '0.9rem' }}
                  />
                </div>
              </div>
              <p style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '8px' }}>
                Leave empty (0) to export full video. Specify times to trim.
              </p>
            </div>

            {/* Subtitle Options */}
            <div style={{ marginBottom: '20px', padding: '16px', background: 'rgba(255,255,255,0.05)', borderRadius: '8px' }}>
              <h4 style={{ margin: '0 0 12px 0', fontSize: '1rem', color: '#e2e8f0' }}>📝 Subtitles</h4>
              <div style={{ display: 'flex', gap: '12px' }}>
                <button
                  onClick={() => setBurnSubtitles(false)}
                  style={{
                    flex: 1, padding: '10px',
                    background: !burnSubtitles ? '#3b82f6' : 'rgba(255,255,255,0.1)',
                    border: !burnSubtitles ? '2px solid #60a5fa' : '2px solid rgba(255,255,255,0.2)',
                    color: '#fff', borderRadius: '6px', cursor: 'pointer', fontSize: '0.9rem', fontWeight: 600
                  }}
                >
                  Without Subtitles
                </button>
                <button
                  onClick={() => setBurnSubtitles(true)}
                  style={{
                    flex: 1, padding: '10px',
                    background: burnSubtitles ? '#3b82f6' : 'rgba(255,255,255,0.1)',
                    border: burnSubtitles ? '2px solid #60a5fa' : '2px solid rgba(255,255,255,0.2)',
                    color: '#fff', borderRadius: '6px', cursor: 'pointer', fontSize: '0.9rem', fontWeight: 600
                  }}
                >
                  Burn Subtitles
                </button>
              </div>
            </div>

            {isExporting ? (
              <div style={{ textAlign: 'center', padding: '20px 0' }}>
                <div className="spinner" style={{ margin: '0 auto 12px auto' }}></div>
                <p>{burnSubtitles ? 'Rendering & Burning Subtitles with FFmpeg...' : 'Rendering video with FFmpeg...'}</p>
              </div>
            ) : exportResult ? (
              <div style={{ background: 'rgba(34, 197, 94, 0.1)', border: '1px solid rgba(34, 197, 94, 0.3)', padding: '16px', borderRadius: '8px', marginBottom: '20px' }}>
                <p style={{ color: '#4ade80', fontWeight: 600, margin: '0 0 12px 0' }}>✅ {exportResult.message}</p>
                <a
                  href={exportResult.url}
                  download={exportResult.filename}
                  target="_blank"
                  rel="noreferrer"
                  className="btn-primary"
                  style={{ display: 'inline-block', textDecoration: 'none', width: '100%', textAlign: 'center' }}
                >
                  ⬇️ Download Exported MP4
                </a>
              </div>
            ) : (
              <button className="btn-primary" style={{ width: '100%' }} onClick={handleExport}>
                {burnSubtitles ? '🔥 Burn Subtitles & Export Video' : '🎬 Export Video'}
              </button>
            )}

            <div style={{ marginTop: '16px', textAlign: 'right' }}>
              <button
                className="btn-secondary"
                onClick={() => { setShowExportModal(false); setExportResult(null); setTrimStartTime(0); setTrimEndTime(0); }}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="editor-layout">
        <div className="editor-main">
          <div className="video-section">
            <VideoPlayer
              video={video}
              currentTime={currentTime}
              onTimeUpdate={handleTimeUpdate}
              onDurationChange={handleDurationChange}
              clips={clips}
              selectedClipId={selectedClipId}
            />
          </div>

          <div className="timeline-section">
            <Timeline
              ref={timelineRef}
              video={video}
              currentTime={currentTime}
              onTimeUpdate={handleTimeUpdate}
              onHistoryChange={handleHistoryChange}
              clips={clips}
              setClips={setClips}
              selectedClipId={selectedClipId}
              setSelectedClipId={setSelectedClipId}
              actualDuration={actualDuration}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default Editor;
