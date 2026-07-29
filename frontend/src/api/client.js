import axios from 'axios';

const API_BASE_URL = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_BASE_URL)
  ? import.meta.env.VITE_API_BASE_URL
  : 'http://127.0.0.1:8000/api/v1';

const API_SERVER_ORIGIN = API_BASE_URL.replace('/api/v1', '').replace(/\/+$/, '');

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ─── Token helpers ────────────────────────────────────────────────────────────
export const setToken = (token) => {
  if (token) {
    localStorage.setItem('auth_token', token);
  } else {
    localStorage.removeItem('auth_token');
  }
};

export const getToken = () => localStorage.getItem('auth_token');

export const setRefreshToken = (token) => {
  if (token) {
    localStorage.setItem('refresh_token', token);
  } else {
    localStorage.removeItem('refresh_token');
  }
};

export const getRefreshToken = () => localStorage.getItem('refresh_token');

// ─── Auth ─────────────────────────────────────────────────────────────────────
export const loginUser = async (email, password) => {
  const params = new URLSearchParams();
  params.append('username', email);
  params.append('password', password);
  
  const response = await apiClient.post('/auth/login', params, {
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
  });

  if (response.data && response.data.access_token) {
    setToken(response.data.access_token);
    if (response.data.refresh_token) {
      setRefreshToken(response.data.refresh_token);
    }
    return true;
  }
  return false;
};

export const registerUser = async (email, password, fullName) => {
  const response = await apiClient.post('/auth/register', {
    email,
    password,
    full_name: fullName,
  });
  return response.data;
};

export const getServerOrigin = () => API_SERVER_ORIGIN;

export const logoutUser = () => {
  setToken(null);
  setRefreshToken(null);
};

export const loginWithGoogle = async (credential) => {
  const response = await apiClient.post('/auth/google', { token: credential });
  if (response.data && response.data.access_token) {
    setToken(response.data.access_token);
    if (response.data.refresh_token) {
      setRefreshToken(response.data.refresh_token);
    }
    return true;
  }
  return false;
};

// ─── Refresh token logic ─────────────────────────────────────────────────────
const refreshAccessToken = async () => {
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    return null;
  }
  try {
    const response = await apiClient.post('/auth/refresh', { refresh_token: refreshToken });
    if (response.data && response.data.access_token) {
      setToken(response.data.access_token);
      if (response.data.refresh_token) {
        setRefreshToken(response.data.refresh_token);
      }
      return response.data.access_token;
    }
  } catch (error) {
    console.error('Token refresh failed:', error);
    logoutUser();
    return null;
  }
  return null;
};

// ─── Request interceptor – attach token ───────────────────────────────────────
apiClient.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ─── Response interceptor – handle 401 ───────────────────────────────────────
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (error.response && error.response.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      try {
        const newToken = await refreshAccessToken();
        if (newToken) {
          originalRequest.headers.Authorization = `Bearer ${newToken}`;
          return apiClient(originalRequest);
        }
      } catch (refreshError) {
        logoutUser();
        window.dispatchEvent(new Event('auth_error'));
      }
    }
    return Promise.reject(error);
  }
);

// ─── Mapping Helpers ──────────────────────────────────────────────────────────
export const getVideoStreamUrl = (filename) => {
  if (!filename) return '';
  if (filename.startsWith('http://') || filename.startsWith('https://') || filename.startsWith('blob:')) {
    return filename;
  }
  return `${API_SERVER_ORIGIN}/uploads/${filename}`;
};

const mapProject = (p) => {
  if (!p) return null;
  return {
    ...p,
    title: p.name || p.title || 'Untitled Project',
  };
};

const mapVideo = (v) => {
  if (!v) return null;
  return {
    ...v,
    filename: v.original_filename || v.filename,
    original_filename: v.original_filename || v.filename,
    size: v.file_size || v.size,
    file_size: v.file_size || v.size,
    url: getVideoStreamUrl(v.stored_filename),
  };
};

// ─── Projects ─────────────────────────────────────────────────────────────────
export const getProjects = async () => {
  const response = await apiClient.get('/projects/');
  const list = response.data.projects || response.data || [];
  return Array.isArray(list) ? list.map(mapProject) : [];
};

export const getProject = async (projectId) => {
  const response = await apiClient.get(`/projects/${projectId}`);
  return mapProject(response.data);
};

export const createProject = async (title) => {
  const response = await apiClient.post('/projects/', { name: title });
  return mapProject(response.data);
};

export const deleteProject = async (projectId) => {
  await apiClient.delete(`/projects/${projectId}`);
};

// ─── Videos ───────────────────────────────────────────────────────────────────
export const uploadVideo = async (file, projectId = null) => {
  const formData = new FormData();
  formData.append('file', file);
  if (projectId) {
    formData.append('project_id', projectId);
  }
  const response = await apiClient.post('/videos/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    timeout: 1200000,
  });
  return mapVideo(response.data);
};

