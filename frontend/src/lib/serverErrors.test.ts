import { describe, expect, it, vi } from 'vitest'
import type { UseFormSetError } from 'react-hook-form'

import { applyServerFieldErrors } from './serverErrors'

type Form = { name: string; area: string }

function makeSetError() {
  const fn = vi.fn()
  return { fn, setError: fn as unknown as UseFormSetError<Form> }
}

describe('applyServerFieldErrors', () => {
  it('既知フィールドの 422 を setError にマッピングする', () => {
    const { fn, setError } = makeSetError()
    const rest = applyServerFieldErrors(
      [{ loc: ['body', 'name'], msg: '顧客名を入力してください', type: 'value_error' }],
      setError,
      ['name', 'area'],
    )
    expect(fn).toHaveBeenCalledWith('name', {
      type: 'server',
      message: '顧客名を入力してください',
    })
    expect(rest).toBeNull()
  })

  it('未知フィールドはフォーム全体エラーとして返す', () => {
    const { fn, setError } = makeSetError()
    const rest = applyServerFieldErrors(
      [
        { loc: ['body', 'unknown_field'], msg: '不明な項目です', type: 'value_error' },
        { loc: ['query'], msg: 'クエリ不正', type: 'value_error' },
      ],
      setError,
      ['name', 'area'],
    )
    expect(fn).not.toHaveBeenCalled()
    expect(rest).toBe('不明な項目です / クエリ不正')
  })

  it('既知と未知が混在する場合は両方処理する', () => {
    const { fn, setError } = makeSetError()
    const rest = applyServerFieldErrors(
      [
        { loc: ['body', 'area'], msg: 'エリアが不正です', type: 'value_error' },
        { loc: ['body', 'other'], msg: 'その他のエラー', type: 'value_error' },
      ],
      setError,
      ['name', 'area'],
    )
    expect(fn).toHaveBeenCalledTimes(1)
    expect(rest).toBe('その他のエラー')
  })
})
