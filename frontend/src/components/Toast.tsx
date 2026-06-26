import { useCallback, useMemo, useRef, useState, type ReactNode } from 'react'

import { ToastContext, type ToastVariant } from './toastContext'

type ToastItem = {
  id: number
  message: string
  variant: ToastVariant
}

const TOAST_DURATION_MS = 5000

const VARIANT_CLASSES: Record<ToastVariant, string> = {
  success: 'border-emerald-200 bg-emerald-50 text-emerald-900',
  error:   'border-red-200 bg-red-50 text-red-900',
}

const VARIANT_ICONS: Record<ToastVariant, string> = {
  success: '✓',
  error:   '✕',
}

const ICON_CLASSES: Record<ToastVariant, string> = {
  success: 'bg-emerald-100 text-emerald-700',
  error:   'bg-red-100 text-red-700',
}

export function ToastView({
  message,
  variant,
}: {
  message: string
  variant: ToastVariant
}) {
  return (
    <div
      role={variant === 'error' ? 'alert' : 'status'}
      className={`flex items-start gap-3 rounded-[8px] border px-4 py-3 text-sm shadow-[0_4px_12px_rgba(30,41,59,0.1)] ${VARIANT_CLASSES[variant]}`}
    >
      <span
        className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-bold ${ICON_CLASSES[variant]}`}
      >
        {VARIANT_ICONS[variant]}
      </span>
      <span className="leading-snug">{message}</span>
    </div>
  )
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const nextIdRef = useRef(1)

  const showToast = useCallback((message: string, variant: ToastVariant) => {
    const id = nextIdRef.current
    nextIdRef.current += 1
    setToasts((current) => [...current, { id, message, variant }])
    setTimeout(() => {
      setToasts((current) => current.filter((toast) => toast.id !== id))
    }, TOAST_DURATION_MS)
  }, [])

  const value = useMemo(() => ({ showToast }), [showToast])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed bottom-5 right-5 flex w-80 flex-col gap-2">
        {toasts.map((toast) => (
          <ToastView key={toast.id} message={toast.message} variant={toast.variant} />
        ))}
      </div>
    </ToastContext.Provider>
  )
}
