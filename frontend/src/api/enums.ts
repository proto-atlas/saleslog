import { z } from 'zod'

import type { components } from './generated/schema'

// 生成 union（OpenAPI 由来）を型の真実源とし、実行時値は as const 配列で持つ。
// 混入は satisfies、欠落は Assert<false になる条件型> で双方向に検査する。
type Assert<T extends true> = T

export type CustomerStatus = components['schemas']['CustomerStatus']
export type CustomerArea = components['schemas']['CustomerArea']
export type UserRole = components['schemas']['UserRole']
export type ActivityType = components['schemas']['ActivityType']
export type VisitStatus = components['schemas']['VisitStatus']

export const CUSTOMER_STATUS = [
  'prospect',
  'negotiating',
  'won',
  'lost',
  'dormant',
] as const satisfies readonly CustomerStatus[]
export type _CustomerStatusExhaustive = Assert<
  [CustomerStatus] extends [(typeof CUSTOMER_STATUS)[number]] ? true : false
>

export const CUSTOMER_AREA = [
  'tokyo',
  'kanagawa',
  'saitama',
  'chiba',
  'other',
] as const satisfies readonly CustomerArea[]
export type _CustomerAreaExhaustive = Assert<
  [CustomerArea] extends [(typeof CUSTOMER_AREA)[number]] ? true : false
>

export const ACTIVITY_TYPE = [
  'visit',
  'call',
  'email',
  'online',
] as const satisfies readonly ActivityType[]
export type _ActivityTypeExhaustive = Assert<
  [ActivityType] extends [(typeof ACTIVITY_TYPE)[number]] ? true : false
>

export const VISIT_STATUS = [
  'planned',
  'done',
  'cancelled',
] as const satisfies readonly VisitStatus[]
export type _VisitStatusExhaustive = Assert<
  [VisitStatus] extends [(typeof VISIT_STATUS)[number]] ? true : false
>

export const USER_ROLE = ['sales', 'manager'] as const satisfies readonly UserRole[]
export type _UserRoleExhaustive = Assert<
  [UserRole] extends [(typeof USER_ROLE)[number]] ? true : false
>

export const customerStatusSchema = z.enum(CUSTOMER_STATUS)
export const customerAreaSchema = z.enum(CUSTOMER_AREA)
export const activityTypeSchema = z.enum(ACTIVITY_TYPE)
export const visitStatusSchema = z.enum(VISIT_STATUS)

// 表示ラベル（内部キーは英小文字、表示は日本語。仕様）
export const customerStatusLabels: Record<CustomerStatus, string> = {
  prospect: '見込み',
  negotiating: '商談中',
  won: '受注',
  lost: '失注',
  dormant: '休眠',
}

export const customerAreaLabels: Record<CustomerArea, string> = {
  tokyo: '東京',
  kanagawa: '神奈川',
  saitama: '埼玉',
  chiba: '千葉',
  other: 'その他',
}

export const activityTypeLabels: Record<ActivityType, string> = {
  visit: '訪問',
  call: '電話',
  email: 'メール',
  online: 'オンライン会議',
}

export const visitStatusLabels: Record<VisitStatus, string> = {
  planned: '予定',
  done: '完了',
  cancelled: 'キャンセル',
}

export const userRoleLabels: Record<UserRole, string> = {
  sales: '営業',
  manager: 'マネージャー',
}
