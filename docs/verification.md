# 検証記録

各項目は「方法・対象・結果」で記録する。数値は記載日時点の計測値。

## 最終確認サマリ（2026-06-26）

| 方法 | 対象 | 結果 |
|---|---|---|
| `backend/.venv/Scripts/python.exe -m ruff check .` | backend lint | `All checks passed!` |
| `backend/.venv/Scripts/python.exe -m mypy app` | backend typecheck | `Success: no issues found in 34 source files` |
| `backend/.venv/Scripts/python.exe -m pytest backend/tests` | backend 全体。`CLERK_AUDIENCE` 必須化、読み取り専用モード中はAgent根拠のGETでDBを更新しないこと、Agent、認証、認可、migration、seed、顧客・活動記録API | **257 passed, 1 warning** |

frontend 全体E2Eの直近記録は下記の「E2E DB準備位置の再確認」セクションに残す。

## 自動テスト（2026-06-06〜07 実施）

| 方法 | 対象 | 結果 |
|---|---|---|
| `.venv/Scripts/pytest`（backend） | API 契約・バリデーション（422 から送信生値を除去）・カスケード削除・JST 境界集計・読み取り専用モード・JWT 検証（署名 / exp / nbf / azp / 未登録 sub / JWKS 取得失敗の各 401）・ロール別アクセス制御（活動履歴・最終訪問日時・入力漏れ一覧のスコープ含む）・ユーザー管理 API | **91 passed** |
| `npm run test`（frontend） | URL クエリ同期・日時変換・下書き保存（キー変更時の再読込含む）・スキーマ・422 マッピングのユニット 40 + 全 Storybook story のコンポーネントテスト 23 | **63 passed**（40 + 23） |
| `npm run e2e` | 主要導線 11 シナリオ（Agentタブでの商談準備生成を含む） + アクセシビリティ検査 8 画面（seed 済み + 空 DB の二重サーバ構成） | **22 passed** |
| `npm run test:coverage` | ロジックモジュール（lib / hooks / フォームスキーマ / 列挙）の v8 カバレッジ | **Statements 93.5% / Branches 89.81%**（しきい値 80% を充足） |
| `npm run typecheck` / `npm run lint` | frontend 全体（TypeScript strict / ESLint） | エラー 0 |

## Agent 検証（2026-06-16〜18 実施）

