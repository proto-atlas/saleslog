"""開発・デモ・E2E 用の決定的 seed。

実行: .venv/Scripts/python -m app.seed
読み取り専用デモのリセットは reset() を 1 トランザクションで呼ぶ
（HTTP エンドポイントは設けない。リセット中の GET に中間状態を見せない。仕様）。

構成:
- アンカー行（固定 id・固定名）: E2E / pytest / Lighthouse の期待値が紐づく
- バルク行: 固定シード乱数（random.Random(20260604)）による決定的生成

E2E が前提にする固定値:
- 顧客 id=1（株式会社アオバ製作所）は活動履歴を複数件持つ（E2E / Lighthouse 対象）
- 検索 `商事` は 3 件、`sky` / `SKY` は 1 件に一致（E2E / pytest の期待値。
  バルク名の語彙に「商事」「Sky」「%」「_」「\\」を含めず、期待件数の変動を避ける）
"""

import random
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db import Base, SessionLocal, engine
from app.enums import ActivityType, CustomerArea, CustomerStatus, UserRole, VisitStatus
from app.models import (
    AgentApproval,
    AgentApprovalIdempotencyRecord,
    AgentArtifact,
    AgentEmailProposal,
    AgentEvent,
    AgentEventCursor,
    AgentMemo,
    AgentPersistedAction,
    AgentRun,
    AgentRunSource,
    AgentStep,
    AgentTask,
    Customer,
    KnowledgeChunk,
    KnowledgeDoc,
    User,
    Visit,
)

BULK_CUSTOMERS = 48  # アンカー12件と合わせて60件
BULK_VISITS = 285  # アンカー15件と合わせて300件
RANDOM_SEED = 20260604  # 決定的 seed

# バルク社名の語彙。検索期待値を壊さないよう「商事」等のアンカー語は含めない
_NAME_HEADS = [
    "アサヒ", "ミドリ", "ヒカリ", "ヤマト", "サンライズ", "フジミ", "ハヤテ", "コスモ",
    "ミライ", "ツバメ", "アズマ", "シラカバ", "イロハ", "カエデ", "ナギサ", "ホシノ",
    "ソラマチ", "ハマカゼ", "キタホシ", "ミナミデ", "タカラギ", "ニシキ", "アヤメ", "クルミ",
]
_NAME_TAILS = [
    "工業", "物産", "システムズ", "興産", "電機", "運輸", "製薬", "設備",
    "技研", "エナジー", "ロジテック", "プランニング",
]
_PREFS = ["東京都", "神奈川県", "埼玉県", "千葉県", "茨城県"]
_MEMO_SAMPLES = [
    "定例の進捗確認",
    "見積り条件のすり合わせ",
    "新製品の紹介",
    "請求関連の確認",
    "次回提案の宿題を回収",
    None,
    None,
]

RESET_DELETE_MODELS = (
    AgentPersistedAction,
    AgentTask,
    AgentMemo,
    AgentEmailProposal,
    AgentApprovalIdempotencyRecord,
    Visit,
    AgentEvent,
    AgentApproval,
    AgentArtifact,
    AgentRunSource,
    AgentStep,
    AgentEventCursor,
    AgentRun,
    KnowledgeChunk,
    KnowledgeDoc,
    Customer,
    User,
)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _anchor_users() -> list[User]:
    return [
        User(id=1, name="管理者ユーザー", role=UserRole.manager),
        User(id=2, name="営業ユーザーA", role=UserRole.sales),
        User(id=3, name="営業ユーザーB", role=UserRole.sales),
    ]