export const getVideos = async (projectId = null) => {
  const response = await apiClient.get('/videos/');
  const list = response.data.videos || response.data || [];
  const mapped = Array.isArray(list) ? list.map(mapVideo) : [];
  return projectId
    ? mapped.filter((v) => String(v.project_id) === String(projectId))
    : mapped;
};

export const deleteVideo = async (videoId) => {
  await apiClient.delete(`/videos/${videoId}`);
};

export const updateVideo = async (videoId, data) => {
  const response = await apiClient.put(`/videos/${videoId}`, data);
  return mapVideo(response.data);
};

export const renameVideo = async (videoId, newFilename) => {
  const response = await apiClient.put(`/videos/${videoId}/rename`, {
    original_filename: newFilename
  });
  return mapVideo(response.data);
};

export const getOutputs = async () => {
  const response = await apiClient.get('/videos/outputs/all');
  return response.data.outputs || [];
};

// ─── AI ───────────────────────────────────────────────────────────────────────
export const analyzeVideo = async (videoId) => {
  const response = await apiClient.post('/ai/analyze', { video_id: videoId });
  return response.data;
};

export const getRetentionPlan = async (videoId) => {
  const response = await apiClient.post('/ai/retention-plan', { video_id: videoId });
  return response.data;
};

export const chatWithAI = async (message, videoId = null, sessionId = null) => {
  const response = await apiClient.post('/ai/chat', {
    message,
    video_id: videoId,
    session_id: sessionId,
  });
  return response.data;
};

// ─── Processing ───────────────────────────────────────────────────────────────
export const trimVideo = async (videoId, startTime, endTime) => {
  const response = await apiClient.post('/processing/trim', {
    video_id: videoId,
    start_time: startTime,
    end_time: endTime,
  });
  return response.data;
};

export const autoTrimVideo = async (videoId, startTime = null, endTime = null, thresholdDb = -30) => {
  const payload = {
    video_id: videoId,
    threshold_db: thresholdDb,
  };
  
  // If startTime and endTime are provided, use manual trim
  if (startTime !== null && endTime !== null) {
    payload.start_time = startTime;
    payload.end_time = endTime;
  }
  
  const response = await apiClient.post('/processing/auto-trim', payload, { timeout: 1200000 });
  return response.data;
};

export const burnSubtitles = async (videoId, subtitleText, outputFilename = null) => {
  const response = await apiClient.post('/processing/burn-subtitles', {
    video_id: videoId,
    subtitle_text: subtitleText,
    output_filename: outputFilename,
  }, { timeout: 600000 });
  return response.data;
};

export const exportViralShort = async (videoId, startTime, endTime, hookTitle = null) => {
  const response = await apiClient.post('/processing/export-short', {
    video_id: videoId,
    start_time: startTime,
    end_time: endTime,
    hook_title: hookTitle,
  }, { timeout: 600000 });
  return response.data;
};

export const exportTimeline = async (videoId, operations = [], outputSettings = {}, timeout = 1200000) => {
  const payload = {
    video_id: videoId,
    operations,
    output_settings: outputSettings
  };
  const response = await apiClient.post('/processing/render', payload, { timeout });
  return response.data;
};

export const getVideoTranscript = async (videoId) => {
  try {
    const response = await apiClient.get(`/transcripts/video/${videoId}`);
    const data = response.data;
    return Array.isArray(data) ? data[0] : data;
  } catch (error) {
    console.error("Failed to fetch transcript:", error);
    return null;
  }
};

// ─── User Profile ─────────────────────────────────────────────────────────────
export const getUserProfile = async () => {
  const response = await apiClient.get('/users/me');
  return response.data;
};

// ─── Settings ─────────────────────────────────────────────────────────────────
export const saveAIConfig = async (geminiApiKey, groqApiKey) => {
  const response = await apiClient.post('/settings/ai-config', {
    gemini_api_key: geminiApiKey,
    groq_api_key: groqApiKey,
  });
  return response.data;
};

export const getAIStatus = async () => {
  const response = await apiClient.get('/settings/ai-status');
  return response.data;
};

// ─── Chat History ─────────────────────────────────────────────────────────────
export const getChatSessions = async () => {
  const response = await apiClient.get('/chat_history/sessions');
  return response.data;
};

export const getChatHistory = async (sessionId) => {
  const response = await apiClient.get(`/chat_history/sessions/${sessionId}`);
  return response.data;
};

export const createNewChat = async (title, videoId = null) => {
  const response = await apiClient.post('/chat_history/sessions', {
    title,
    video_id: videoId,
  });
  return response.data;
};

export const sendChatMessage = async (sessionId, message, videoId = null) => {
  const response = await apiClient.post(`/chats/${sessionId}/message`, {
    message,
    video_id: videoId,
  });
  return response.data;
};

export default apiClient;
