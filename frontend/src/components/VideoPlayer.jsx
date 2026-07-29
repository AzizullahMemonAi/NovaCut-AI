import React, { useRef, useState, useEffect, useMemo } from 'react';
import { getVideoStreamUrl, getServerOrigin } from '../api/client';
import './VideoPlayer.css';

const VideoPlayer = ({ video, currentTime, onTimeUpdate, onDurationChange, clips = [], selectedClipId }) => {
  const videoRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [duration, setDuration] = useState(0);
  const [zoomLevel, setZoomLevel] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [buffered, setBuffered] = useState(0);
  
  const [activeSubtitle, setActiveSubtitle] = useState('');
  const activeChunkIdRef = useRef(null);
  const isUserSeekingRef = useRef(false);
  const lastVideoUrlRef = useRef(null);

  const currentTimeRef = useRef(currentTime);
  useEffect(() => {
    currentTimeRef.current = currentTime;
  }, [currentTime]);

  const onTimeUpdateRef = useRef(onTimeUpdate);
  useEffect(() => {
    onTimeUpdateRef.current = onTimeUpdate;
  }, [onTimeUpdate]);

  const getDuration = () => video?.duration || duration || 60;

  // Subtitle sync loop using activeChunkIdRef to eliminate DOM thrashing & state queue lag
  useEffect(() => {
    let syncAnimationFrameId;

    const syncSubtitles = () => {
      const curTime = (videoRef.current && !videoRef.current.paused) ? videoRef.current.currentTime : currentTimeRef.current;
      const subtitleChunks = clips.filter((c) => c.track === 'c1' || c.track === 'subtitles' || c.isCaption);

      if (subtitleChunks.length > 0) {
        const matchingIndex = subtitleChunks.findIndex(
          (chunk) => curTime >= chunk.startTime && curTime <= chunk.endTime
        );

        if (matchingIndex !== activeChunkIdRef.current) {
          activeChunkIdRef.current = matchingIndex;

          if (matchingIndex !== -1) {
            const chunk = subtitleChunks[matchingIndex];
            const cleanText = (chunk.text || chunk.name || '').replace(/^💬\s*/, '');
            setActiveSubtitle(cleanText);
          } else {
            setActiveSubtitle('');
          }
        }
      } else {
        if (activeChunkIdRef.current !== null) {
          activeChunkIdRef.current = null;
          setActiveSubtitle('');
        }
      }

      syncAnimationFrameId = requestAnimationFrame(syncSubtitles);
    };

    syncAnimationFrameId = requestAnimationFrame(syncSubtitles);

    return () => {
      if (syncAnimationFrameId) {
        cancelAnimationFrame(syncAnimationFrameId);
      }
    };
  }, [clips]);

  // Find active video and audio clips at the current timeline playhead position
  const activeVideoClip = clips.find(
    (c) => c.track === 'v1' && currentTime >= c.startTime && currentTime <= c.endTime
  );

  const activeAudioClip = clips.find(
    (c) => c.track === 'a1' && currentTime >= c.startTime && currentTime <= c.endTime
  );

  // Sync HTML5 media element time and state with timeline currentTime
  useEffect(() => {
    if (!videoRef.current) return;

    const totalDuration = getDuration();
    if (currentTime >= totalDuration) {
      setIsPlaying(false);
      if (!videoRef.current.paused) {
        videoRef.current.pause();
      }
      return;
    }

    const targetTime = activeVideoClip
      ? (currentTime - activeVideoClip.startTime) + activeVideoClip.sourceStart
      : currentTime;

    // Seek only when divergence is significant (e.g. after user scrubbing)
    if (Math.abs(videoRef.current.currentTime - targetTime) > 0.5) {
      videoRef.current.currentTime = targetTime;
    }

    videoRef.current.muted = !activeAudioClip;
  }, [currentTime, isPlaying, activeVideoClip, activeAudioClip, video]);

  // Use the video element's native timeupdate event to drive the playhead position
  const handleTimeUpdate = () => {
    if (!videoRef.current) return;
    const totalDuration = getDuration();
    const rawTime = videoRef.current.currentTime;

    // Convert video time to timeline time (reverse of clip-aware mapping)
    const activeClip = clips.find(
      (c) => c.track === 'v1' && rawTime >= c.sourceStart && rawTime <= c.sourceEnd
    );

    let timelineTime;
    if (activeClip) {
      timelineTime = activeClip.startTime + (rawTime - activeClip.sourceStart);
    } else {
      timelineTime = rawTime;
    }

    if (timelineTime >= totalDuration) {
      onTimeUpdateRef.current(totalDuration);
      setIsPlaying(false);
    } else {
      onTimeUpdateRef.current(timelineTime);
    }
  };

  const handleVideoPlay = () => {
    setIsPlaying(true);
  };

  const handleVideoPause = () => {
    setIsPlaying(false);
  };

  const handleVideoEnded = () => {
    setIsPlaying(false);
    onTimeUpdateRef.current(getDuration());
  };

  const handlePlayPause = () => {
    if (!videoRef.current) return;
    if (videoRef.current.paused) {
      setIsPlaying(true);
      videoRef.current.play().catch(() => { });
    } else {
      setIsPlaying(false);
      videoRef.current.pause();
    }
  };

  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      const actualDuration = videoRef.current.duration;
      setDuration(actualDuration);
      if (onDurationChange && actualDuration > 0) {
        onDurationChange(actualDuration);
      }
    }
  };

  const toggleFullscreen = () => {
    if (videoRef.current) {
      if (videoRef.current.requestFullscreen) {
        videoRef.current.requestFullscreen();
      } else if (videoRef.current.webkitRequestFullscreen) {
        videoRef.current.webkitRequestFullscreen();
      } else if (videoRef.current.msRequestFullscreen) {
        videoRef.current.msRequestFullscreen();
      }
    }
  };

  const formatTime = (seconds) => {
    if (isNaN(seconds)) return "00:00:00";
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  if (!video) {
    return (
      <div className="video-player-container glass-panel">
        <div className="video-viewport">
          <div className="video-placeholder">
            <span style={{ color: 'var(--text-muted)' }}>Select or upload a video</span>
          </div>
        </div>
      </div>
    );
  }

  // Memoize video URL to prevent unnecessary re-renders
  const videoUrl = useMemo(() => {
    if (!video) return '';
    if (video.output_filename) {
      return `${getServerOrigin()}/outputs/${video.output_filename}`;
    }
    if (video.stored_filename?.startsWith('blob:')) {
      return video.stored_filename;
    }
    if (video.stored_filename) {
      return getVideoStreamUrl(video.stored_filename);
    }
    return '';
  }, [video?.stored_filename, video?.output_filename]);

  // Only update video source when URL actually changes
  useEffect(() => {
    if (videoUrl && videoUrl !== lastVideoUrlRef.current && videoRef.current) {
      lastVideoUrlRef.current = videoUrl;
      videoRef.current.load();
    }
  }, [videoUrl]);

  const isVideoVisible = !!activeVideoClip;

  const activeV2Clip = clips.find(
    (c) => c.track === 'v2' && currentTime >= c.startTime && currentTime <= c.endTime
  );

  const activeZoomClip = clips.find(
    (c) => c.type === 'zoom_in' && currentTime >= c.startTime && currentTime <= c.endTime
  );

  const currentZoomScale = activeZoomClip ? (activeZoomClip.scale || 1.25) * zoomLevel : zoomLevel;

  const activeCaptionClip = clips.find(
    (c) => (c.track === 'c1' || c.track === 'subtitles' || c.isCaption) && currentTime >= c.startTime && currentTime <= c.endTime
  );

  const displaySubtitle = activeSubtitle || (activeCaptionClip ? (activeCaptionClip.text || activeCaptionClip.name || '').replace(/^💬\s*/, '') : '');

  return (
    <div className="video-player-container glass-panel">
      <div className="video-viewport" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', backgroundColor: '#000', position: 'relative' }}>

        {/* Primary Video Track V1 */}
        {!video.mime_type?.startsWith('image/') && !video.mime_type?.startsWith('text/') && video.mime_type !== 'application/pdf' && (
          <video
            ref={videoRef}
            src={videoUrl}
            className="active-video"
            style={{
              transform: `scale(${currentZoomScale})`,
              transition: activeZoomClip ? 'none' : 'transform 0.2s ease, opacity 0.15s ease',
              opacity: isVideoVisible ? 1 : 0,
              width: '100%',
              height: '100%',
              objectFit: 'contain'
            }}
            onLoadedMetadata={handleLoadedMetadata}
            onTimeUpdate={handleTimeUpdate}
            onPlay={handleVideoPlay}
            onPause={handleVideoPause}
            onEnded={handleVideoEnded}
            onClick={handlePlayPause}
            onWaiting={() => setIsLoading(true)}
            onCanPlay={() => setIsLoading(false)}
            onError={(e) => setError('Failed to load video')}
            onSeeked={() => setIsLoading(false)}
            preload="metadata"
          />
        )}

        {/* Track V2 - AI B-Roll Visual Overlay Viewport */}
        {activeV2Clip && (activeV2Clip.video_url || activeV2Clip.url) && (
          <video
            src={activeV2Clip.video_url || activeV2Clip.url}
            autoPlay
            loop
            muted
            playsInline
            volume={0}
            style={{
              position: 'absolute',
              inset: 0,
              width: '100%',
              height: '100%',
              objectFit: 'cover',
              zIndex: 20,
              pointerEvents: 'none',
              borderRadius: '8px',
              transform: `scale(${currentZoomScale})`,
              transition: activeZoomClip ? 'none' : 'transform 0.2s ease'
            }}
          />
        )}

        {/* If in video gap, show overlay */}
        {!isVideoVisible && !video.mime_type?.startsWith('image/') && (
          <div className="video-gap-overlay" style={{ position: 'absolute', color: 'var(--color-text-muted)', fontSize: 'var(--font-sm)', pointerEvents: 'none' }}>
            ⬛ Video Gap (Black Screen)
          </div>
        )}

        {video.mime_type?.startsWith('image/') && (
          <img
            src={videoUrl}
            className="active-video"
            style={{ transform: `scale(${zoomLevel})`, maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
            alt={video.original_filename}
          />
        )}

        {/* Subtitle / Caption Overlay */}
        {displaySubtitle && (
          <div className="subtitle-overlay">
            {displaySubtitle}
          </div>
        )}

        {/* Zoom Controls Overlay */}
        {(!video.mime_type?.startsWith('audio/') && !video.mime_type?.startsWith('text/') && video.mime_type !== 'application/pdf') && (
          <div className="zoom-controls">
            <button className="zoom-btn" onClick={() => setZoomLevel(prev => Math.min(prev + 0.25, 3))}>+</button>
            <span className="zoom-level">{Math.round(zoomLevel * 100)}%</span>
            <button className="zoom-btn" onClick={() => setZoomLevel(prev => Math.max(prev - 0.25, 0.25))}>-</button>
          </div>
        )}
      </div>

      {/* Player Controls */}
      {(!video.mime_type?.startsWith('image/') && !video.mime_type?.startsWith('text/') && video.mime_type !== 'application/pdf') && (
        <div className="player-controls-wrapper">
          <div
            className="player-tracker"
            onPointerDown={(e) => {
              const rect = e.currentTarget.getBoundingClientRect();
              const dur = getDuration();
              const update = (eMove) => {
                const x = Math.max(0, Math.min(eMove.clientX - rect.left, rect.width));
                const pct = x / rect.width;
                onTimeUpdate(pct * dur);
              };
              update(e);
              const up = () => {
                window.removeEventListener('pointermove', update);
                window.removeEventListener('pointerup', up);
              };
              window.addEventListener('pointermove', update);
              window.addEventListener('pointerup', up);
            }}
          >
            <div className="tracker-fill" style={{ width: `${(currentTime / getDuration()) * 100}%` }}></div>
            <div className="tracker-thumb" style={{ left: `${(currentTime / getDuration()) * 100}%` }}></div>
          </div>

          <div className="player-controls">
            <div className="control-group center">
              <button className="control-btn" onClick={() => onTimeUpdate(Math.max(0, currentTime - 5))}>⏮</button>
              <button className="control-btn play-btn" onClick={handlePlayPause}>
                {isPlaying ? '⏸' : '▶'}
              </button>
              <button className="control-btn" onClick={() => onTimeUpdate(Math.min(getDuration(), currentTime + 5))}>⏭</button>
            </div>

            <div className="control-group right">
              <div className="time-display">
                <span>{formatTime(currentTime)}</span> / <span>{formatTime(getDuration())}</span>
              </div>
              <button className="control-btn active" style={{ marginLeft: 8 }}>HD</button>
              <button className="control-btn" onClick={toggleFullscreen}>⛶</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default VideoPlayer;
