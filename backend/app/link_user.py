"""users.external_id へ認証プロバイダの subject を紐付ける CLI。

実行: .venv/Scripts/python -m app.link_user <user_id> <sub>
管理画面導入前の初回紐付け（bootstrap）に使う。
"""

import sys

from app.db import SessionLocal
from app.models import User


def main() -> None:
    if len(sys.argv) != 3:
        print("使い方: python -m app.link_user <user_id> <sub>")
        raise SystemExit(2)
    user_id = int(sys.argv[1])
    sub = sys.argv[2].strip()
    if sub == "":
        print("sub は空白以外の文字列を指定してください")
        raise SystemExit(2)

    with SessionLocal() as session, session.begin():
        user = session.get(User, user_id)
        if user is None:
            print(f"user_id={user_id} のユーザーが見つかりません")
            raise SystemExit(1)
        user.external_id = sub
        name = user.name
    print(f"紐付け完了: {name} (id={user_id})")


if __name__ == "__main__":
    main()
