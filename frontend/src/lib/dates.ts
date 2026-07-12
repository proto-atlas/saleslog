// 表示はすべて JST（データは UTC 格納。仕様）
const JST_DATE = new Intl.DateTimeFormat('ja-JP', {
  timeZone: 'Asia/Tokyo',
  year: 'numeric',
  month: 'numeric',
  day: 'numeric',
})

const JST_DATE_TIME = new Intl.DateTimeFormat('ja-JP', {
  timeZone: 'Asia/Tokyo',
  year: 'numeric',
  month: 'numeric',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})

export function formatDateJst(isoUtc: string): string {
  return JST_DATE.format(new Date(isoUtc))
}

export function formatDateTimeJst(isoUtc: string): string {
  return JST_DATE_TIME.format(new Date(isoUtc))
}

/** 指定時刻が属する JST 日付の 0:00 を UTC ミリ秒で返す */
export function startOfJstDayMs(ms: number): number {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Tokyo',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date(ms))
  const year = Number(parts.find((part) => part.type === 'year')?.value)
  const month = Number(parts.find((part) => part.type === 'month')?.value)
  const day = Number(parts.find((part) => part.type === 'day')?.value)
  // JST 0:00 = UTC 前日 15:00
  return Date.UTC(year, month - 1, day, 0, 0, 0, 0) - 9 * 60 * 60 * 1000
}
