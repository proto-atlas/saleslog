# Agent 検証

Agent機能は、外部LLMの文章品質だけではなく、業務アプリ内の実行境界を検査対象にする。

## 評価対象

- サーバ側固定フロー
- 人間承認
- 冪等性と二重保存防止
- 主張ごとの引用検査
- ナレッジ検索のSQL ACL
- 安全なイベントとSSE再接続
- 根拠抜粋の保持
- sales / manager の権限境界
- Providerの分離とMock実行

## 評価ケース

backendの `app.agent.evaluation.REQUIRED_EVALUATION_CASES` に51件の必須ケースを登録している。pytestで件数、重複、schema項目、満点条件、probeの存在、業務レコード差分を確認し、欠落があればCIが失敗する。

主な分類は以下。

- 正常系: 商談準備、履歴不足、ナレッジなし
- citation: source不一致、抜粋不一致、checksum不一致、重要claim抽出
- approval: reject、approve、期限切れ、payload validation
- idempotency: in_progress、succeeded、failed、stale、lease競合
- auth: unauthorized customer/run、manager権限範囲、認可再確認
- knowledge: doc/chunk ACL、allowed user/role、source type、FTS5 query
- SSE: Last-Event-ID、cursor範囲、event_seq順序
- fault: persist中断、worker timeout、SSE event書き込み失敗
- UI/E2E: Agentタブから実行、結果、根拠、承認表示、承認後の業務レコード作成

## 故障注入

故障注入は `AGENT_FAULT_HOOKS` 環境変数で有効化する。hook名は `app.agent.faults.AGENT_FAULT_HOOKS` に固定し、pytestで全hook名が有効化できることを確認する。

対象hook:

- `db_transaction_failure_hook`
- `business_record_inserted_but_approval_update_failed_hook`
- `idempotency_record_created_then_process_crashed_hook`
- `idempotency_existing_in_progress_hook`
- `idempotency_lease_expired_while_original_process_alive_hook`
- `approval_payload_validation_failure_hook`
- `worker_heartbeat_stopped_hook`
- `sse_event_write_failed_hook`
- `fts5_match_syntax_error_hook`

## 実行方法

```bash
python -m pytest
npm run test
npm run e2e
```

CIではbackend pytest、frontend unit/Storybook、E2Eを実行し、OpenAPI生成型の差分も検査する。
