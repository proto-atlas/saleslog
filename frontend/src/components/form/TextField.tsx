import { useId, type ComponentPropsWithRef } from 'react'

type Props = ComponentPropsWithRef<'input'> & {
  label: string
  error?: string
}

export function TextField({ label, error, className = '', ...inputProps }: Props) {
  const inputId = useId()
  const errorId = useId()
  const hasError = error !== undefined

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={inputId} className="text-[13px] font-medium text-slate-500">
        {label}
      </label>
      <input
        id={inputId}
        aria-invalid={hasError || undefined}
        aria-describedby={hasError ? errorId : undefined}
        className={`rounded-[8px] border-[1.5px] px-3 py-2 text-sm text-slate-800 transition-colors placeholder:text-slate-600 focus:border-[#1D4ED8] focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]/20 ${
          hasError ? 'border-red-400 bg-red-50/30' : 'border-slate-200 bg-white'
        } ${className}`}
        {...inputProps}
      />
      {hasError && (
        <p id={errorId} className="text-xs text-red-600">
          {error}
        </p>
      )}
    </div>
  )
}
