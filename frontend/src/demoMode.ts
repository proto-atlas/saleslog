/** 静的UIデモの基準時刻（UTC）。合成データの「今日」判定と揃える。 */
export const STATIC_DEMO_CLOCK_ISO = '2026-06-28T09:00:00.000Z'

/** バナー表示用（JSTの日付） */
export const STATIC_DEMO_CLOCK_LABEL_JST = '2026-06-28'

export const staticDemoEnabled = import.meta.env.VITE_DEMO_MODE === 'static'

export function getAppReferenceTimeMs(nowMs: number = Date.now()): number {
  if (staticDemoEnabled) {
    return Date.parse(STATIC_DEMO_CLOCK_ISO)
  }
  return nowMs
}
