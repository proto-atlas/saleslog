# ADR-0006: SSE再接続の正本をevent_seqにする

## ステータス
採用済み

## 背景

Agent進捗は安全なイベントとして表示する。再接続時に重複や欠落を避けるため、run内で単調増加するカーソルが必要になる。

## 検討した選択肢

| 選択肢 | 利点 | 欠点 | 採用しなかった理由 |
| --- | --- | --- | --- |
| `created_at` で再送範囲を決める | 実装しやすい | 同時刻や時計精度の影響を受ける | 順序の正本にしにくい |
| run内の `event_seq` を使う | 順序が明確 | カーソルテーブルが必要 | 再接続条件を検査しやすい |

## 決定

`agent_event_cursors` でrunごとの `last_event_seq` を持ち、event作成時に増加させる。SSEの `id:` は `agent_events.event_seq` とする。

## 検証

- `backend/.venv/Scripts/python.exe -m pytest`: 非整数・負数の `Last-Event-ID` を400、最大値超過を409として確認

## 影響

`agent_events` の保持期限後、古いカーソルで再接続する場合は状態再取得が必要になる。
