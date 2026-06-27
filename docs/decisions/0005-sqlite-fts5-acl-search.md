# ADR-0005: SQLite FTS5検索でdoc ACLを同じSQLに含める

## ステータス
採用済み

## 背景

ナレッジ検索で権限外の文書を取得してから後段で除外すると、LLMへ渡す前の境界が曖昧になる。検索時点で文書側ACLを適用する必要がある。

## 検討した選択肢

| 選択肢 | 利点 | 欠点 | 採用しなかった理由 |
| --- | --- | --- | --- |
| FTS結果を取得後にPythonでACLを判定 | 実装しやすい | 権限外の本文を一度取得する | 検索時点の漏えい防止にならない |
| `knowledge_docs` をjoinしてSQLでACLを判定 | 権限外の文書を検索結果に出さない | SQLが長くなる | データ境界を明確にできる |

## 決定

FTS5検索は `knowledge_chunks_fts`、`knowledge_chunks`、`knowledge_docs` をjoinし、文書側ACLを同じSQLで評価する。JSON配列の判定は `json_each()` を使う。

## 検証

| 方法 | 対象 | 結果 |
| --- | --- | --- |
| `backend/.venv/Scripts/python.exe -m pytest` | private doc、role別doc、source type、検索時のdoc ACL | `docs/verification.md` に backend pytest の通過結果を記録 |

## 影響

SQLite FTS5の `unicode61` は日本語部分一致に制約がある。日本語検索品質を高める場合は、別方式との比較が必要になる。
