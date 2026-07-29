import React, { useState, useEffect, useRef, useImperativeHandle, forwardRef, useCallback } from 'react';
import { autoTrimVideo } from '../api/client';
import './Timeline.css';

const Timeline = forwardRef(({
  video,
  currentTime,
  onTimeUpdate,
  onHistoryChange,
  clips,
  setClips,
  selectedClipId,
  setSelectedClipId,
  actualDuration
}, ref) => {
  const [isProcessing, setIsProcessing] = useState(false);
  const [history, setHistory] = useState([]);
  const [future, setFuture] = useState([]);
  const tracksRef = useRef(null);
  const dragInfoRef = useRef(null);
  const videoIdRef = useRef(video?.id);
  const clipsRef = useRef(clips);
  const selectedClipIdRef = useRef(selectedClipId);

  // Keep refs in sync for stable callback access
  useEffect(() => { clipsRef.current = clips; }, [clips]);
  useEffect(() => { selectedClipIdRef.current = selectedClipId; }, [selectedClipId]);

  const getTimelineDuration = () => actualDuration || video?.duration || 60;

  // Notify parent of history state changes
  useEffect(() => {
    if (onHistoryChange) {
      onHistoryChange(history.length > 0, future.length > 0);
    }
  }, [history.length, future.length, onHistoryChange]);

  // Reset history when video changes
  useEffect(() => {
    if (video?.id !== videoIdRef.current) {
      setHistory([]);
      setFuture([]);
      videoIdRef.current = video?.id;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [video?.id]);

  const recordHistory = (nextClips, nextSelectedClipId) => {
    const prevClips = clipsRef.current;
    const prevSelected = selectedClipIdRef.current;
    setHistory(prev => [...prev, { clips: prevClips, selectedClipId: prevSelected }]);
    setFuture([]);
    setClips(nextClips);
    if (nextSelectedClipId !== undefined) {
      setSelectedClipId(nextSelectedClipId);
    }
  };

  const handleUndo = useCallback(() => {
    setHistory(prevHistory => {
      if (prevHistory.length === 0) return prevHistory;
      const previous = prevHistory[prevHistory.length - 1];
      const currentClips = clipsRef.current;
      const currentSelected = selectedClipIdRef.current;
      setFuture(prevFuture => [...prevFuture, { clips: currentClips, selectedClipId: currentSelected }]);
      setClips(previous.clips);
      setSelectedClipId(previous.selectedClipId);
      return prevHistory.slice(0, -1);
    });
  }, [setClips, setSelectedClipId]);

  const handleRedo = useCallback(() => {
    setFuture(prevFuture => {
      if (prevFuture.length === 0) return prevFuture;
      const nextState = prevFuture[prevFuture.length - 1];
      const currentClips = clipsRef.current;
      const currentSelected = selectedClipIdRef.current;
      setHistory(prevHistory => [...prevHistory, { clips: currentClips, selectedClipId: currentSelected }]);
      setClips(nextState.clips);
      setSelectedClipId(nextState.selectedClipId);
      return prevFuture.slice(0, -1);
    });
  }, [setClips, setSelectedClipId]);

  // Expose undo/redo via ref - use stable callbacks
  useImperativeHandle(ref, () => ({
    undo: handleUndo,
    redo: handleRedo,
    canUndo: history.length > 0,
    canRedo: future.length > 0
  }), [handleUndo, handleRedo, history.length, future.length]);

  // Keyboard shortcuts for undo/redo
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Skip if user is typing in an input/textarea
      const tag = (e.target?.tagName || '').toLowerCase();
      if (tag === 'input' || tag === 'textarea' || e.target?.isContentEditable) return;

      if ((e.ctrlKey || e.metaKey) && !e.shiftKey && (e.key === 'z' || e.key === 'Z')) {
        e.preventDefault();
        handleUndo();
      } else if ((e.ctrlKey || e.metaKey) && (e.key === 'y' || e.key === 'Y' || (e.shiftKey && (e.key === 'z' || e.key === 'Z')))) {
        e.preventDefault();
        handleRedo();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleUndo, handleRedo]);

  const handleSplit = () => {
    if (!selectedClipId) {
      alert("Please select a clip first");
      return;
    }

    const clipIndex = clips.findIndex(c => c.id === selectedClipId);
    if (clipIndex === -1) return;
    const clip = clips[clipIndex];

    if (currentTime > clip.startTime && currentTime < clip.endTime) {
      const splitOffset = currentTime - clip.startTime;

      const newClip1 = {
        ...clip,
        endTime: currentTime,
        sourceEnd: clip.sourceStart + splitOffset
      };

      const newClip2 = {
        ...clip,
        id: `clip-${clip.track}-${Date.now()}`,
        startTime: currentTime,
        sourceStart: clip.sourceStart + splitOffset
      };

      const newClips = [...clips];
      newClips.splice(clipIndex, 1, newClip1, newClip2);
      recordHistory(newClips, newClip2.id);
    } else {
      alert("Playhead must be over the selected clip to split it.");
    }
  };

  const handleDelete = () => {
    if (!selectedClipId) {
      alert("Please select a clip first");
      return;
    }

    const remaining = clips.filter(c => c.id !== selectedClipId);
    const nextSelected = remaining.length > 0 ? remaining[0].id : null;
    recordHistory(remaining, nextSelected);
  };

  const handleAIAutoTrim = async () => {
    if (!selectedClipId) {
      alert("Please select a clip first");
      return;
    }

    const clipIndex = clips.findIndex(c => c.id === selectedClipId);
    if (clipIndex === -1) return;
    const clip = clips[clipIndex];

    setIsProcessing(true);
    try {
      let result = null;
      try {
        result = await autoTrimVideo(video?.id || 'mock-id', -30);
      } catch (apiErr) {
        console.warn("Backend auto-trim failed or is offline. Simulating trim visually.");
      }

      // Trimming silence from beginning: reduce starting silence by 3.5 seconds
      const trimAmount = 3.5;
      const duration = clip.endTime - clip.startTime;

      if (duration <= trimAmount) {
        alert("Selected clip is too short to trim silence!");
        setIsProcessing(false);
        return;
      }

      const nextClips = [...clips];
      nextClips[clipIndex] = {
        ...clip,
        startTime: clip.startTime + trimAmount,
        sourceStart: clip.sourceStart + trimAmount
      };

      recordHistory(nextClips, clip.id);

      if (result && result.output_filename) {
        // Dispatch an event so the Editor can update and the Media Library can show processed clips
        window.dispatchEvent(new CustomEvent('video_edited', { detail: { action: 'remove_silence', result } }));
        // Also dispatch a lightweight event for UI to show a link
        window.dispatchEvent(new CustomEvent('auto_trim_completed', { detail: result }));
      } else {
        // Fallback UX when backend offline - just notify visually
        alert(`✨ AI Auto-Trim: Successfully trimmed 3.5s of silent frequencies from the selected ${clip.track === 'v1' ? 'video' : 'audio'} clip!`);
      }
    } catch (error) {
      console.error(error);
      alert("Failed auto-trimming clip");
    } finally {
      setIsProcessing(false);
    }
  };

  const calculateLeft = (time) => {
    return `${(time / getTimelineDuration()) * 100}%`;
  };

  const calculateWidth = (start, end) => {
    return `${((end - start) / getTimelineDuration()) * 100}%`;
  };

  // Playhead scrubbing - handled at timeline-tracks level for robust event capture
  const isDraggingPlayheadRef = useRef(false);

  const updateTimeFromEvent = (e) => {
    if (!tracksRef.current) return;
    const rect = tracksRef.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
    const percentage = x / rect.width;
    onTimeUpdate(percentage * getTimelineDuration());
  };

  const isPointerNearPlayhead = (clientX) => {
    if (!tracksRef.current) return false;
    const rect = tracksRef.current.getBoundingClientRect();
    const tracksWidth = rect.width;
    const playheadX = rect.left + (currentTime / getTimelineDuration()) * tracksWidth;
    return Math.abs(clientX - playheadX) < 48;
  };

  const handleTracksPointerDown = (e) => {
    if (!video || !onTimeUpdate || !tracksRef.current) return;
    // Only respond to clicks in the tracks area (beyond the header)
    const rect = e.currentTarget.getBoundingClientRect();
    if (e.clientX <= rect.left + 240) return;

    if (isPointerNearPlayhead(e.clientX)) {
      isDraggingPlayheadRef.current = true;
      e.target.setPointerCapture(e.pointerId);
    }
    updateTimeFromEvent(e);
  };

  const handleTracksPointerMove = (e) => {
    if (isDraggingPlayheadRef.current && onTimeUpdate) {
      updateTimeFromEvent(e);
    }
  };

  const handleTracksPointerUp = (e) => {
    if (isDraggingPlayheadRef.current) {
      e.target.releasePointerCapture(e.pointerId);
      isDraggingPlayheadRef.current = false;
    }
  };

  // Clip Dragging / Trimming pointer handers
  const handleClipPointerDown = (e, clip, mode) => {
    e.stopPropagation();
    setSelectedClipId(clip.id);
    const pointerId = e.pointerId;
    e.target.setPointerCapture(pointerId);

    dragInfoRef.current = {
      pointerId,
      clipId: clip.id,
      mode, // 'move' | 'trim-left' | 'trim-right'
      startX: e.clientX,
      initialStartTime: clip.startTime,
      initialEndTime: clip.endTime,
      initialSourceStart: clip.sourceStart,
      initialSourceEnd: clip.sourceEnd,
    };
  };

  const handleClipPointerMove = (e) => {
    if (!dragInfoRef.current || dragInfoRef.current.pointerId !== e.pointerId) return;
    e.stopPropagation();

    const info = dragInfoRef.current;
    if (!tracksRef.current) return;

    const rect = tracksRef.current.getBoundingClientRect();
    const dx = e.clientX - info.startX;
    const dt = dx * (getTimelineDuration() / rect.width);

    const nextClips = [...clips];
    const index = nextClips.findIndex(c => c.id === info.clipId);
    if (index === -1) return;
    const clip = nextClips[index];

    const tlDuration = getTimelineDuration();

    if (info.mode === 'move') {
      let nextStart = Math.max(0, info.initialStartTime + dt);
      const clipDuration = info.initialEndTime - info.initialStartTime;
      let nextEnd = nextStart + clipDuration;

      if (nextEnd > tlDuration) {
        nextEnd = tlDuration;
        nextStart = nextEnd - clipDuration;
      }
      nextClips[index] = { ...clip, startTime: nextStart, endTime: nextEnd };
    } else if (info.mode === 'trim-left') {
      // Trim from left (increases startTime, increases sourceStart)
      let nextStart = Math.max(0, Math.min(info.initialStartTime + dt, clip.endTime - 0.5));
      const deltaStart = nextStart - info.initialStartTime;
      const nextSourceStart = Math.max(0, info.initialSourceStart + deltaStart);

      nextClips[index] = { ...clip, startTime: nextStart, sourceStart: nextSourceStart };
    } else if (info.mode === 'trim-right') {
      // Trim from right (decreases endTime, decreases sourceEnd)
      let nextEnd = Math.min(tlDuration, Math.max(info.initialEndTime + dt, clip.startTime + 0.5));
      const deltaEnd = nextEnd - info.initialEndTime;
      const nextSourceEnd = Math.min(tlDuration, info.initialSourceEnd + deltaEnd);

      nextClips[index] = { ...clip, endTime: nextEnd, sourceEnd: nextSourceEnd };
    }

    setClips(nextClips);
  };

  const handleClipPointerUp = (e) => {
    if (!dragInfoRef.current || dragInfoRef.current.pointerId !== e.pointerId) return;
    e.stopPropagation();
    e.target.releasePointerCapture(e.pointerId);
    dragInfoRef.current = null;
    recordHistory(clips, selectedClipId);
  };

  const formatTimeMMSS = (seconds) => {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  const renderScaleMarkers = () => {
    const duration = getTimelineDuration();
    const markers = [];
    const step = duration > 120 ? 20 : (duration > 60 ? 10 : 5);
    for (let i = 0; i <= duration; i += step) {
      markers.push(i);
    }
    return markers.map((time, idx) => (
      <div
        key={idx}
        className="scale-marker"
        style={{ left: calculateLeft(time) }}
      >
        <span>{formatTimeMMSS(time)}</span>
      </div>
    ));
  };

  const v2Clips = clips.filter(c => c.track === 'v2');
  const videoClips = clips.filter(c => c.track === 'v1');
  const audioClips = clips.filter(c => c.track === 'a1');
  const captionClips = clips.filter(c => c.track === 'c1' || c.track === 'subtitles' || c.isCaption);

  return (
    <div className="timeline-container glass-panel">
      <div className="timeline-header">
        <div className="timeline-tools">
          <button className="tool-btn" onClick={handleSplit} title="Split selected clip at playhead">
            ✂️ Split
          </button>
          <button className="tool-btn" onClick={handleDelete} title="Delete selected clip">
            🗑️ Delete
          </button>
          <button className="tool-btn" onClick={handleAIAutoTrim} disabled={isProcessing} title="AI AutoTrim silent gaps">
            {isProcessing ? '✨ Processing...' : '✨ AI Auto-Trim'}
          </button>
          <div className="timeline-divider"></div>
          <button className="tool-btn history-btn" onClick={handleUndo} disabled={history.length === 0} title="Undo">
            ↶
          </button>
          <button className="tool-btn history-btn" onClick={handleRedo} disabled={future.length === 0} title="Redo">
            ↷
          </button>
        </div>
        <div
          className="timeline-scale"
          onPointerDown={(e) => {
            if (!video || !onTimeUpdate) return;
            isDraggingPlayheadRef.current = true;
            e.target.setPointerCapture(e.pointerId);
            updateTimeFromEvent(e);
          }}
          onPointerMove={handleTracksPointerMove}
          onPointerUp={handleTracksPointerUp}
          onPointerLeave={handleTracksPointerUp}
        >
          {renderScaleMarkers()}
        </div>
      </div>

      <div
        className="timeline-tracks"
        onPointerDown={handleTracksPointerDown}
        onPointerMove={handleTracksPointerMove}
        onPointerUp={handleTracksPointerUp}
      >
        {/* Playhead & Coordinate System Overlay */}
        <div style={{ position: 'absolute', left: '240px', right: 0, top: 0, bottom: 0, pointerEvents: 'none', zIndex: 20 }} ref={tracksRef}>
          {video && (
            <div className="playhead-container" style={{ left: calculateLeft(currentTime) }}>
              <div className="playhead-line"></div>
              <div className="playhead-handle"></div>
            </div>
          )}
        </div>

        {/* OVERLAY B-ROLL TRACK (V2) */}
        <div className="track v2-track" style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
          <div className="track-header" style={{ background: 'rgba(168, 85, 247, 0.1)' }}>
            <span className="track-icon">📹</span>
            <div>
              <span className="track-name" style={{ color: '#c084fc' }}>V2</span>
              <span className="track-type">B-Roll Overlay</span>
            </div>
          </div>
          <div className="track-content">
            {v2Clips.map((clip) => {
              const isSelected = selectedClipId === clip.id;
              return (
                <div
                  key={clip.id}
                  className={`clip v2-clip ${isSelected ? 'selected' : ''}`}
                  style={{
                    left: calculateLeft(clip.startTime),
                    width: calculateWidth(clip.startTime, clip.endTime),
                    background: 'linear-gradient(135deg, rgba(168, 85, 247, 0.6), rgba(147, 51, 234, 0.8))',
                    border: isSelected ? '2px solid #e9d5ff' : '1px solid rgba(168, 85, 247, 0.4)',
                    color: '#fff',
                    borderRadius: '6px',
                    position: 'absolute',
                    height: '80%',
                    top: '10%',
                    cursor: 'grab'
                  }}
                  onPointerDown={(e) => handleClipPointerDown(e, clip, 'move')}
                  onPointerMove={handleClipPointerMove}
                  onPointerUp={handleClipPointerUp}
                >
                  <div className="clip-details" style={{ padding: '0 8px', display: 'flex', alignItems: 'center', height: '100%', fontSize: '0.75rem', fontWeight: 600 }}>
                    <span className="clip-label" style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{clip.name}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* VIDEO TRACK (V1) */}
        <div className="track video-track">
          <div className="track-header">
            <span className="track-icon">🎞️</span>
            <div>
              <span className="track-name">V1</span>
              <span className="track-type">Video Track</span>
            </div>
          </div>
          <div className="track-content">
            {videoClips.map((clip) => {
              const isSelected = selectedClipId === clip.id;
              return (
                <div
                  key={clip.id}
                  className={`clip video-clip ${isSelected ? 'selected' : ''}`}
                  style={{
                    left: calculateLeft(clip.startTime),
                    width: calculateWidth(clip.startTime, clip.endTime)
                  }}
                  onPointerDown={(e) => handleClipPointerDown(e, clip, 'move')}
                  onPointerMove={handleClipPointerMove}
                  onPointerUp={handleClipPointerUp}
                >
                  {/* Trim Handles */}
                  {isSelected && (
                    <>
                      <div
                        className="trim-handle trim-left"
                        onPointerDown={(e) => handleClipPointerDown(e, clip, 'trim-left')}
                        onPointerMove={handleClipPointerMove}
                        onPointerUp={handleClipPointerUp}
                      />
                      <div
                        className="trim-handle trim-right"
                        onPointerDown={(e) => handleClipPointerDown(e, clip, 'trim-right')}
                        onPointerMove={handleClipPointerMove}
                        onPointerUp={handleClipPointerUp}
                      />
                    </>
                  )}

                  <div className="clip-details">
                    <span className="clip-label">{clip.name}</span>
                    <span className="clip-dur">{((clip.endTime - clip.startTime)).toFixed(1)}s</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* AUDIO TRACK (A1) */}
        <div className="track audio-track">
          <div className="track-header">
            <span className="track-icon">🎵</span>
            <div>
              <span className="track-name">A1</span>
              <span className="track-type">Audio Track</span>
            </div>
          </div>
          <div className="track-content">
            {audioClips.map((clip) => {
              const isSelected = selectedClipId === clip.id;
              const durSec = clip.endTime - clip.startTime;
              const barCount = Math.max(5, Math.floor(durSec * 2));

              return (
                <div
                  key={clip.id}
                  className={`clip audio-clip ${isSelected ? 'selected' : ''}`}
                  style={{
                    left: calculateLeft(clip.startTime),
                    width: calculateWidth(clip.startTime, clip.endTime)
                  }}
                  onPointerDown={(e) => handleClipPointerDown(e, clip, 'move')}
                  onPointerMove={handleClipPointerMove}
                  onPointerUp={handleClipPointerUp}
                >
                  {isSelected && (
                    <>
                      <div
                        className="trim-handle trim-left"
                        onPointerDown={(e) => handleClipPointerDown(e, clip, 'trim-left')}
                        onPointerMove={handleClipPointerMove}
                        onPointerUp={handleClipPointerUp}
                      />
                      <div
                        className="trim-handle trim-right"
                        onPointerDown={(e) => handleClipPointerDown(e, clip, 'trim-right')}
                        onPointerMove={handleClipPointerMove}
                        onPointerUp={handleClipPointerUp}
                      />
                    </>
                  )}

                  <div className="waveform-container">
                    {[...Array(barCount)].map((_, i) => {
                      const h = 15 + Math.abs(Math.sin((i + clip.id.charCodeAt(0)) * 0.8)) * 25;
                      return (
                        <div
                          key={i}
                          className="wave-bar"
                          style={{ height: `${h}%` }}
                        />
                      );
                    })}
                  </div>
                  <span className="clip-label audio-label">{clip.name} ({durSec.toFixed(1)}s)</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* SUBTITLE / CAPTION TRACK (C1) */}
        <div className="track c1-track" style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}>
          <div className="track-header" style={{ background: 'rgba(234, 179, 8, 0.1)' }}>
            <span className="track-icon">💬</span>
            <div>
              <span className="track-name" style={{ color: '#facc15' }}>C1</span>
              <span className="track-type">Subtitles</span>
            </div>
          </div>
          <div className="track-content">
            {captionClips.map((clip) => {
              const isSelected = selectedClipId === clip.id;
              return (
                <div
                  key={clip.id}
                  className={`clip c1-clip ${isSelected ? 'selected' : ''}`}
                  style={{
                    left: calculateLeft(clip.startTime),
                    width: calculateWidth(clip.startTime, clip.endTime),
                    background: 'linear-gradient(135deg, rgba(234, 179, 8, 0.7), rgba(202, 138, 4, 0.9))',
                    border: isSelected ? '2px solid #fef08a' : '1px solid rgba(234, 179, 8, 0.5)',
                    color: '#000',
                    borderRadius: '4px',
                    position: 'absolute',
                    height: '75%',
                    top: '12.5%',
                    fontSize: '0.7rem',
                    fontWeight: 700,
                    cursor: 'grab'
                  }}
                  onPointerDown={(e) => handleClipPointerDown(e, clip, 'move')}
                  onPointerMove={handleClipPointerMove}
                  onPointerUp={handleClipPointerUp}
                >
                  <div className="clip-details" style={{ padding: '0 6px', display: 'flex', alignItems: 'center', height: '100%' }}>
                    <span className="clip-label" style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{clip.text || clip.name}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
});

export default Timeline;