def _anchor_customers() -> list[Customer]:
    return [
        # id=1 は E2E / Lighthouse の固定対象（活動履歴を複数持たせる）
        Customer(id=1, name="株式会社アオバ製作所", address="東京都大田区1-2-3", area=CustomerArea.tokyo, status=CustomerStatus.negotiating, owner_id=2),
        Customer(id=2, name="マルヤマ商事", address="東京都台東区4-5-6", area=CustomerArea.tokyo, status=CustomerStatus.prospect, owner_id=2),
        Customer(id=3, name="Sky Net Works 株式会社", address="神奈川県横浜市7-8-9", area=CustomerArea.kanagawa, status=CustomerStatus.won, owner_id=3),
        Customer(id=4, name="100%サポート株式会社", address="埼玉県さいたま市1-1-1", area=CustomerArea.saitama, status=CustomerStatus.negotiating, owner_id=3),
        Customer(id=5, name="A_Bテクノロジーズ", address="千葉県千葉市2-2-2", area=CustomerArea.chiba, status=CustomerStatus.prospect, owner_id=2),
        Customer(id=6, name="北関東商事", address="埼玉県川口市3-3-3", area=CustomerArea.saitama, status=CustomerStatus.dormant, owner_id=3),
        Customer(id=7, name="湾岸商事", address="千葉県市川市4-4-4", area=CustomerArea.chiba, status=CustomerStatus.lost, owner_id=2),
        Customer(id=8, name="さくらフーズ", address="東京都新宿区5-5-5", area=CustomerArea.tokyo, status=CustomerStatus.won, owner_id=1),
        Customer(id=9, name="ミナト物流", address="神奈川県川崎市6-6-6", area=CustomerArea.kanagawa, status=CustomerStatus.negotiating, owner_id=3),
        Customer(id=10, name="オリオン電装", address=None, area=CustomerArea.other, status=CustomerStatus.prospect, owner_id=1),
        Customer(id=11, name="ハルカワ印刷", address="東京都板橋区7-7-7", area=CustomerArea.tokyo, status=CustomerStatus.dormant, owner_id=2),
        Customer(id=12, name="ツバキ建設", address="神奈川県相模原市8-8-8", area=CustomerArea.kanagawa, status=CustomerStatus.prospect, owner_id=3),
    ]


def _anchor_visits(now: datetime) -> list[Visit]:
    return [
        # 顧客1: 履歴4件 + 未来の予定1件（次回訪問予定の導出対象）
        Visit(customer_id=1, user_id=2, activity_type=ActivityType.visit, status=VisitStatus.done, visited_at=now - timedelta(days=150), memo="初回訪問。担当者と名刺交換"),
        Visit(customer_id=1, user_id=2, activity_type=ActivityType.online, status=VisitStatus.done, visited_at=now - timedelta(days=90), memo="オンラインで見積り条件のすり合わせ"),
        Visit(customer_id=1, user_id=2, activity_type=ActivityType.call, status=VisitStatus.done, visited_at=now - timedelta(days=30), memo="進捗確認の電話。次回<b>重要</b>案件の相談あり"),
        Visit(customer_id=1, user_id=2, activity_type=ActivityType.visit, status=VisitStatus.done, visited_at=now - timedelta(days=7), memo="提案書を持参して説明"),
        Visit(customer_id=1, user_id=2, activity_type=ActivityType.visit, status=VisitStatus.planned, visited_at=now + timedelta(days=3), memo="契約条件の最終確認"),
        # 入力漏れ（予定日時を過ぎたまま planned）×2 — ダッシュボード警告と unrecorded フィルタの対象
        Visit(customer_id=2, user_id=2, activity_type=ActivityType.visit, status=VisitStatus.planned, visited_at=now - timedelta(days=2), memo="新規開拓の初回訪問予定"),
        Visit(customer_id=9, user_id=3, activity_type=ActivityType.call, status=VisitStatus.planned, visited_at=now - timedelta(days=10), memo=None),
        # 今日の予定（ダッシュボードの導線対象になりうる）
        Visit(customer_id=3, user_id=3, activity_type=ActivityType.online, status=VisitStatus.planned, visited_at=now + timedelta(hours=2), memo="保守契約の更新打診"),
        # 訪問推移グラフが 6 ヶ月にわたるよう分散
        Visit(customer_id=6, user_id=3, activity_type=ActivityType.visit, status=VisitStatus.done, visited_at=now - timedelta(days=120), memo="休眠顧客の掘り起こし訪問"),
        Visit(customer_id=7, user_id=2, activity_type=ActivityType.visit, status=VisitStatus.done, visited_at=now - timedelta(days=60), memo="競合採用の連絡を受領"),
        Visit(customer_id=8, user_id=1, activity_type=ActivityType.visit, status=VisitStatus.done, visited_at=now - timedelta(days=70), memo="納品立ち会い"),
        Visit(customer_id=3, user_id=3, activity_type=ActivityType.visit, status=VisitStatus.done, visited_at=now - timedelta(days=40), memo="導入後フォロー"),
        Visit(customer_id=4, user_id=3, activity_type=ActivityType.email, status=VisitStatus.done, visited_at=now - timedelta(days=20), memo="見積り送付"),
        Visit(customer_id=10, user_id=1, activity_type=ActivityType.call, status=VisitStatus.done, visited_at=now - timedelta(days=8), memo="紹介経由の初回ヒアリング"),
        Visit(customer_id=5, user_id=2, activity_type=ActivityType.visit, status=VisitStatus.cancelled, visited_at=now - timedelta(days=15), memo="先方都合で中止"),
    ]


