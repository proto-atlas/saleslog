import type { ReactNode } from 'react'

import { EmptyState } from './EmptyState'
import { ErrorState } from './ErrorState'

export type DataTableColumn<TRow> = {
  key: string
  header: string
  render: (row: TRow) => ReactNode
  sortKey?: string
}

type Props<TRow> = {
  columns: DataTableColumn<TRow>[]
  rows: TRow[]
  rowKey: (row: TRow) => string | number
  isLoading?: boolean
  errorMessage?: string | null
  onRetry?: () => void
  emptyState?: ReactNode
  sort?: string
  onSortChange?: (sort: string) => void
  onRowClick?: (row: TRow) => void
  rowActionLabel?: (row: TRow) => string
}

const SKELETON_ROWS = 5

export function DataTable<TRow>({
  columns,
  rows,
  rowKey,
  isLoading = false,
  errorMessage = null,
  onRetry,
  emptyState,
  sort,
  onSortChange,
  onRowClick,
  rowActionLabel,
}: Props<TRow>) {
  if (errorMessage !== null && onRetry !== undefined) {
    return <ErrorState message={errorMessage} onRetry={onRetry} />
  }

  if (!isLoading && rows.length === 0) {
    return <>{emptyState ?? <EmptyState title="データがありません" />}</>
  }

  const handleSort = (sortKey: string) => {
    if (onSortChange === undefined) return
    onSortChange(sort === sortKey ? `-${sortKey}` : sortKey)
  }

  const ariaSort = (sortKey: string | undefined) => {
    if (sortKey === undefined || sort === undefined) return undefined
    if (sort === sortKey) return 'ascending' as const
    if (sort === `-${sortKey}`) return 'descending' as const
    return undefined
  }

  return (
    <div className="overflow-x-auto rounded-[10px] border border-slate-200/80 bg-white shadow-[0_1px_4px_rgba(30,41,59,0.06)]">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-100">
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                aria-sort={ariaSort(column.sortKey)}
                className="bg-white px-4 py-3 text-left text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-600"
              >
                {column.sortKey !== undefined && onSortChange !== undefined ? (
                  <button
                    type="button"
                    onClick={() => handleSort(column.sortKey as string)}
                    className="inline-flex items-center gap-1 hover:text-slate-600"
                  >
                    {column.header}
                    <span aria-hidden="true" className="text-[11px]">
                      {sort === column.sortKey
                        ? '↑'
                        : sort === `-${column.sortKey}`
                          ? '↓'
                          : '↕'}
                    </span>
                  </button>
                ) : (
                  column.header
                )}
              </th>
            ))}
            {onRowClick !== undefined && (
              <th scope="col" className="sr-only">
                操作
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {isLoading
            ? Array.from({ length: SKELETON_ROWS }, (_, i) => (
                <tr key={i} className="border-t border-slate-50">
                  {columns.map((column) => (
                    <td key={column.key} className="px-4 py-3">
                      <div className="h-4 animate-pulse rounded-[4px] bg-slate-100" />
                    </td>
                  ))}
                  {onRowClick !== undefined && (
                    <td className="px-4 py-3">
                      <div className="h-4 animate-pulse rounded-[4px] bg-slate-100" />
                    </td>
                  )}
                </tr>
              ))
            : rows.map((row, index) => (
                <tr
                  key={rowKey(row)}
                  className={`border-t border-slate-50 transition-colors ${
                    index % 2 === 1 ? 'bg-slate-50/40' : 'bg-white'
                  } ${
                    onRowClick !== undefined
                      ? 'cursor-pointer hover:bg-[#F0F4FF]'
                      : ''
                  }`}
                  onClick={onRowClick === undefined ? undefined : () => onRowClick(row)}
                >
                  {columns.map((column) => (
                    <td key={column.key} className="px-4 py-3">
                      {column.render(row)}
                    </td>
                  ))}
                  {onRowClick !== undefined && (
                    <td className="px-4 py-3 text-right">
                      <button
                        type="button"
                        aria-label={rowActionLabel?.(row)}
                        onClick={(event) => {
                          event.stopPropagation()
                          onRowClick(row)
                        }}
                        className="rounded-[6px] px-2.5 py-1 text-xs font-semibold text-[#1D4ED8] hover:bg-[#EEF3FF] focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]/30"
                      >
                        開く
                      </button>
                    </td>
                  )}
                </tr>
              ))}
        </tbody>
      </table>
    </div>
  )
}