| 方法 | 対象 | 結果 |
|---|---|---|
| `backend/.venv/Scripts/python.exe -m pytest` | backend API、認証既定値のfail-closed、Agent run、承認、承認編集payload上限（余計なキー・深さ・byte size・キー数・配列長・文字列長・claim_ids・422非反射）、冪等性、SSE `Last-Event-ID`、FTS5権限境界、LLM Provider設定、mock復帰時の外部LLM数値env無視、実Providerの数値env不正・認証失敗・モデル不一致のerror code分離、Windows向けLLM HTTP transport、evaluation 51ケース | **194 passed, 1 warning** |
| `backend/.venv/Scripts/python.exe -m pytest tests/test_agent.py tests/test_auth.py` | Agent本体、承認、承認編集payload上限（余計なキー・深さ・byte size・キー数・配列長・文字列長・claim_ids・422非反射）、冪等性、SSE、FTS5、LLM Provider設定、Windows向けLLM HTTP transport、認証既定値のfail-closed、明示 `AUTH_MODE=fixed` のローカル認証なし動作 | **53 passed, 1 warning** |
| `backend/.venv/Scripts/python.exe -m pytest tests/test_agent.py tests/test_agent_evaluation.py` | Agent本体、承認、承認編集payload上限（余計なキー・深さ・byte size・キー数・配列長・文字列長・claim_ids・422非反射）、冪等性、SSE、FTS5、LLM Provider設定、OpenAI / Anthropic provider request body、Windows向けLLM HTTP transport、evaluation 51ケース | **102 passed, 1 warning** |
| `backend/.venv/Scripts/python.exe -m pytest tests/test_agent_evaluation.py` | Agent evaluation 51ケース、case schema、業務レコード差分、fault hook名 | **61 passed, 1 warning** |
| `backend/.venv/Scripts/python.exe -m app.export_openapi` + `npm run gen:api` | OpenAPI JSON と frontend 生成型 | exit 0 |
| `npm.cmd run typecheck` | frontend TypeScript | exit 0 |
| `npm.cmd run lint` | frontend ESLint | exit 0 |
| 手動確認: `AGENT_LLM_PROVIDER=anthropic` + Anthropicモデル設定でAgent実行 | Anthropic 実API、PowerShell HTTP transport、非strict tool use、サーバ側 `AgentLLMOutput` 検証、承認保存 | **直近4件（run #33〜#36）が `provider=anthropic` / `waiting_for_approval` / `last_error_code=null`。latency 35.8〜50.4秒。run #36 は approval #30/#31 が `persisted`、`persist_error=null`、run status `completed`** |
| `npx vitest run src/api/client.test.ts src/pages/customers/customerAgentPanel.test.ts --browser.enabled=false` | AgentパネルSSE表示、承認payload検証、サーバ側検証エラー時の承認不可、source link、保存後リンク、期限切れ判定、Agent API error body の表示用抽出 | **2 files / 29 tests passed** |
| `npm run test` | frontend unit + Storybook project | **unit 10 files / 69 tests passed、Storybook 11 files / 23 tests passed** |
| `npm run e2e` | frontend production build、既存主要導線、Agentタブでの商談準備生成、承認後の業務レコード作成、axe serious / critical 検査 | **22 passed**。Viteのchunk size警告あり |
| `npm run build` | frontend production build | exit 0。Viteのchunk size警告あり |
| `$env:DATABASE_URL='sqlite:///:memory:'` + `.venv/Scripts/alembic.exe upgrade head` | Alembic migration | exit 0 |
| `git diff --check` | 空白エラー確認 | exit 0（LF→CRLF警告のみ） |

`npm run test` はブラウザ接続timeoutが1回発生したが、単独再実行で上表の結果になった。

外部LLM接続は、OpenAI / Anthropic の request payload と response parsing を pytest で確認した。Anthropic は実APIで直近4件のAgent run成功を確認した。OpenAI は request payload の自動テスト対象だが、実API疎通は未確認。OpenAI の JSON schema strict 指定は Anthropic とは別経路のため、OpenAI切替時は実APIで再確認する。

## 権限境界の再検証（2026-06-19 実施）

| 方法 | 対象 | 結果 |
|---|---|---|
| `backend/.venv/Scripts/python.exe -m pytest tests/test_agent.py -q` | Agent run、根拠 source ACL 再確認、承認一覧・編集・承認・却下の権限境界、冪等性、LLM Provider設定 | **51 passed, 1 warning** |
| `backend/.venv/Scripts/python.exe -m pytest -q` | backend 全体（顧客削除、ユーザー管理、Agent、認証、評価ケースを含む） | **206 passed, 1 warning** |
| `frontend/node_modules/.bin/tsc.cmd -b --noEmit` | frontend TypeScript | exit 0 |
| `frontend/node_modules/.bin/vitest.cmd run --project=unit` | frontend unit project（顧客フォーム変換、Agentパネル、API client、日付変換を含む） | **10 files / 70 tests passed** |
| `frontend/node_modules/.bin/eslint.cmd .` | frontend ESLint | exit 0 |
| `frontend/node_modules/.bin/vite.cmd build` | frontend production build | exit 0。Viteのchunk size警告あり |

## 認証・並行投入強化後の再検証（2026-06-19 実施）

