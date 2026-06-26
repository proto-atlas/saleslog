import { useEffect, useId, useRef, type ReactNode } from 'react'

type Props = {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
}

export function Dialog({ open, onClose, title, children }: Props) {
  const ref = useRef<HTMLDialogElement>(null)
  const titleId = useId()

  useEffect(() => {
    const dialog = ref.current
    if (dialog === null) return
    if (open && !dialog.open) {
      dialog.showModal()
    } else if (!open && dialog.open) {
      dialog.close()
    }
  }, [open])

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      aria-labelledby={titleId}
      className="m-auto w-full max-w-md rounded-[12px] p-7 shadow-[0_8px_32px_rgba(30,41,59,0.14)] backdrop:bg-slate-900/40"
    >
      <h2 id={titleId} className="mb-5 text-lg font-bold tracking-[-0.01em] text-slate-800">
        {title}
      </h2>
      {children}
    </dialog>
  )
}
