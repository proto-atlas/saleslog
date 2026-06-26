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
