"""OpenAPI スキーマを backend/openapi.json へ書き出す（TS 型生成の入力。仕様）。

実行: .venv/Scripts/python -m app.export_openapi
"""

import json
from pathlib import Path

from app.main import app


def main() -> None:
    path = Path(__file__).resolve().parent.parent / "openapi.json"
    path.write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"openapi.json 書き出し完了: {path}")


if __name__ == "__main__":
    main()
