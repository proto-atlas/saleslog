"""JST（Asia/Tokyo）基準の日付境界ユーティリティ。

DB は naive UTC 格納。「今日 / 今月 / 直近6ヶ月」の判定は JST で行い、
比較は UTC naive に変換してから SQL に渡す。
"""

from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))


def utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _jst_to_utc_naive(jst_dt: datetime) -> datetime:
    return jst_dt.astimezone(timezone.utc).replace(tzinfo=None)


def to_jst(utc_naive: datetime) -> datetime:
    return utc_naive.replace(tzinfo=timezone.utc).astimezone(JST)


def jst_today_bounds(now_utc_naive: datetime) -> tuple[datetime, datetime]:
    """JST の当日 [0:00, 翌日 0:00) を UTC naive で返す。"""
    jst_now = to_jst(now_utc_naive)
    day_start = jst_now.replace(hour=0, minute=0, second=0, microsecond=0)
    return _jst_to_utc_naive(day_start), _jst_to_utc_naive(day_start + timedelta(days=1))


def _jst_month_start(jst_dt: datetime) -> datetime:
    return jst_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _add_months(jst_month_start: datetime, months: int) -> datetime:
    month_index = jst_month_start.month - 1 + months
    year = jst_month_start.year + month_index // 12
    month = month_index % 12 + 1
    return jst_month_start.replace(year=year, month=month)


def jst_this_month_bounds(now_utc_naive: datetime) -> tuple[datetime, datetime]:
    """JST の当月 [月初, 翌月初) を UTC naive で返す。"""
    start = _jst_month_start(to_jst(now_utc_naive))
    return _jst_to_utc_naive(start), _jst_to_utc_naive(_add_months(start, 1))


def jst_last_six_months(now_utc_naive: datetime) -> list[str]:
    """当月を含む直近6ヶ月の "YYYY-MM"（昇順。仕様 visits_trend）。"""
    start = _jst_month_start(to_jst(now_utc_naive))
    months = [_add_months(start, offset) for offset in range(-5, 1)]
    return [m.strftime("%Y-%m") for m in months]


def jst_six_months_window(now_utc_naive: datetime) -> tuple[datetime, datetime]:
    """trend 集計対象の [5ヶ月前の月初, 翌月初) を UTC naive で返す。"""
    start = _jst_month_start(to_jst(now_utc_naive))
    return (
        _jst_to_utc_naive(_add_months(start, -5)),
        _jst_to_utc_naive(_add_months(start, 1)),
    )


def jst_month_key(utc_naive: datetime) -> str:
    """visited_at（UTC naive）を JST の "YYYY-MM" バケットへ。"""
    return to_jst(utc_naive).strftime("%Y-%m")
