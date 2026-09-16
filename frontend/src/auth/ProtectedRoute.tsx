/**
 * ProtectedRoute — redirects unauthenticated users to /login.
 * Routes themselves are protected — hiding nav items is not sufficient.
 */
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from './AuthContext'
import type { ReactNode } from 'react'

interface Props {
  children: ReactNode
}

export default function ProtectedRoute({ children }: Props) {
  const { isAuthenticated } = useAuth()
  const location = useLocation()

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <>{children}</>
}
