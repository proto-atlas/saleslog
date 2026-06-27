# ADR-0001: 認可の role 正本をデータベースに置く

## ステータス
採用済み

## 背景
- 認証導入後、API の認可判定に使う role（manager / sales）をどこに持つかを決める必要がある。
- 認証基盤の session token には任意のカスタム claim を載せられるため、「token に role を埋め込む」方式と「DB の users テーブルを正本にする」方式が選べる。
- token の claim と DB の値が食い違ったとき、どちらを信じるかを決める処理を設計段階で消しておきたい。

## 検討した選択肢
| 選択肢 | 利点 | 欠点 | 採用しなかった理由 |
| --- | --- | --- | --- |
| token のカスタム claim に role を載せる | リクエスト毎の DB 参照が不要 | role 変更が token 失効まで反映されない。role の正本が token と DB の2か所になる | 不一致時の裁定処理が新たに必要になるため |
| DB（users.role）を正本にする | role 変更が即時反映される。正本が1か所。token は本人確認のみに使う | 認可判定のたびに users を1回参照する | （採用） |

## 決定
token は認証（ユーザーの同定）のみに使い、認可は token の subject → `users.external_id` で users 行を解決し、`users.role` で access matrix を評価する。role を token に複製しない。subject に対応する users 行が無い場合は 401 とし、ユーザーの自動作成は行わない（登録は seed と管理画面に限定する）。

## 検証

| 方法 | 対象 | 結果 |
| --- | --- | --- |
| `docs/verification.md` の認証・認可項目 | 未登録 subject、role 別アクセス制御、manager 限定 API | 401 / 404 / manager 限定の期待結果を記録 |
| `AUTH_MODE=clerk` でサインイン後に画面操作 | `/api/me`、ダッシュボード、顧客詳細、サインアウト | API 200 とサインアウト後の画面遷移を記録 |
| README と API 応答の確認 | 認証 provider の subject 生値 | 公開文書と通常応答に subject 生値を返さないことを確認 |

## 影響
- 楽になる: role 変更・権限剥奪が次のリクエストから即時に効く。token 再発行や失効待ちを考えなくてよい
- トレードオフ: 認可判定のたびに users への参照が1回入る（ローカル SQLite の主キー/UNIQUE 参照であり、この規模では実測上の問題になりにくい。問題になった時点で計測して判断する）
