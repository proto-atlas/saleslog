import { describe, expect, test } from 'vitest'

import { findNextPlannedVisit } from './nextPlannedVisit'

describe('findNextPlannedVisit', () => {
  test('当日の未完了予定を次回訪問として返す', () => {
    const visits = [
      { status: 'planned' as const, visited_at: '2026-07-12T00:30:00+09:00' },
    ]

    expect(findNextPlannedVisit(visits, Date.parse('2026-07-12T18:00:00+09:00'))).toBe(visits[0])
  })

  test('複数の未完了予定から最も早い予定を返す', () => {
    const visits = [
      { status: 'planned' as const, visited_at: '2026-07-14T10:00:00+09:00' },
      { status: 'planned' as const, visited_at: '2026-07-13T10:00:00+09:00' },
    ]

    expect(findNextPlannedVisit(visits, Date.parse('2026-07-12T18:00:00+09:00'))).toBe(visits[1])
  })

  test('完了済みの当日訪問は次回訪問に含めない', () => {
    const visits = [
      { status: 'done' as const, visited_at: '2026-07-12T19:00:00+09:00' },
    ]

    expect(findNextPlannedVisit(visits, Date.parse('2026-07-12T18:00:00+09:00'))).toBeNull()
  })
})
