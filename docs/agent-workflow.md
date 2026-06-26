# Agent ワークフロー

Agent run はHTTPリクエスト内で業務データの確定書き込みまで進めない。run作成後、DB状態を正本としてworker処理を進める。

## 実行前半

1. 顧客の権限範囲を確認する
2. `agent_runs.status = pending` でrunを作成する
3. workerがrunを `running` にする
4. 顧客情報、活動履歴、社内ナレッジを取得する
5. `agent_run_sources` に根拠スナップショットを保存する
6. 成果物を `agent_artifacts` に保存する
7. 書き込み候補を `agent_approvals.status = pending` で保存する
8. runを `waiting_for_approval` にする

同じユーザー、同じ顧客、同じworkflow、同じ目的のactive runが残っている場合、作成APIは新しいrunを作らず既存runを返す。レスポンスの `reused` が `true` の場合、画面は未完了の既存実行を表示する。

## 承認後

承認または編集承認では、payload検証、権限再確認、業務レコード作成、approval更新、idempotency response保存、run完了判定を同じ処理単位で行う。

Reject では業務テーブルへ書き込まず、対象approvalを `rejected` にする。全approvalが完了系状態になればrunは `completed` になる。

## SSE

`GET /api/agent-runs/{run_id}/events` は `Last-Event-ID` をrun内の `event_seq` として扱う。非整数・負数は400、現在runの最大 `event_seq` より大きい値は409を返す。