| 方法 | 対象 | 結果 |
|---|---|---|
| `backend/.venv/Scripts/python.exe -m pytest tests/test_auth.py tests/test_agent.py -q` | Clerk JWT 検証（署名 / exp / nbf / azp / sub / audience、任意設定時の issuer）と Agent run active 重複制約 | **72 passed, 1 warning** |
| `$env:DATABASE_URL='sqlite:///:memory:'` + `backend/.venv/Scripts/alembic.exe upgrade head` | Alembic migration（Agent run active 重複防止 index を含む） | exit 0 |
| `backend/.venv/Scripts/python.exe -m pytest -q` | backend 全体 | **215 passed, 1 warning** |
| `frontend/node_modules/.bin/vitest.cmd run src/pages/customers/customerSalesRoleUi.test.tsx --project=unit` | sales ロールの顧客詳細削除UI非表示と顧客作成 `owner_id` 省略 | **1 file / 2 tests passed** |
| `frontend/node_modules/.bin/vitest.cmd run --project=unit` | frontend unit project | **11 files / 72 tests passed** |
| `frontend/node_modules/.bin/vitest.cmd run --project=storybook` | Storybook project | **11 files / 23 tests passed** |
| `frontend/node_modules/.bin/tsc.cmd -b --noEmit` | frontend TypeScript | exit 0 |
| `frontend/node_modules/.bin/eslint.cmd .` | frontend ESLint | exit 0 |
| `frontend/node_modules/.bin/vite.cmd build` | frontend production build | exit 0。Viteのchunk size警告あり |

## 認証主体切替・ロールUI追加検証（2026-06-19 実施）

| 方法 | 対象 | 結果 |
|---|---|---|
| `frontend/node_modules/.bin/vitest.cmd run src/auth/AuthQueryCacheBoundary.test.tsx --project=unit` | 認証ユーザー変更・サインアウト時の TanStack Query cache 削除、認証主体切替中に古い cache を描画しないこと | **1 file / 3 tests passed** |
| `frontend/node_modules/.bin/vitest.cmd run src/pages/customers/customerSalesRoleUi.test.tsx --project=unit` | sales ロールの顧客詳細削除UI非表示、顧客作成 `owner_id` 省略、顧客一覧 `owner_id` 非送信、活動記録一覧 `user_id` 非送信 | **1 file / 5 tests passed** |
| `frontend/node_modules/.bin/tsc.cmd -b --noEmit` | frontend TypeScript | exit 0 |
| `frontend/node_modules/.bin/eslint.cmd .` | frontend ESLint | exit 0 |
| `frontend/node_modules/.bin/vitest.cmd run --project=unit` | frontend unit project | **12 files / 77 tests passed** |
| `frontend/node_modules/.bin/vitest.cmd run --project=storybook` | Storybook project | **11 files / 23 tests passed** |
| `backend/.venv/Scripts/python.exe -m pytest -q` | backend 全体 | **219 passed, 1 warning** |
| 一時 SQLite DB + `backend/.venv/Scripts/alembic.exe upgrade head` | Alembic migration（fresh SQLite DB） | exit 0 |
| 一時 SQLite DB + `backend/.venv/Scripts/alembic.exe upgrade head` → `downgrade base` → `upgrade head` | Alembic migrationの往復確認（fresh SQLite DB） | exit 0 |
| `NPM_CONFIG_PREFIX=<Node.js install dir>` + `npm run e2e` | frontend production build、Playwright E2E、seeded/empty DB導線、axe serious / critical 検査 | **22 passed**。Viteのchunk size警告あり |
| `git diff --check` | 空白エラー確認 | exit 0（LF→CRLF警告のみ） |

## worker timeout競合・Anthropic標準設定の再検証（2026-06-20 実施）

