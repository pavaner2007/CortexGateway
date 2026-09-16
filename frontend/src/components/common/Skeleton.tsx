interface SkeletonProps {
  className?: string
  rows?: number
}

export function Skeleton({ className = '' }: { className?: string }) {
  return (
    <div
      className={`bg-white/5 rounded-lg animate-pulse ${className}`}
      aria-hidden="true"
    />
  )
}

export function SkeletonCard() {
  return (
    <div className="glass-card p-6 space-y-3">
      <Skeleton className="h-4 w-1/3" />
      <Skeleton className="h-8 w-1/2" />
      <Skeleton className="h-3 w-2/3" />
    </div>
  )
}

export function SkeletonTable({ rows = 5 }: SkeletonProps) {
  return (
    <div className="space-y-2" aria-label="Loading table">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-12 w-full rounded-xl" />
      ))}
    </div>
  )
}
