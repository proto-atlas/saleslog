import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderHook } from '@testing-library/react'

import { DRAFT_DEBOUNCE_MS, useFormDraft } from './useFormDraft'

class FakeStorage {
  private store = new Map<string, string>()
  getItem(key: string): string | null {
    return this.store.get(key) ?? null
  }
  setItem(key: string, value: string): void {
    this.store.set(key, value)
  }
  removeItem(key: string): void {
    this.store.delete(key)
  }
}

describe('useFormDraft', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('入力値変更から debounce 後に保存される', () => {
    const storage = new FakeStorage()
    const { rerender } = renderHook(
      ({ values }) =>
        useFormDraft({ key: 'draft:visit:new', values, enabled: true, storage }),
      { initialProps: { values: { memo: '' } } },
    )

    rerender({ values: { memo: '下書きA' } })
    expect(storage.getItem('draft:visit:new')).toBeNull()

    vi.advanceTimersByTime(DRAFT_DEBOUNCE_MS)
    expect(storage.getItem('draft:visit:new')).toBe(
      JSON.stringify({ memo: '下書きA' }),
    )
  })

  it('マウント時に既存の下書きがあれば pendingDraft として返す', () => {
    const storage = new FakeStorage()
    storage.setItem('draft:visit:new', JSON.stringify({ memo: '前回の入力' }))

    const { result } = renderHook(() =>
      useFormDraft({
        key: 'draft:visit:new',
        values: { memo: '' },
        enabled: true,
        storage,
      }),
    )
    expect(result.current.pendingDraft).toEqual({ memo: '前回の入力' })
  })

  it('復元確認に答える前は上書き保存しない', () => {
    const storage = new FakeStorage()
    storage.setItem('draft:visit:new', JSON.stringify({ memo: '前回の入力' }))

    const { rerender } = renderHook(
      ({ values }) =>
        useFormDraft({ key: 'draft:visit:new', values, enabled: true, storage }),
      { initialProps: { values: { memo: '' } } },
    )
    rerender({ values: { memo: '新しい入力' } })
    vi.advanceTimersByTime(DRAFT_DEBOUNCE_MS)

    expect(storage.getItem('draft:visit:new')).toBe(
      JSON.stringify({ memo: '前回の入力' }),
    )
  })

  it('discardDraft はキーを削除しプロンプトを閉じる', () => {
    const storage = new FakeStorage()
    storage.setItem('draft:visit:new', JSON.stringify({ memo: '前回の入力' }))

    const { result, rerender } = renderHook(
      ({ values }) =>
        useFormDraft({ key: 'draft:visit:new', values, enabled: true, storage }),
      { initialProps: { values: { memo: '' } } },
    )
    result.current.discardDraft()
    rerender({ values: { memo: '' } })

    expect(storage.getItem('draft:visit:new')).toBeNull()
    expect(result.current.pendingDraft).toBeNull()
  })

  it('clearDraft（保存成功時）はキーを削除する', () => {
    const storage = new FakeStorage()
    const { result, rerender } = renderHook(
      ({ values }) =>
        useFormDraft({ key: 'draft:visit:new', values, enabled: true, storage }),
      { initialProps: { values: { memo: '' } } },
    )
    rerender({ values: { memo: '保存予定' } })
    vi.advanceTimersByTime(DRAFT_DEBOUNCE_MS)
    expect(storage.getItem('draft:visit:new')).not.toBeNull()

    result.current.clearDraft()
    expect(storage.getItem('draft:visit:new')).toBeNull()
  })

  it('key が変わったら新しいキーの下書きを読み直す', () => {
    // 認証有効時、ユーザー ID 確定で draft:visit:new → draft:visit:new:2 に変わるケース
    const storage = new FakeStorage()
    storage.setItem('draft:visit:new:2', JSON.stringify({ memo: 'ユーザー2の下書き' }))

    const { result, rerender } = renderHook(
      ({ key }) =>
        useFormDraft({ key, values: { memo: '' }, enabled: false, storage }),
      { initialProps: { key: 'draft:visit:new' } },
    )
    expect(result.current.pendingDraft).toBeNull()

    rerender({ key: 'draft:visit:new:2' })
    expect(result.current.pendingDraft).toEqual({ memo: 'ユーザー2の下書き' })
  })
})
