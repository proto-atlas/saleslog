import { describe, expect, it } from 'vitest'

import {
  buildCustomerListSearch,
  parseCustomerListParams,
} from './customerListParams'

describe('parseCustomerListParams', () => {
  it('有効なクエリを型付きパラメータへ変換する', () => {
    const sp = new URLSearchParams(
      'search=商事&area=tokyo&status=won&owner_id=2&sort=-name&page=3&page_size=50',
    )
    expect(parseCustomerListParams(sp)).toEqual({
      search: '商事',
      area: 'tokyo',
      status: 'won',
      owner_id: 2,
      sort: '-name',
      page: 3,
      page_size: 50,
    })
  })

  it('不正値・許可外の値は黙って捨てる', () => {
    const sp = new URLSearchParams(
      'area=osaka&status=unknown&owner_id=abc&sort=address&page=0&page_size=101',
    )
    expect(parseCustomerListParams(sp)).toEqual({
      area: undefined,
      status: undefined,
      owner_id: undefined,
      sort: undefined,
    })
  })

  it('空白のみの search は未指定として扱う', () => {
    const sp = new URLSearchParams('search=%20%20')
    expect(parseCustomerListParams(sp).search).toBeUndefined()
  })

  it('既定値と同じ page / page_size はパラメータに含めない', () => {
    const sp = new URLSearchParams('page=1&page_size=20')
    const params = parseCustomerListParams(sp)
    expect(params.page).toBeUndefined()
    expect(params.page_size).toBeUndefined()
  })
})

describe('buildCustomerListSearch', () => {
  it('空値・既定値はキーを出さない', () => {
    const sp = buildCustomerListSearch({
      search: '',
      area: undefined,
      page: 1,
      page_size: 20,
    })
    expect(sp.toString()).toBe('')
  })

  it('指定値だけをクエリにする', () => {
    const sp = buildCustomerListSearch({
      search: '商事',
      status: 'prospect',
      page: 2,
    })
    expect(sp.get('search')).toBe('商事')
    expect(sp.get('status')).toBe('prospect')
    expect(sp.get('page')).toBe('2')
    expect(sp.get('area')).toBeNull()
  })

  it('parse → build の往復で同じクエリに戻る', () => {
    const original = 'area=chiba&page=2&search=%E5%95%86%E4%BA%8B&sort=name'
    const parsed = parseCustomerListParams(new URLSearchParams(original))
    const rebuilt = buildCustomerListSearch(parsed)
    expect(
      [...rebuilt.entries()].sort((a, b) => a[0].localeCompare(b[0])),
    ).toEqual([...new URLSearchParams(original).entries()].sort((a, b) => a[0].localeCompare(b[0])))
  })
})
