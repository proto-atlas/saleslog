import { describe, expect, it } from 'vitest'

import {
  toCreateBody,
  toPatchBody,
  utcIsoToLocalInput,
  visitFormSchema,
} from './visitFormSchema'

const VALID_INPUT = {
  customer_id: '1',
  activity_type: 'visit',
  status: 'done',
  visited_at: '2026-06-10T10:30',
  memo: '',
}

describe('visitFormSchema', () => {
  it('有効な入力を変換する（customer_id の数値化）', () => {
    const parsed = visitFormSchema.parse(VALID_INPUT)
    expect(parsed.customer_id).toBe(1)
  })

  it('顧客未選択（空文字 → 0）は拒否する', () => {
    expect(
      visitFormSchema.safeParse({ ...VALID_INPUT, customer_id: '' }).success,
    ).toBe(false)
  })

  it('memo は 2000 文字まで、2001 文字は拒否する', () => {
    expect(
      visitFormSchema.safeParse({ ...VALID_INPUT, memo: 'あ'.repeat(2000) }).success,
    ).toBe(true)
    expect(
      visitFormSchema.safeParse({ ...VALID_INPUT, memo: 'あ'.repeat(2001) }).success,
    ).toBe(false)
  })

  it('日時未入力は拒否する', () => {
    expect(
      visitFormSchema.safeParse({ ...VALID_INPUT, visited_at: '' }).success,
    ).toBe(false)
  })
})

describe('日時変換', () => {
  it('UTC ISO → ローカル入力値 → UTC ISO の往復が分精度で一致する', () => {
    // 実行環境のタイムゾーンに依存しない往復検証
    const utcIso = '2026-06-01T09:30:00.000Z'
    const localInput = utcIsoToLocalInput(utcIso)
    expect(localInput).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/)
    expect(new Date(localInput).toISOString()).toBe(utcIso)
  })

  it('toCreateBody はローカル日時を UTC ISO に変換し、空 memo を null にする', () => {
    const body = toCreateBody(visitFormSchema.parse(VALID_INPUT))
    expect(body.visited_at).toBe(new Date(VALID_INPUT.visited_at).toISOString())
    expect(body.memo).toBeNull()
  })

  it('toPatchBody は customer_id を含めない', () => {
    const body = toPatchBody(
      visitFormSchema.parse({ ...VALID_INPUT, memo: '更新メモ' }),
    )
    expect('customer_id' in body).toBe(false)
    expect(body.memo).toBe('更新メモ')
  })
})
