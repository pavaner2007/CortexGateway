import { Component, type ReactNode, type ErrorInfo } from 'react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError(): State {
    return { hasError: true }
  }

  componentDidCatch(_error: Error, _info: ErrorInfo) {
    // Do NOT log error to console — may contain sensitive request context
    // In production, send to an error tracking service (not yet implemented)
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback ?? (
        <div className="flex flex-col items-center justify-center min-h-screen text-center p-8">
          <div className="w-16 h-16 rounded-2xl bg-rose-500/10 flex items-center justify-center mb-6">
            <svg className="w-8 h-8 text-rose-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v4m0 4h.01M10.293 3.293a1 1 0 011.414 0l8 8a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-8-8a1 1 0 010-1.414l8-8z" />
            </svg>
          </div>
          <h1 className="text-xl font-semibold text-slate-200 mb-2">Something went wrong</h1>
          <p className="text-slate-500 text-sm mb-6 max-w-sm">
            An unexpected error occurred. Your session data is intact.
          </p>
          <div className="flex gap-3">
            <button
              onClick={() => this.setState({ hasError: false })}
              className="px-4 py-2 text-sm font-medium bg-brand-500/20 text-brand-400 border border-brand-500/30 rounded-lg hover:bg-brand-500/30 transition-colors"
            >
              Try again
            </button>
            <a
              href="/dashboard"
              className="px-4 py-2 text-sm font-medium text-slate-400 border border-white/10 rounded-lg hover:bg-white/5 transition-colors"
            >
              Return to Dashboard
            </a>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
