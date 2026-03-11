import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import api from '../utils/api';

const useAuthStore = create(
  persist(
    (set, get) => ({
      // State
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      // Actions
      login: async (credentials) => {
        set({ isLoading: true, error: null });
        
        try {
          const response = await api.post('/auth/login', credentials);
          const { access_token, expires_in } = response;
          
          // For demo token, extract username from token format: "demo_token_username_timestamp"
          let user = {
            username: 'admin',
            role: 'admin'
          };
          
          // Try to parse as JWT first, fallback to demo token parsing
          try {
            const tokenPayload = JSON.parse(atob(access_token.split('.')[1]));
            user = {
              username: tokenPayload.sub,
              role: tokenPayload.role || 'admin',
            };
          } catch (e) {
            // It's a demo token, extract username
            const tokenParts = access_token.split('_');
            if (tokenParts.length >= 2) {
              user.username = tokenParts[1];
            }
          }
          
          set({
            user,
            token: access_token,
            isAuthenticated: true,
            isLoading: false,
            error: null,
          });
          
          // Set authorization header for future requests
          api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
          
          return { success: true };
        } catch (error) {
          const errorMessage = error.response?.data?.detail || 'Login failed';
          set({
            user: null,
            token: null,
            isAuthenticated: false,
            isLoading: false,
            error: errorMessage,
          });
          
          return { success: false, error: errorMessage };
        }
      },

      logout: () => {
        // Clear authorization header
        delete api.defaults.headers.common['Authorization'];
        
        set({
          user: null,
          token: null,
          isAuthenticated: false,
          isLoading: false,
          error: null,
        });
      },

      refreshToken: async () => {
        const { token } = get();
        if (!token) return false;

        try {
          // Check if token is expired
          const tokenPayload = JSON.parse(atob(token.split('.')[1]));
          const now = Date.now() / 1000;
          
          if (tokenPayload.exp > now) {
            return true; // Token is still valid
          }
          
          // Token is expired, you would typically refresh it here
          // For now, we'll just logout
          get().logout();
          return false;
        } catch (error) {
          console.error('Token validation failed:', error);
          get().logout();
          return false;
        }
      },

      clearError: () => {
        set({ error: null });
      },

      // Initialize auth state from persisted storage
      initializeAuth: () => {
        const { token, user } = get();
        if (token && user) {
          // Validate token
          get().refreshToken();
          
          // Set authorization header
          api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
        }
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        user: state.user,
        token: state.token,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);

export { useAuthStore };
