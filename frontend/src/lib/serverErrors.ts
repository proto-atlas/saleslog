import type { FieldValues, Path, UseFormSetError } from 'react-hook-form'

import type { ValidationErrorItem } from '../api/client'

// サーバ 422 の detail[].loc 末尾をフォームフィールドへマッピングする。
// 解決できなかった分はフォーム全体エラーとして返す（null = 全件マッピングできた）。
export function applyServerFieldErrors<T extends FieldValues>(
  errors: ValidationErrorItem[],
  setError: UseFormSetError<T>,
  knownFields: readonly string[],
): string | null {
  const unresolved: string[] = []
  for (const error of errors) {
    const last = error.loc[error.loc.length - 1]
    if (typeof last === 'string' && knownFields.includes(last)) {
      setError(last as Path<T>, { type: 'server', message: error.msg })
    } else {
      unresolved.push(error.msg)
    }
  }
  return unresolved.length > 0 ? unresolved.join(' / ') : null
}
