# Agent セキュリティ

Agent機能は、生成結果をそのまま権限判断やDB確定書き込みに使わない。

## 認可

- run、artifact、source、approval、SSEはすべてrunの権限範囲を通す
- salesは自分が作成したrunのみ参照・操作できる
- managerは管理可能な顧客に紐づくrunを参照・操作できる
- 権限外は原則404を返す

## 書き込み

Agentは業務テーブルへ直接書き込まず、`agent_approvals` に書き込み候補を保存する。業務テーブルへの保存は、ユーザーが承認または編集承認した場合に限る。

## 冪等性

承認APIは `agent_approval_idempotency_records` で `approval_id + idempotency_key` を一意に扱う。同一keyの再送では保存済みresponseを返す。処理中recordがstaleになった場合は、業務レコードとの対応を確認してからfailure responseまたは修復結果を保存する。

## イベント記録とSSE

SSEには `safe_message_key`、許可済みparam、run / event のIDや状態などのイベントメタ情報だけを流す。顧客本文、活動本文、ナレッジ本文、メール本文、根拠抜粋、LLMの未加工出力、`lease_token`、`processing_owner` は含めない。

## ナレッジ検索

SQLite FTS5検索は `knowledge_chunks` と `knowledge_docs` をjoinし、文書側ACLを同じSQLで評価する。`allowed_user_ids_json`、`allowed_roles_json`、`source_types_json` の配列判定は `json_each()` を使う。

`KnowledgeVisibility.owner_team` は、現在のユーザーデータにチーム所属を持たないため検索・引用再確認ともに許可されない。チーム単位のナレッジ共有を使う場合は、ユーザーのチーム所属を保存し、検索ACLと引用再確認の両方へ同じ判定を追加する。
