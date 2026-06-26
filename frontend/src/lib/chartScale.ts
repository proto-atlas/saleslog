// 自前バーチャートの目盛り計算

export type ChartScale = {
  max: number
  ticks: number[]
}

const TICK_COUNT = 4 // 目盛りの本数（0 を除く）。読みやすさの目安

// 最大値を 1 / 2 / 5 × 10^n に切り上げ、均等な目盛りを返す
export function calcScale(maxValue: number): ChartScale {
  if (maxValue <= 0) {
    return { max: TICK_COUNT, ticks: [1, 2, 3, 4] }
  }
  const rawStep = maxValue / TICK_COUNT
  const magnitude = 10 ** Math.floor(Math.log10(rawStep))
  const candidates = [1, 2, 5, 10].map((base) => base * magnitude)
  const step = candidates.find((candidate) => candidate * TICK_COUNT >= maxValue) ?? candidates[3]
  const ticks = Array.from({ length: TICK_COUNT }, (_, i) => step * (i + 1))
  return { max: step * TICK_COUNT, ticks }
}