| 方法 | 対象 | 結果 |
|---|---|---|
| `backend/.venv/Scripts/python.exe -m pytest tests/test_agent.py::test_worker_stops_when_database_status_is_failed tests/test_agent.py::test_worker_cancel_check_reads_database_status tests/test_agent.py::test_agent_llm_settings_defaults_to_anthropic_model_and_requires_openai_model tests/test_agent.py::test_openai_provider_requires_explicit_model tests/test_agent.py::test_openai_provider_uses_responses_token_param_name tests/test_agent.py::test_openai_request_body_uses_responses_json_schema -q` | worker timeoutで `failed` になったrunをstale workerがactive状態へ戻さないこと、キャンセル競合、Anthropic既定model、OpenAI providerの明示model必須化、OpenAI request body | **6 passed, 1 warning** |
| `backend/.venv/Scripts/python.exe -m ruff check .` | backend lint | `All checks passed!` |
| `backend/.venv/Scripts/python.exe -m mypy` | backend typecheck | `Success: no issues found in 34 source files` |
| `backend/.venv/Scripts/python.exe -m pytest -q` | backend 全体 | **227 passed, 1 warning** |
| `rg` による旧model名・読みにくいmodel文字列の残存確認 | 成果物対象のコード・README・docs・CI・frontendに残る旧OpenAI既定model名と読みにくいAnthropic model文字列 | ヒットなし |
| `git diff --check` | 空白エラー確認 | exit 0（LF→CRLF警告のみ） |
| Web確認: OpenAI公式 Models page（`https://platform.openai.com/docs/models`、確認日 2026-06-20） | OpenAI provider の旧既定候補 | 公式Models page内で旧既定候補を確認できなかったため、OpenAI providerの既定modelを空文字にし、利用時は `OPENAI_MODEL` 明示必須に変更 |
| Web確認: Anthropic公式 Models overview（`https://platform.claude.com/docs/en/about-claude/models/overview`、確認日 2026-06-21） | Anthropic標準model ID | `claude-haiku-4-5-20251001` が Claude API ID として掲載されていることを確認 |

## Agent・認証cache・公開表現の追加検証（2026-06-20 実施）

| 方法 | 対象 | 結果 |
|---|---|---|
| `backend/.venv/Scripts/python.exe -m pytest tests/test_users.py::test_external_id_whitespace_is_422 tests/test_users.py::test_external_id_is_trimmed_before_duplicate_check tests/test_agent.py::test_worker_does_not_hold_transaction_during_llm_call tests/test_agent.py::test_worker_provider_error_does_not_overwrite_cancelled_run tests/test_agent.py::test_agent_event_seq_uses_database_reserved_sequence tests/test_agent.py::test_agent_llm_output_limits_top_level_lists tests/test_agent.py::test_agent_llm_output_limits_claim_ids tests/test_agent.py::test_stale_running_worker_timeout_creates_failed_event tests/test_agent.py::test_agent_llm_settings_blank_anthropic_model_uses_default -q` | external_id 正規化、LLM中キャンセル競合、provider error時のterminal状態保持、SSE event採番、LLM出力上限、timeout event、空白 Anthropic model | **9 passed, 1 warning** |
| `backend/.venv/Scripts/python.exe -m pytest tests/test_migrations.py -q` | 既存DB migrationのactive run重複・active run上限の異常系 | **2 passed, 1 warning** |
| `backend/.venv/Scripts/python.exe -m ruff check .` | backend lint | `All checks passed!` |
| `backend/.venv/Scripts/python.exe -m mypy` | backend typecheck | `Success: no issues found in 34 source files` |
| `backend/.venv/Scripts/python.exe -m pytest -q` | backend 全体 | **238 passed, 1 warning** |
| `backend/.venv/Scripts/python.exe -m app.export_openapi` + `npm run gen:api` | OpenAPI JSON と frontend 生成型 | exit 0 |
| `node_modules/.bin/tsc.cmd -b --noEmit` | frontend TypeScript | exit 0 |
| `node_modules/.bin/eslint.cmd .` | frontend ESLint | exit 0 |
| `frontend/node_modules/.bin/vitest.cmd run src/auth/AuthQueryCacheBoundary.test.tsx --project=unit` | 認証主体ごとの QueryClient 切替、サインアウト時の cache 分離、認証ロード中の子描画抑止 | **1 file / 3 tests passed** |
| `npm run test` | frontend unit + Storybook project | **unit 12 files / 78 tests passed、Storybook 11 files / 23 tests passed** |
| `npm run build` | frontend production build | exit 0。Viteのchunk size警告あり |
| `git diff --check` | 空白エラー確認 | exit 0（LF正規化予告のみ） |
| `rg` による公開可視範囲の語句確認 | 環境依存パス表記、secret形状、合成データ名の残存 | ヒットなし |

