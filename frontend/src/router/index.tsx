import { Routes, Route, Navigate } from 'react-router-dom'
import ProtectedRoute from '../auth/ProtectedRoute'
import Login from '../pages/Login'
import Dashboard from '../pages/Dashboard'
import Providers from '../pages/Providers'
import Teams from '../pages/Teams'
import TeamDetail from '../pages/TeamDetail'
import Budgets from '../pages/Budgets'
import Analytics from '../pages/Analytics'
import Logs from '../pages/Logs'
import ErrorBoundary from '../components/common/ErrorBoundary'

export default function AppRouter() {
  return (
    <Routes>
      {/* Public */}
      <Route path="/login" element={<Login />} />

      {/* Protected admin routes */}
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <ErrorBoundary>
              <Dashboard />
            </ErrorBoundary>
          </ProtectedRoute>
        }
      />
      <Route
        path="/providers"
        element={
          <ProtectedRoute>
            <ErrorBoundary>
              <Providers />
            </ErrorBoundary>
          </ProtectedRoute>
        }
      />
      <Route
        path="/teams"
        element={
          <ProtectedRoute>
            <ErrorBoundary>
              <Teams />
            </ErrorBoundary>
          </ProtectedRoute>
        }
      />
      <Route
        path="/teams/:teamId"
        element={
          <ProtectedRoute>
            <ErrorBoundary>
              <TeamDetail />
            </ErrorBoundary>
          </ProtectedRoute>
        }
      />
      <Route
        path="/budgets"
        element={
          <ProtectedRoute>
            <ErrorBoundary>
              <Budgets />
            </ErrorBoundary>
          </ProtectedRoute>
        }
      />
      <Route
        path="/analytics"
        element={
          <ProtectedRoute>
            <ErrorBoundary>
              <Analytics />
            </ErrorBoundary>
          </ProtectedRoute>
        }
      />
      <Route
        path="/logs"
        element={
          <ProtectedRoute>
            <ErrorBoundary>
              <Logs />
            </ErrorBoundary>
          </ProtectedRoute>
        }
      />

      {/* Redirects */}
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}
