# 設計判断ログ

このディレクトリには、重要な設計判断を ADR として残します。

## ADR一覧

- [ADR-0001: 認可の role 正本をデータベースに置く](0001-role-source-of-truth-in-db.md)
- [ADR-0002: Agentの書き込みを承認制にする](0002-human-approval-for-agent-actions.md)
- [ADR-0003: Agentフローをサーバ側固定にする](0003-server-side-fixed-agent-workflow.md)
- [ADR-0004: citationをrun時点の根拠スナップショットに紐づける](0004-agent-citation-snapshot-and-retention.md)
- [ADR-0005: SQLite FTS5検索でdoc ACLを同じSQLに含める](0005-sqlite-fts5-acl-search.md)
- [ADR-0006: SSE再接続の正本をevent_seqにする](0006-sse-event-seq-reconnect.md)