## 承認編集version必須化・E2E再検証（2026-06-21 実施）

| 方法 | 対象 | 結果 |
|---|---|---|
| `backend/.venv/Scripts/python.exe -m app.export_openapi` + `npm run gen:api` | `AgentApprovalPatch.version` 必須化後のOpenAPI JSON と frontend 生成型 | exit 0。生成型は `version: number` |
| `backend/.venv/Scripts/python.exe -m pytest tests/test_agent.py::test_agent_approval_edit_is_404_when_source_acl_changed tests/test_agent.py::test_edit_agent_approval_requires_version tests/test_agent.py::test_edit_agent_approval_rejects_stale_version -q` | 承認編集APIのversion必須、古いversion拒否、source ACL変更時の404 | **3 passed, 1 warning** |
| `backend/.venv/Scripts/python.exe -m ruff check .` | backend lint | `All checks passed!` |
| `backend/.venv/Scripts/python.exe -m mypy` | backend typecheck | `Success: no issues found in 34 source files` |
| `backend/.venv/Scripts/python.exe -m pytest -q` | backend 全体 | **244 passed, 1 warning** |
| `npm run typecheck` | frontend TypeScript | exit 0 |
| `npm run lint` | frontend ESLint | exit 0 |
| `npm run test` | frontend unit + Storybook project | **unit 12 files / 80 tests passed、Storybook 11 files / 23 tests passed** |
| `node_modules/.bin/playwright.cmd test a11y.spec.ts --project=seeded` | axe serious / critical 検査 8画面。`nav, main` を対象にし、ナビゲーションと主要領域の表示を事前確認 | **8 passed** |
| `npm run e2e` | frontend production build、Playwright E2E、seeded/empty DB導線、`nav, main` 対象のaxe serious / critical 検査 | **22 passed**。Viteのchunk size警告あり |
| `git diff --check` | 空白エラー確認 | exit 0（CRLF→LF警告のみ） |
| `rg` による公開可視範囲の語句確認 | 旧model表現、環境依存パス表記、余計なコメント空白 | ヒットなし |
| `netstat -ano | findstr ":8000 :8010 :4173 :4183 :5173"` | E2E後のローカルサーバー残存確認 | LISTENINGなし（TIME_WAITのみ） |

## 生成型・承認期限処理・a11y検証の再確認（2026-06-21 実施）

| 方法 | 対象 | 結果 |
|---|---|---|
| `backend/.venv/Scripts/python.exe -m app.export_openapi` + `npm run gen:api` | OpenAPI JSON と frontend 生成型 | exit 0。生成型のAPIパスは `"/api/users/{user_id}"` の通常表記 |
| `backend/.venv/Scripts/python.exe -m pytest tests/test_agent_evaluation.py::test_agent_evaluation_case_passes[approval_expiration_finalizes_run] -q` | 期限切れ承認がrunを完了状態へ遷移させる評価ケース | **1 passed, 1 warning** |
| `backend/.venv/Scripts/python.exe -m pytest -q` | backend 全体 | **248 passed, 1 warning** |
| `backend/.venv/Scripts/python.exe -m ruff check` | backend lint | `All checks passed!` |
| `backend/.venv/Scripts/python.exe -m mypy app` | backend typecheck | `Success: no issues found in 34 source files` |
| `npm run typecheck` | frontend TypeScript | exit 0 |
| `npm run lint` | frontend ESLint | exit 0 |
| `npm run test` | frontend unit + Storybook project | **unit 12 files / 80 tests passed、Storybook 11 files / 23 tests passed** |
| `npm run e2e` | frontend production build、Playwright E2E、`nav, main` 対象のaxe serious / critical 検査、seeded/empty DB導線 | **22 passed**。Viteのchunk size警告あり |
| `Get-NetTCPConnection -LocalPort 8000,8010,4173,4183` | E2E後のローカルサーバー残存確認 | LISTENINGなし（TIME_WAITのみ） |

## E2E単独再実行（2026-06-21 実施）

