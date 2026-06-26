import { describe, expect, it } from 'vitest'

import { customerFormSchema, toCreateBody } from './customerFormSchema'

const VALID_INPUT = {
  name: '  株式会社テスト  ',
  address: '',
  area: 'tokyo',
  status: 'prospect',
  owner_id: '2',
}

describe('customerFormSchema', () => {
  it('有効な入力を変換する（trim と owner_id の数値化）', () => {
    const parsed = customerFormSchema.parse(VALID_INPUT)
    expect(parsed.name).toBe('株式会社テスト')
    expect(parsed.owner_id).toBe(2)
  })

  it('空白のみの name は拒否する', () => {
    const result = customerFormSchema.safeParse({ ...VALID_INPUT, name: '   ' })
    expect(result.success).toBe(false)
  })

  it('name は 80 文字まで、81 文字は拒否する', () => {
    expect(
      customerFormSchema.safeParse({ ...VALID_INPUT, name: 'あ'.repeat(80) }).success,
    ).toBe(true)
    expect(
      customerFormSchema.safeParse({ ...VALID_INPUT, name: 'あ'.repeat(81) }).success,
    ).toBe(false)
  })

  it('owner_id が未選択（空文字 → 0）の場合は拒否する', () => {
    const result = customerFormSchema.safeParse({ ...VALID_INPUT, owner_id: '' })
    expect(result.success).toBe(false)
  })
})

describe('toCreateBody', () => {
  it('空文字の address を null に変換する', () => {
    const body = toCreateBody(customerFormSchema.parse(VALID_INPUT))
    expect(body.address).toBeNull()
  })

  it('入力済みの address はそのまま送る', () => {
    const body = toCreateBody(
      customerFormSchema.parse({ ...VALID_INPUT, address: '東京都港区1-2-3' }),
    )
    expect(body.address).toBe('東京都港区1-2-3')
  })

  it('owner_id を省略する作成bodyに変換できる', () => {
    const body = toCreateBody(customerFormSchema.parse(VALID_INPUT), {
      includeOwnerId: false,
    })
    expect(body.owner_id).toBeUndefined()
  })
})
