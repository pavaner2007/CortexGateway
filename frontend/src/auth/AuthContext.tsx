/**
 * Auth Context — manages session state backed by sessionStorage.
 *
 * SECURITY rules:
 *   - API key stored in sessionStorage (cleared on tab close)
 *   - Key is NEVER logged, printed, or embedded in URLs
 *   - Context only exposes role/org metadata, not the raw key to components
 *   - Logout and 401 both clear the session completely
 */
import {
  createContext,
  useContext,
  useState,
  useCallback,
  type ReactNode,
} from 'react'
import type { Session } from '../types/auth'
import { SESSION_KEY } from '../types/auth'

interface AuthState {
  session: Session | null
  isAuthenticated: boolean
  isAdmin: boolean
  login: (session: Session) => void
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)

function readSession(): Session | null {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY)
    if (!raw) return null
    return JSON.parse(raw) as Session
  } catch {
    return null
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(readSession)

  const login = useCallback((s: Session) => {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(s))
    setSession(s)
  }, [])

  const logout = useCallback(() => {
    sessionStorage.removeItem(SESSION_KEY)
    setSession(null)
  }, [])

  return (
    <AuthContext.Provider
      value={{
        session,
        isAuthenticated: session !== null,
        isAdmin: session?.role === 'admin',
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