| 方法 | 対象 | 結果 |
|---|---|---|
| `Get-NetTCPConnection -LocalPort 8000,8010,4173,4183` | E2E前のローカルサーバー残存確認 | LISTENINGなし |
| `npm run e2e` | frontend production build、Playwright E2E、`nav, main` 対象のaxe serious / critical 検査、seeded/empty DB導線 | **22 passed**。Viteのchunk size警告あり |
| `Get-NetTCPConnection -LocalPort 8000,8010,4173,4183` | E2E後のローカルサーバー残存確認 | LISTENINGなし（TIME_WAITのみ） |

## E2E DB準備位置の再確認（2026-06-21 実施）

| 方法 | 対象 | 結果 |
|---|---|---|
| `backend/.venv/Scripts/python.exe -m pytest tests/test_seed.py -q` | seed CLI の `--reset-schema --empty` と既存 `reset()` | **2 passed, 1 warning** |
| `npm run e2e -- admin-users.spec.ts --project=seeded` | seeded project単体の管理ユーザー作成E2E | **1 passed**。DB未作成を示す `no such table: users` ログなし |
| `npm run e2e` | frontend production build、Playwright E2E、`nav, main` 対象のaxe serious / critical 検査、seeded/empty DB導線 | **22 passed**。Viteのchunk size警告あり |
| `Get-NetTCPConnection -LocalPort 8000,8010,4173,4183` | E2E後のローカルサーバー残存確認 | LISTENINGなし |
| `backend/.venv/Scripts/python.exe -m pytest -q` | backend 全体 | **249 passed, 1 warning** |
| `backend/.venv/Scripts/python.exe -m ruff check` | backend lint | `All checks passed!` |
| `backend/.venv/Scripts/python.exe -m mypy app` | backend typecheck | `Success: no issues found in 34 source files` |
| `npm run typecheck` | frontend TypeScript | exit 0 |
| `npm run lint` | frontend ESLint | exit 0 |
| `npm run test` | frontend unit + Storybook project | **unit 12 files / 80 tests passed、Storybook 11 files / 23 tests passed** |

## Agent実行再利用と出力言語指定（2026-06-21 実施）

| 方法 | 対象 | 結果 |
|---|---|---|
| `backend/.venv/Scripts/python.exe -m pytest tests/test_agent.py::test_duplicate_active_agent_run_returns_existing_run tests/test_agent.py::test_anthropic_request_body_日本語出力を指示する tests/test_agent.py::test_system_prompt_日本語自然文と識別子保持を明示する tests/test_agent.py::test_anthropic_request_body_omits_strict_for_large_schema -q` | 同一条件のactive run再利用レスポンス、Anthropic request bodyの日本語出力指定、strict tool use未使用 | **4 passed, 1 warning** |
| `backend/.venv/Scripts/python.exe -m pytest tests/test_agent.py -k "powershell_transport" -q` | PowerShell transport のUTF-8送信・UTF-8受信・HTTP error変換 | **5 passed, 75 deselected, 1 warning** |
| `backend/.venv/Scripts/python.exe -m ruff check app tests/test_agent.py` | backend lint | `All checks passed!` |
| `backend/.venv/Scripts/python.exe -m mypy app` | backend typecheck | `Success: no issues found in 34 source files` |
| `backend/.venv/Scripts/python.exe -m app.export_openapi` + `npm run gen:api` | OpenAPI JSON と frontend 生成型 | exit 0 |
| `npm run typecheck` | frontend TypeScript | exit 0 |
| `npm run lint` | frontend ESLint | exit 0 |
| `E2E_SEEDED_API_PORT=18000`、`E2E_EMPTY_API_PORT=18010`、`E2E_SEEDED_WEB_PORT=14173`、`E2E_EMPTY_WEB_PORT=14183` を指定して `npm run e2e -- agent.spec.ts --project=seeded` | 既存の8000番backendを停止せず、Agent実行作成、同一条件の既存run再利用表示、承認保存までのE2E | **1 passed**。Viteのchunk size警告あり |
| `Get-NetTCPConnection -LocalPort 18000,18010,14173,14183 -State Listen` | E2E後の代替ポートサーバー残存確認 | LISTENINGなし |

