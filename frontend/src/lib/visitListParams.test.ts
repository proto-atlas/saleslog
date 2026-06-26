import { describe, expect, it } from 'vitest'

import {
  buildVisitListSearch,
  parseVisitListParams,
  toVisitListApiParams,
} from './visitListParams'

describe('parseVisitListParams', () => {
  it('有効なクエリを型付きで取り出す', () => {
    const sp = new URLSearchParams(
      'customer_id=2&user_id=3&status=planned&from=2026-06-01&to=2026-06-05&unrecorded=true&page=2',
    )
    expect(parseVisitListParams(sp)).toEqual({
      customer_id: 2,
      user_id: 3,
      status: 'planned',
      from: '2026-06-01',
      to: '2026-06-05',
      unrecorded: true,
      page: 2,
    })
  })

  it('不正値は黙って捨てる', () => {
    const sp = new URLSearchParams(
      'customer_id=abc&status=unknown&from=06-01&unrecorded=1&page=0',
    )
    const params = parseVisitListParams(sp)
    expect(params.customer_id).toBeUndefined()
    expect(params.status).toBeUndefined()
    expect(params.from).toBeUndefined()
    expect(params.unrecorded).toBeUndefined()
    expect(params.page).toBeUndefined()
  })
})

describe('buildVisitListSearch', () => {
  it('未指定・既定値はキーを出さない', () => {
    expect(buildVisitListSearch({}).toString()).toBe('')
    expect(buildVisitListSearch({ page: 1 }).toString()).toBe('')
  })

  it('unrecorded=true を往復できる', () => {
    const sp = buildVisitListSearch({ unrecorded: true })
    expect(sp.get('unrecorded')).toBe('true')
    expect(parseVisitListParams(sp).unrecorded).toBe(true)
  })
})

describe('toVisitListApiParams', () => {
  it('期間（JST 日付）を UTC ISO の日界に変換する', () => {
    const api = toVisitListApiParams({ from: '2026-06-01', to: '2026-06-01' })
    // JST 6/1 0:00 = UTC 5/31 15:00
    expect(api.from).toBe('2026-05-31T15:00:00.000Z')
    // JST 6/1 23:59:59.999 = UTC 6/1 14:59:59.999
    expect(api.to).toBe('2026-06-01T14:59:59.999Z')
  })

  it('未指定の期間は undefined のまま', () => {
    const api = toVisitListApiParams({})
    expect(api.from).toBeUndefined()
    expect(api.to).toBeUndefined()
  })
})
