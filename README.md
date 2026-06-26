# Saleslog

外回り営業向けの顧客・活動記録管理アプリ。

顧客マスタと訪問・電話などの活動記録を1か所で扱い、ダッシュボードで「今日の予定」と「入力漏れ（予定日を過ぎたままの記録）」を可視化します。React + TypeScript のフロントエンドと FastAPI バックエンドによるフルスタック構成です。

[操作録画（約45秒）](docs/assets/saleslog-demo.webm)

公開デモは用意していません。顧客情報と Agent 実行履歴を扱う業務アプリのため、動作確認はローカル環境を前提にしています。

## 主な機能

- 顧客管理: 登録・編集・削除、名前検索（大文字小文字を区別しない部分一致）、エリア / ステータスでの絞り込み、ページネーション。manager は担当者でも絞り込めます。フィルタ状態は URL クエリと同期し、リロード・共有で再現できます
- 活動記録: 訪問・電話・メール・オンライン会議の記録と予定。編集中の離脱防止（確認ダイアログ）、入力途中の下書き保存（再訪問時に復元確認）
- ダッシュボード: 顧客総数・当月活動件数・入力漏れ件数、今日の予定、エリア別 / 担当者別の顧客件数と月次推移（グラフはライブラリ不使用の SVG 自前描画）
- エリア別ボード: エリアごとの顧客カード一覧で状況を俯瞰し、カードから詳細へ遷移
- 認証とロール別アクセス制御: Clerk によるサインインと、manager / sales のロール別データ範囲。sales は自分の担当顧客・自分の活動記録のみ閲覧・編集でき、範囲はサーバ側で強制します（クエリ指定では広げられず、権限外は 404）
- ユーザー管理画面（manager 限定): メンバーの追加・役割変更・サインインアカウントの紐付けと解除。最後の manager の降格や自分自身の役割変更は拒否します
- Agent: 顧客詳細から商談準備・フォローアップ・失注リスク確認を実行し、根拠付きの成果物と人間承認後の業務レコード保存を扱います
- 読み取り専用モード: 環境変数 `DEMO_READ_ONLY=true` で全書き込み API（POST / PATCH / DELETE）を 405 にします。確認用環境でデータを変更させないための設定です

## 技術構成

| 層 | 採用技術 |
|---|---|
| フロントエンド | React / TypeScript (strict) / Vite / React Router (data mode) / Tailwind CSS v4 / TanStack Query / React Hook Form / Zod |
| バックエンド | FastAPI / SQLAlchemy（同期） / Alembic / SQLite |
| 認証 | Clerk（`@clerk/react`） + PyJWT（JWKS 公開鍵による JWT 検証） |
| テスト | pytest / Vitest（browser mode） / Storybook + addon-vitest / Playwright |

設計上の要点:

- 型は OpenAPI を単一の真実源とし、`openapi-typescript` でフロントの型を生成（CI で再生成差分を検査）
- 列挙値は英小文字キーで永続化し、表示ラベルはフロントの定数マップで日本語化
- 日時は UTC で格納し、「今日 / 今月」の判定と表示は JST 基準
- バリデーションエラー（422）の応答から送信生値を除去し、画面・ログに反射させない
- 認可の正本はサーバ側 DB のロール。JWT は本人特定（`sub`）のみに使い、画面の出し分けは利便性、データ範囲の強制はサーバが行う
- 認証エラーは一律 401 のみを返し、失敗理由は応答に含めない（理由はサーバログのみ）
- `AUTH_MODE=fixed` で認証なしのローカル実行・E2E・CI を明示的に有効化し、未設定時は Clerk JWT 検証を要求
- Agent の業務レコード作成は承認後に限定し、冪等性キーで再送時の二重作成を防ぎます

Agent 関連ドキュメント:

- [Agent アーキテクチャ](docs/agent-architecture.md)
- [Agent ワークフロー](docs/agent-workflow.md)
- [Agent セキュリティ](docs/agent-security.md)
- [Agent 検証](docs/agent-evaluation.md)
- [設計判断](docs/decisions/)

Agent のLLM接続:

- 既定は `AGENT_LLM_PROVIDER=mock` で、ローカル実行と自動テスト向けに決定的な出力を返します
- 外部LLMの標準運用は Anthropic のみです。`AGENT_LLM_PROVIDER=anthropic`、`ANTHROPIC_API_KEY`、必要に応じて `ANTHROPIC_MODEL` を設定します。既定の Anthropic model は `claude-haiku-4-5-20251001` です。実API疎通は [検証記録](docs/verification.md) に記録した時点の結果です
- OpenAI provider は互換用の実装として残していますが、このプロジェクトの通常運用対象ではありません。既定modelは持たず、使う場合は `AGENT_LLM_PROVIDER=openai`、`OPENAI_API_KEY`、`OPENAI_MODEL` をすべて明示してください。OpenAI 実API疎通は未確認です

## ローカルでの実行

バックエンド（Python 3.12 以上）:

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"   # Windows（macOS/Linux は .venv/bin/pip）
.venv/Scripts/alembic upgrade head
.venv/Scripts/python -m app.seed        # 合成データを投入
$env:AUTH_MODE="fixed"                  # PowerShell。ローカル確認用の固定ユーザーを使う
.venv/Scripts/uvicorn app.main:app --port 8000
```

Agent run は API で作成され、worker が DB から pending run を取得して処理します。ローカル確認では API の BackgroundTasks でも動きますが、継続運用ではバックエンドとは別のターミナルで worker を常駐させてください。

```bash
cd backend
.venv/Scripts/python -m app.agent_worker
```

既存DBへAgent runのactive制約migrationを適用する場合、active状態の同一目的run重複、または同一ユーザーでactive runが5件を超えるデータがあるとmigrationは停止します。停止した場合は、該当runを業務上の状態に合わせて完了または失敗扱いに整理してから再実行してください。

確認SQL:

```sql
select user_id, customer_id, workflow_type, objective_hash, count(*) as active_count
from agent_runs
where status in ('pending', 'running', 'waiting_for_approval')
group by user_id, customer_id, workflow_type, objective_hash
having count(*) > 1;

select user_id, count(*) as active_count
from agent_runs
where status in ('pending', 'running', 'waiting_for_approval')
group by user_id
having count(*) > 5;
```

フロントエンド（Node.js 22 以上）:

```bash
cd frontend
npm ci
npm run dev   # http://localhost:5173（/api は 8000 へプロキシ）
```

### 認証を有効にする場合（任意）

`AUTH_MODE=fixed` を指定したローカル起動では、固定ユーザーとして全機能を試せます。公開環境や reverse proxy 配下では `AUTH_MODE=fixed` を使わず、`AUTH_MODE=clerk` を指定してください。Clerk 認証を有効にする手順:

1. Clerk のアプリケーションを作成し、publishable key を取得する
2. バックエンドを環境変数付きで起動する
   - `AUTH_MODE=clerk`（未設定時も `clerk` 扱い）
   - `CLERK_JWKS_URL=https://<your-app>.clerk.accounts.dev/.well-known/jwks.json`
   - `CLERK_AUTHORIZED_PARTIES=http://localhost:5173`（カンマ区切りで複数可）
   - `CLERK_AUDIENCE=saleslog-api`（JWT の `aud` と一致する値。カンマ区切りで複数可）
3. フロントエンドの `frontend/.env.development.local` に `VITE_CLERK_PUBLISHABLE_KEY=pk_test_...` を設定する
4. 初回のみ、サインインに使うアカウントの `sub`（user_xxx）を DB のユーザーに紐付ける

```bash
cd backend
.venv/Scripts/python -m app.link_user 1 user_xxxxxxxxxxxx
```

以降は manager のユーザー管理画面から他メンバーの紐付け・役割変更を行います。

## テスト

```bash
# バックエンド API テスト
cd backend
.venv/Scripts/python -m ruff check .
.venv/Scripts/python -m mypy
.venv/Scripts/pytest

# フロントエンド（ユニット + Storybook コンポーネントテスト）
cd frontend && npm run test

# E2E（バックエンド・フロントエンドのサーバ起動と seed 投入は自動）
cd frontend && npm run e2e

# カバレッジ（しきい値: statements / branches 80%）
cd frontend && npm run test:coverage
```

検証結果（実行コマンド・対象・結果の記録）は [docs/verification.md](docs/verification.md) を参照してください。

## デモデータについて

- 同梱の seed データはすべて合成（ダミー）です。実在の企業・人物とは関係ありません
- seed データはローカルで再作成できるため、操作確認後も初期状態に戻せます

## ライセンス

MIT License（再利用条件が明確な標準的ライセンスのため）。詳細は [LICENSE](LICENSE) を参照してください。
