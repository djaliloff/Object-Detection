import axios from 'axios';
import toast from 'react-hot-toast';

// Create axios instance
const api = axios.create({
  baseURL: process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor
api.interceptors.request.use(
  (config) => {
    // Add auth token if available
    const token = localStorage.getItem('auth-storage');
    if (token) {
      try {
        const authData = JSON.parse(token);
        if (authData.state?.token) {
          config.headers.Authorization = `Bearer ${authData.state.token}`;
        }
      } catch (error) {
        console.error('Error parsing auth token:', error);
      }
    }
    
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Throttle: show network-error toast at most once per 15 s
let _lastNetworkToast = 0;
const _showNetworkToast = () => {
  const now = Date.now();
  if (now - _lastNetworkToast > 15000) {
    _lastNetworkToast = now;
    toast.error('Network error. Please check your connection.', { id: 'network-error' });
  }
};

// Response interceptor
api.interceptors.response.use(
  (response) => {
    return response.data;
  },
  (error) => {
    // Silent URLs: background polling – never show toast
    const silentPatterns = [
      '/analytics/summary',
      '/cameras/discover',
      '/camera-groups',
      '/events',
      '/cameras',
      '/zones',
    ];
    const url = error.config?.url || '';
    const method = error.config?.method?.toLowerCase() || 'get';
    const isSilent = method === 'get' && silentPatterns.some((p) => url.includes(p));

    if (isSilent) {
      return Promise.reject(error);
    }

    if (error.response) {
      const status = error.response.status;
      const message = error.response.data?.detail || error.response.data?.message || 'An error occurred';

      switch (status) {
        case 401:
          localStorage.removeItem('auth-storage');
          window.location.href = '/login';
          toast.error('Session expired. Please login again.');
          break;
        case 403:
          toast.error('You do not have permission to perform this action.');
          break;
        case 404:
          // Silently ignore 404 for background requests
          break;
        case 422:
          if (error.response.data?.detail && Array.isArray(error.response.data.detail)) {
            error.response.data.detail.forEach((err) => {
              toast.error(`${err.loc?.join('.')} ${err.msg}`);
            });
          } else {
            toast.error(message);
          }
          break;
        case 500:
          // Silently ignore 500 for background polling
          break;
        default:
          toast.error(message);
      }
    } else if (error.request) {
      // Network error – throttled
      _showNetworkToast();
    } else {
      toast.error('An unexpected error occurred.');
    }

    return Promise.reject(error);
  }
);

// API service functions
export const authAPI = {
  login: (credentials) => api.post('/auth/login', credentials),
};

export const camerasAPI = {
  getCameras: () => api.get('/cameras'),
  getCamera: (id) => api.get(`/cameras/${id}`),
  createCamera: (data) => api.post('/cameras', data),
  updateCamera: (id, data) => api.put(`/cameras/${id}`, data),
  deleteCamera: (id) => api.delete(`/cameras/${id}`),
  getCameraHealth: (id) => api.get(`/cameras/${id}/health`),
  discoverCameras: () => api.post('/cameras/discover'),
  uploadVideo: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/cameras/upload-video', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },
};

export const eventsAPI = {
  getEvents: (params = {}) => api.get('/events', { params }),
  updateEventStatus: (id, status) => api.put(`/events/${id}/status`, { status }),
};

export const zonesAPI = {
  getZones: (cameraId) => api.get('/zones', { params: { camera_id: cameraId } }),
  createZone: (data) => api.post('/zones', data),
  updateZone: (id, data) => api.put(`/zones/${id}`, data),
  deleteZone: (id) => api.delete(`/zones/${id}`),
};

export const analyticsAPI = {
  getSummary: () => api.get('/analytics/summary'),
};

export const usersAPI = {
  getUsers: () => api.get('/users'),
  createUser: (data) => api.post('/users', data),
  updateUser: (id, data) => api.put(`/users/${id}`, data),
  deleteUser: (id) => api.delete(`/users/${id}`),
};

export const cameraGroupsAPI = {
  getCameraGroups: () => api.get('/camera-groups'),
  createCameraGroup: (data) => api.post('/camera-groups', data),
  updateCameraGroup: (id, data) => api.put(`/camera-groups/${id}`, data),
  deleteCameraGroup: (id) => api.delete(`/camera-groups/${id}`),
};

export default api;
