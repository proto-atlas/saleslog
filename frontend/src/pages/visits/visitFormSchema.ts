import { z } from 'zod'

import type { VisitCreate, VisitPatch } from '../../api/client'
import { activityTypeSchema, visitStatusSchema } from '../../api/enums'

// 制約はサーバと同値。visited_at はフォーム上 datetime-local 文字列で持つ
export const visitFormSchema = z.object({
  customer_id: z.coerce.number().int().min(1, '顧客を選択してください'),
  activity_type: activityTypeSchema,
  status: visitStatusSchema,
  visited_at: z.string().min(1, '日時を入力してください'),
  memo: z.string().max(2000, 'メモは2000文字以内で入力してください'),
})

export type VisitFormInput = z.input<typeof visitFormSchema>
export type VisitFormOutput = z.output<typeof visitFormSchema>

// datetime-local（ローカル時刻）→ ISO 8601 UTC
function localInputToUtcIso(value: string): string {
  return new Date(value).toISOString()
}

// ISO 8601 UTC → datetime-local の値（ローカル時刻の YYYY-MM-DDTHH:mm）
export function utcIsoToLocalInput(iso: string): string {
  const date = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export function toCreateBody(values: VisitFormOutput): VisitCreate {
  return {
    customer_id: values.customer_id,
    activity_type: values.activity_type,
    status: values.status,
    visited_at: localInputToUtcIso(values.visited_at),
    memo: values.memo === '' ? null : values.memo,
  }
}

export function toPatchBody(values: VisitFormOutput): VisitPatch {
  return {
    activity_type: values.activity_type,
    status: values.status,
    visited_at: localInputToUtcIso(values.visited_at),
    memo: values.memo === '' ? null : values.memo,
  }
}
