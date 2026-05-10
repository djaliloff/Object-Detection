import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'react-hot-toast';

// Layout components
import Layout from './components/Layout';
import AuthLayout from './components/AuthLayout';

// Page components
import Dashboard from './pages/Dashboard';
import Surveillance from './pages/Surveillance';
import CameraConfiguration from './pages/CameraConfiguration';
import Events from './pages/Events';
import Analytics from './pages/Analytics';
import Settings from './pages/Settings';
import Login from './pages/Login';

// Hooks and stores
import { useAuthStore } from './stores/authStore';
import ProtectedRoute from './components/ProtectedRoute';

// Styles
import './index.css';
import './App.css';

// Create a client for React Query
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 5 * 60 * 1000, // 5 minutes
    },
  },
});

function App() {
  const { isAuthenticated } = useAuthStore();

  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <div className="App">
          <Toaster
            position="top-right"
            toastOptions={{
              duration: 4000,
              style: {
                background: '#363636',
                color: '#fff',
              },
              success: {
                duration: 3000,
                iconTheme: {
                  primary: '#4ade80',
                  secondary: '#fff',
                },
              },
              error: {
                duration: 5000,
                iconTheme: {
                  primary: '#ef4444',
                  secondary: '#fff',
                },
              },
            }}
          />

          <Routes>
            {/* Public routes */}
            <Route
              path="/login"
              element={
                isAuthenticated ? (
                  <Navigate to="/dashboard" replace />
                ) : (
                  <AuthLayout>
                    <Login />
                  </AuthLayout>
                )
              }
            />

            {/* Protected routes */}
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <Layout />
                </ProtectedRoute>
              }
            >
              <Route index element={<Navigate to="/dashboard" replace />} />
              <Route path="dashboard" element={<Dashboard />} />
              <Route path="surveillance" element={<Surveillance />} />
              <Route path="cameras" element={<CameraConfiguration />} />
              <Route path="events" element={<Events />} />
              <Route path="analytics" element={<Analytics />} />
              <Route path="settings" element={<Settings />} />
            </Route>

            {/* Catch all route */}
            <Route
              path="*"
              element={
                <Navigate to={isAuthenticated ? "/dashboard" : "/login"} replace />
              }
            />
          </Routes>
        </div>
      </Router>
    </QueryClientProvider>
  );
}

export default App;