def _bulk_customers(rand: random.Random) -> list[Customer]:
    customers = []
    for _ in range(BULK_CUSTOMERS):
        head = rand.choice(_NAME_HEADS)
        tail = rand.choice(_NAME_TAILS)
        address = (
            f"{rand.choice(_PREFS)}サンプル市{rand.randint(1, 9)}-{rand.randint(1, 9)}-{rand.randint(1, 9)}"
            if rand.random() > 0.15
            else None
        )
        customers.append(
            Customer(
                name=f"{head}{tail}",
                address=address,
                area=rand.choice(list(CustomerArea)),
                status=rand.choice(list(CustomerStatus)),
                # 担当別集計が複数本のバーになるよう分散（sales 寄り）
                owner_id=rand.choice([1, 2, 2, 3, 3]),
            )
        )
    return customers


def _bulk_visits(
    rand: random.Random, now: datetime, customer_ids: list[int]
) -> list[Visit]:
    visits = []
    for _ in range(BULK_VISITS):
        # 直近6ヶ月の実績 + 今日/今後数日の予定に分散
        if rand.random() < 0.12:
            visited_at = now + timedelta(
                days=rand.randint(0, 7), hours=rand.randint(0, 9)
            )
            status = VisitStatus.planned
        else:
            visited_at = now - timedelta(
                days=rand.randint(0, 180), hours=rand.randint(0, 23)
            )
            # 過去分の大半は done。一部を planned のまま残し「入力漏れ」を決定的に再現する
            roll = rand.random()
            if roll < 0.85:
                status = VisitStatus.done
            elif roll < 0.93:
                status = VisitStatus.cancelled
            else:
                status = VisitStatus.planned
        visits.append(
            Visit(
                customer_id=rand.choice(customer_ids),
                user_id=rand.choice([1, 2, 2, 3, 3]),
                activity_type=rand.choice(list(ActivityType)),
                status=status,
                visited_at=visited_at,
                memo=rand.choice(_MEMO_SAMPLES),
            )
        )
    return visits


def reset(session: Session) -> None:
    """全データを削除して seed を投入する。呼び出し側が 1 トランザクションで囲む。"""
    for model in RESET_DELETE_MODELS:
        session.query(model).delete(synchronize_session=False)

    rand = random.Random(RANDOM_SEED)

    session.add_all(_anchor_users())
    # relationship を張っていない FK（owner_id 等）は挿入順序の自動解決対象にならないため、
    # 参照される側を先に flush して INSERT 順を固定する
    session.flush()

    anchor_customers = _anchor_customers()
    session.add_all(anchor_customers)
    bulk_customers = _bulk_customers(rand)
    session.add_all(bulk_customers)
    session.flush()

    now = _now()
    customer_ids = [c.id for c in anchor_customers + bulk_customers]
    session.add_all(_anchor_visits(now))
    session.add_all(_bulk_visits(rand, now, customer_ids))


def main() -> None:
    # --empty: 顧客・活動記録を空にする（E2E の空状態検証用）。
    # users は認証・固定ユーザー解決の前提インフラのため投入する
    args = sys.argv[1:]
    only_users = "--empty" in args
    reset_schema = "--reset-schema" in args
    if reset_schema:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    if only_users:
        with SessionLocal() as session, session.begin():
            for model in RESET_DELETE_MODELS:
                session.query(model).delete(synchronize_session=False)
            session.add_all(_anchor_users())
        print("空DBを作成（users のみ投入）")
        return
    with SessionLocal() as session, session.begin():
        reset(session)
    total_customers = BULK_CUSTOMERS + 12
    total_visits = BULK_VISITS + 15
    print(f"seed 投入完了: users=3, customers={total_customers}, visits={total_visits}")


if __name__ == "__main__":
    main()
