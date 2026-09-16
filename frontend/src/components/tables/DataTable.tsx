import type { ReactNode } from 'react'

interface Column<T> {
  key: string
  label: string
  render?: (row: T) => ReactNode
  className?: string
}

interface DataTableProps<T> {
  columns: Column<T>[]
  rows: T[]
  keyFn: (row: T) => string
  onRowClick?: (row: T) => void
  emptyMessage?: string
}

export default function DataTable<T>({
  columns,
  rows,
  keyFn,
  onRowClick,
  emptyMessage = 'No data',
}: DataTableProps<T>) {
  if (rows.length === 0) {
    return (
      <div className="py-12 text-center text-slate-500 text-sm">{emptyMessage}</div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-white/5">
            {columns.map(col => (
              <th
                key={col.key}
                className={`px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider ${col.className ?? ''}`}
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-white/5">
          {rows.map(row => (
            <tr
              key={keyFn(row)}
              onClick={() => onRowClick?.(row)}
              className={`${onRowClick ? 'cursor-pointer hover:bg-white/3' : ''} transition-colors`}
            >
              {columns.map(col => (
                <td key={col.key} className={`px-4 py-3 text-slate-300 ${col.className ?? ''}`}>
                  {col.render ? col.render(row) : String((row as Record<string, unknown>)[col.key] ?? '—')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
