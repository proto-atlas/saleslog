import { describe, expect, it } from 'vitest'

import { calcScale } from './chartScale'

describe('calcScale', () => {
  it('0 以下でも描画できる既定スケールを返す', () => {
    expect(calcScale(0)).toEqual({ max: 4, ticks: [1, 2, 3, 4] })
  })

  it('最大値を 1/2/5 系列の目盛りに切り上げる', () => {
    expect(calcScale(7)).toEqual({ max: 8, ticks: [2, 4, 6, 8] })
    expect(calcScale(13)).toEqual({ max: 20, ticks: [5, 10, 15, 20] })
    expect(calcScale(60)).toEqual({ max: 80, ticks: [20, 40, 60, 80] })
    expect(calcScale(300)).toEqual({ max: 400, ticks: [100, 200, 300, 400] })
  })

  it('最大値が目盛り上限を超えない', () => {
    for (const value of [1, 3, 9, 21, 49, 99, 101, 999]) {
      expect(calcScale(value).max).toBeGreaterThanOrEqual(value)
    }
  })
})
