import { describe, expect, it } from 'vitest'

import { formatDateJst, formatDateTimeJst, startOfJstDayMs } from './dates'

describe('JST 表示変換', () => {
  it('UTC の ISO 文字列を JST の日付にする（+9時間で日付が変わるケース）', () => {
    // UTC 15:30 = JST 翌日 0:30
    expect(formatDateJst('2026-06-01T15:30:00Z')).toBe('2026/6/2')
  })

  it('UTC の ISO 文字列を JST の日時にする', () => {
    expect(formatDateTimeJst('2026-06-01T09:30:00Z')).toBe('2026/6/1 18:30')
  })

  it('JST日付の開始時刻を返す', () => {
    // 2026-06-28 18:00 JST = 09:00 UTC → 当日0:00 JST = 2026-06-27 15:00 UTC
    expect(startOfJstDayMs(Date.parse('2026-06-28T09:00:00.000Z'))).toBe(
      Date.parse('2026-06-27T15:00:00.000Z'),
    )
  })
})
