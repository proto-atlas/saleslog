import { createContext, useContext } from 'react'

export type ToastVariant = 'success' | 'error'

export type ToastContextValue = {
  showToast: (message: string, variant: ToastVariant) => void
}

export const ToastContext = createContext<ToastContextValue | null>(null)

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext)
  if (context === null) {
    throw new Error('useToast は ToastProvider の内側で使う')
  }
  return context
}
