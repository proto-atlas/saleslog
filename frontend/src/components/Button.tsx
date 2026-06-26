import type { ComponentPropsWithRef } from 'react'

type Variant = 'primary' | 'secondary' | 'danger'

const VARIANT_CLASSES: Record<Variant, string> = {
  primary:
    'bg-[#1D4ED8] text-white hover:bg-[#1E40AF] disabled:bg-[#93B4FF] shadow-[0_1px_3px_rgba(61,111,255,0.4)] disabled:shadow-none',
  secondary:
    'border border-slate-200 bg-white text-slate-800 hover:bg-slate-50 disabled:text-slate-600',
  danger:
    'bg-red-700 text-white hover:bg-red-800 disabled:bg-red-400 shadow-[0_1px_3px_rgba(239,68,68,0.35)] disabled:shadow-none',
}

type Props = ComponentPropsWithRef<'button'> & {
  variant?: Variant
}

export function Button({
  variant = 'primary',
  className = '',
  type = 'button',
  ...rest
}: Props) {
  return (
    <button
      type={type}
      className={`rounded-[7px] px-4 py-2 text-sm font-semibold tracking-[0.01em] transition-colors disabled:cursor-not-allowed ${VARIANT_CLASSES[variant]} ${className}`}
      {...rest}
    />
  )
}
