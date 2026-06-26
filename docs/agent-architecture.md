# Agent アーキテクチャ

Saleslog Agent は、顧客詳細画面から商談準備・フォローアップ・失注リスク確認を支援する機能である。顧客情報、活動履歴、社内ナレッジを参照し、商談ブリーフ、リスク、機会、確認質問、次アクション案、フォローアップ草案を作成する。

## 構成

- API: FastAPI router `agent_runs`
- 実行状態: `agent_runs`
- 実行イベント: `agent_events` と `agent_event_cursors`
- 根拠情報: `agent_run_sources`
- 成果物: `agent_artifacts`
- 承認: `agent_approvals`
- 承認冪等性: `agent_approval_idempotency_records`
- ナレッジ検索: `knowledge_docs`、`knowledge_chunks`、`knowledge_chunks_fts`

## 境界

LLM Provider は `AGENT_LLM_PROVIDER` で `mock` / `anthropic` / `openai` を切り替える。外部LLMの標準運用は `anthropic` のみ、ローカル開発・自動テストは決定的な出力を返す `mock` を使う。`openai` は互換用の実装として残しているが通常運用対象ではなく、既定modelを持たない。使う場合は `OPENAI_MODEL` を明示する。認可、DB書き込み、citation確定、承認状態遷移、冪等性、run完了判定はサーバ側で処理する。

## イベント記録

`agent_events` には `safe_message_key` と許可済みparamだけを保存する。顧客本文、活動本文、ナレッジ本文、モデル入力文、LLMの未加工出力、`lease_token`、`processing_owner` は保存しない。

## 既知の制約

- 外部LLMの実API疎通には、対象providerのAPIキーとモデル設定が必要。
- citation validation は excerpt / checksum / claim対応など機械的に判定できる範囲を扱う。
- 日本語ナレッジ検索は SQLite FTS5 `unicode61` の制約を受ける。
