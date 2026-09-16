export default function Spinner({ size = 'md' }: { size?: 'sm' | 'md' | 'lg' }) {
  const s = { sm: 'w-4 h-4', md: 'w-6 h-6', lg: 'w-10 h-10' }[size]
  return (
    <div
      role="status"
      aria-label="Loading"
      className={`${s} border-2 border-brand-500/30 border-t-brand-500 rounded-full animate-spin`}
    />
  )
}
