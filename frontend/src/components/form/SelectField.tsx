import { useId, type ComponentPropsWithRef, type ReactNode } from 'react'

type Props = ComponentPropsWithRef<'select'> & {
  label: string
  error?: string
  children: ReactNode
}

export function SelectField({
  label,
  error,
  className = '',
  children,
  ...selectProps
}: Props) {
  const selectId = useId()
  const errorId = useId()
  const hasError = error !== undefined

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={selectId} className="text-[13px] font-medium text-slate-500">
        {label}
      </label>
      <select
        id={selectId}
        aria-invalid={hasError || undefined}
        aria-describedby={hasError ? errorId : undefined}
        className={`rounded-[8px] border-[1.5px] bg-white px-3 py-2 text-sm text-slate-800 transition-colors focus:border-[#1D4ED8] focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]/20 ${
          hasError ? 'border-red-400' : 'border-slate-200'
        } ${className}`}
        {...selectProps}
      >
        {children}
      </select>
      {hasError && (
        <p id={errorId} className="text-xs text-red-600">
          {error}
        </p>
      )}
    </div>
  )
}