## Agent表示整理（2026-06-21 実施）

| 方法 | 対象 | 結果 |
|---|---|---|
| `node_modules/.bin/tsc.cmd -b --noEmit` | frontend TypeScript | exit 0 |
| `node_modules/.bin/eslint.cmd .` | frontend ESLint | exit 0 |
| `E2E_SEEDED_API_PORT=18000`、`E2E_EMPTY_API_PORT=18010`、`E2E_SEEDED_WEB_PORT=14173`、`E2E_EMPTY_WEB_PORT=14183` を指定して `npm run e2e -- agent.spec.ts --project=seeded` | Agentタブの実行、承認保存、内部イベント名と内部ID配列を表示しないこと | **1 passed**。Viteのchunk size警告あり |
| Playwrightで `http://127.0.0.1:19173/customers/1?tab=agent` を表示し、スクリーンショットを保存 | 商談アシスタントの表示確認 | `C:\tmp\saleslog-agent-ui-review.png` を保存。画面内の `step_completed` と `claim_ids` は 0 件 |
| `Get-NetTCPConnection -LocalPort 18000,18010,14173,14183 -State Listen` | E2E後の代替ポートサーバー残存確認 | LISTENINGなし |

## Agent根拠詳細表示の整理（2026-06-22 実施）

| 方法 | 対象 | 結果 |
|---|---|---|
| `node_modules/.bin/tsc.cmd -b --noEmit` | frontend TypeScript | exit 0 |
| `node_modules/.bin/eslint.cmd .` | frontend ESLint | exit 0 |
| `node_modules/.bin/vitest.cmd run src/pages/customers/customerAgentPanel.test.ts --project=unit --browser.enabled=false` | Agent承認payload helper、差分判定、期限切れ判定 | **1 file / 25 tests passed** |
| `E2E_SEEDED_API_PORT=18000`、`E2E_EMPTY_API_PORT=18010`、`E2E_SEEDED_WEB_PORT=14173`、`E2E_EMPTY_WEB_PORT=14183` を指定して `npm run e2e -- agent.spec.ts --project=seeded` | 根拠の詳細ボタンで詳細パネルが開くこと、活動ログ編集画面へ自動遷移しないこと、引用に紐づかない根拠で空の関連主張文を表示しないこと | **1 passed**。Viteのchunk size警告あり |
| `Get-NetTCPConnection -LocalPort 18000,18010,14173,14183 -State Listen` | E2E後の代替ポートサーバー残存確認 | LISTENINGなし |

## Agent結果復元と戻り導線（2026-06-22 実施）

| 方法 | 対象 | 結果 |
|---|---|---|
| `backend/.venv/Scripts/python.exe -m pytest tests/test_agent.py::test_list_customer_agent_runs_returns_recent_runs tests/test_agent.py::test_list_customer_agent_runs_sales_sees_own_runs -q` | 顧客別Agent実行履歴API、salesユーザーの自分の実行のみ表示 | **2 passed, 1 warning** |
| `backend/.venv/Scripts/python.exe -m app.export_openapi` + `npm run gen:api` | OpenAPI JSON と frontend 生成型 | exit 0 |
| `node_modules/.bin/tsc.cmd -b --noEmit` | frontend TypeScript | exit 0 |
| `node_modules/.bin/eslint.cmd .` | frontend ESLint | exit 0 |
| `node_modules/.bin/vitest.cmd run src/pages/customers/customerAgentPanel.test.ts --project=unit --browser.enabled=false` | Agent承認payload helper、差分判定、期限切れ判定 | **1 file / 25 tests passed** |
| `E2E_SEEDED_API_PORT=18000`、`E2E_EMPTY_API_PORT=18010`、`E2E_SEEDED_WEB_PORT=14173`、`E2E_EMPTY_WEB_PORT=14183` を指定して `npm run e2e -- agent.spec.ts --project=seeded` | Agentタブと選択runのURL復元、根拠詳細から活動ログ編集画面へ移動後にAgent結果へ戻る導線、戻った後の生成結果表示 | **1 passed**。Viteのchunk size警告あり |
| `Get-NetTCPConnection -LocalPort 18000,18010,14173,14183 -State Listen` | E2E後の代替ポートサーバー残存確認 | LISTENINGなし |

