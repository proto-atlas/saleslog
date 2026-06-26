# ADR-0004: citationをrun時点の根拠スナップショットに紐づける

## ステータス
採用済み

## 背景

顧客情報や活動履歴は後から変更される。Agent成果物の根拠を後で確認するには、run時点で参照したsourceのchecksumと短いexcerptを保存する必要がある。

## 検討した選択肢

| 選択肢 | 利点 | 欠点 | 採用しなかった理由 |
| --- | --- | --- | --- |
| 元テーブルだけを参照する | 保存量が少ない | 後から内容が変わると根拠が再現できない | 監査に弱い |
| run時点のsource情報を保存する | run時点の根拠を確認できる | 保持期限の管理が必要 | 根拠確認と保持期限を両立できる |

## 決定

`agent_run_sources` にsource checksum、char range、excerpt hash、短いexcerptを保存する。artifact側の `citations_json` にはexcerpt本文を重複保存しない。

## 検証

- `backend/.venv/Scripts/python.exe -m pytest`: citationの根拠スナップショットを含むartifact作成を確認

## 影響

保持期限後はexcerptをnull化できる。checksumと範囲情報は監査用に保持できる。
