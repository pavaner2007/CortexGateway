interface EmptyStateProps {
  title: string
  description?: string
  icon?: React.ReactNode
}

export default function EmptyState({ title, description, icon }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      {icon && (
        <div className="mb-4 text-slate-600">
          {icon}
        </div>
      )}
      <p className="text-slate-400 font-medium">{title}</p>
      {description && (
        <p className="text-slate-600 text-sm mt-1">{description}</p>
      )}
    </div>
  )
}
