from typing import Protocol, cast


class SupportsRowcount(Protocol):
    rowcount: int | None


def result_rowcount(result: object) -> int:
    return int(cast(SupportsRowcount, result).rowcount or 0)
