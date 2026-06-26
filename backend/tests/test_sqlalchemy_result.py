from dataclasses import dataclass

from app.sqlalchemy_result import result_rowcount


@dataclass
class _ResultLike:
    rowcount: int | None


def test_result_rowcount_normalizes_none_to_zero():
    assert result_rowcount(_ResultLike(rowcount=None)) == 0


def test_result_rowcount_returns_integer_value():
    assert result_rowcount(_ResultLike(rowcount=2)) == 2
