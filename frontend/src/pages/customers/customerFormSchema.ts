import { z } from 'zod'

import type { CustomerCreate } from '../../api/client'
import { customerAreaSchema, customerStatusSchema } from '../../api/enums'

// 制約はサーバと同値。最終判定はサーバの 422 に従う
export const customerFormSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, '顧客名を入力してください')
    .max(80, '顧客名は80文字以内で入力してください'),
  address: z.string().max(200, '住所は200文字以内で入力してください'),
  area: customerAreaSchema,
  status: customerStatusSchema,
  owner_id: z.coerce.number().int().min(1, '担当者を選択してください'),
})

export type CustomerFormInput = z.input<typeof customerFormSchema>
export type CustomerFormOutput = z.output<typeof customerFormSchema>

type CreateBodyOptions = {
  includeOwnerId?: boolean
}

export function toCreateBody(
  values: CustomerFormOutput,
  options: CreateBodyOptions = {},
): CustomerCreate {
  const body: CustomerCreate = {
    name: values.name,
    address: values.address === '' ? null : values.address,
    area: values.area,
    status: values.status,
  }

  if (options.includeOwnerId ?? true) {
    body.owner_id = values.owner_id
  }

  return body
}