## 認証・認可（2026-06-06 実施）

自動テスト（pytest に含む）:

- JWT 検証: ローカル生成の RSA 鍵ペアでトークンを作成し、正当なトークンの受理と、署名不正・期限切れ（exp）・有効化前（nbf）・azp 欠落・azp 不一致・未登録 sub・JWKS 取得失敗の各ケースで 401 になることを検査（11 件）
- 失敗理由の非漏えい: 401 応答の本文が `{"detail": "Unauthorized"}` のみで、失敗理由を含まないことを検査
- ロール別アクセス制御: sales ロールが他者の顧客・活動記録に 404、一覧が自分の範囲に絞られること、クエリでの範囲拡大が無効なこと、ダッシュボード集計が自分の範囲に縮退することを検査（10 件）
- ユーザー管理 API: manager 限定（sales は 404）、自分自身の役割変更・紐付け変更の拒否（自己締め出し防止）、紐付けの重複・空文字の拒否、紐付け状況（linked）を manager のみに返すことを検査。複数 manager 時の降格可否も検査（最後の 1 人の降格拒否分岐は、操作者自身が manager である限り自己変更拒否が先に効くため、防御的実装として保持）

手動確認（Clerk 実環境・`AUTH_MODE=clerk`）:

- 方法: バックエンドを `AUTH_MODE=clerk` + JWKS URL + 許可 origin + audience 指定で起動し、Clerk のテストアカウントでサインイン
- 結果: サインイン画面からサインイン後、`/api/me`・ダッシュボード・顧客詳細の API が 200。サインアウトでサインイン画面に戻り、下書きが破棄される
- azp 検査: 別 origin を許可リストから外した状態で 401 になることを確認

手動確認（sales ロールの表示範囲・2026-06-07）:

- 方法: 同アカウントを sales ユーザー（id=2）へ紐付け替えて localhost でサインインし、画面を操作
- 結果: 顧客詳細の活動履歴が自分の記録のみになること、活動記録の編集保存が未保存確認なしで顧客詳細へ遷移することを確認
- 追加検査:
  - 顧客詳細の活動履歴 API が、sales では自分の記録のみを返すことを pytest で検査
  - 活動記録の編集保存後、未保存確認を出さずに顧客詳細へ遷移することを E2E で検査

## アクセシビリティ（axe 自動検査・2026-06-06 実施）

- 方法: `@axe-core/playwright` を E2E（`e2e/a11y.spec.ts`）に組み込み、各画面の `nav, main` の描画完了後に検査
- 対象: `/`・`/customers`・`/customers/1`・`/visits`・`/visits/new`・`/visits/1/edit`・`/map`・`/admin/users` の 8 画面の `nav, main`
- 判定基準: serious / critical の違反 0 件
- 結果: **8 画面すべて違反 0 件**
- 注: 自動検査で検出できる範囲の確認であり、すべてのアクセシビリティ品質を保証するものではない。サインイン画面は認証有効時のみ表示される外部コンポーネントのため対象外

## Lighthouse（デスクトップ preset・2026-06-06 実施）

- 方法: production build（`vite build` → `vite preview` :4173）+ seed 投入済み API（:8000）を localhost で起動し、Lighthouse CLI（`--preset=desktop`）で計測
- 結果:

| 画面 | Performance | Accessibility | Best Practices |
|---|---|---|---|
| `/`（ダッシュボード） | 100 | 100 | 100 |
| `/customers`（一覧） | 99 | 100 | 100 |
| `/customers/1`（詳細） | 98 | 100 | 100 |

- 注: 計測値は実行環境・時点に依存する参考値
