import { useEffect, useRef, useState } from 'react'

// 入力値変更から保存までの間隔
export const DRAFT_DEBOUNCE_MS = 500

type StorageLike = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>

type Options<T> = {
  key: string
  // 監視対象のフォーム値（変更のたびに渡す）
  values: T
  // 保存を有効にするか（編集対象のロード前は無効にする等）
  enabled: boolean
  storage?: StorageLike
}

type Result<T> = {
  // マウント時に存在した下書き（復元確認に使う。null = なし）
  pendingDraft: T | null
  // 復元確認への応答（復元はしないがプロンプトを閉じる = discard）
  discardDraft: () => void
  acceptDraft: () => void
  // 保存成功時に呼ぶ（キー削除）
  clearDraft: () => void
}

// フォーム下書きを localStorage に debounce 保存する。
// 自動復元はせず、呼び出し側が pendingDraft を使って確認 UI を出す
function readDraft<T>(storage: StorageLike, key: string): T | null {
  const raw = storage.getItem(key)
  if (raw === null) {
    return null
  }
  try {
    return JSON.parse(raw) as T
  } catch {
    return null
  }
}

export function useFormDraft<T>({
  key,
  values,
  enabled,
  storage = window.localStorage,
}: Options<T>): Result<T> {
  const [pendingDraft, setPendingDraft] = useState<T | null>(() =>
    readDraft<T>(storage, key),
  )

  // key が変わったら読み直す（認証でユーザー ID が確定しキーが変わるケース）。
  // render 中の derived state 更新パターン（effect 経由だと 1 render 古い値が見える）
  const [loadedKey, setLoadedKey] = useState(key)
  if (key !== loadedKey) {
    setLoadedKey(key)
    setPendingDraft(readDraft<T>(storage, key))
  }

  const timerRef = useRef<number | undefined>(undefined)
  const storageRef = useRef(storage)
  const promptOpen = pendingDraft !== null

  useEffect(() => {
    // 復元確認に答える前は上書き保存しない（リロード直後に下書きが消えるのを防ぐ）
    if (!enabled || promptOpen) {
      return
    }
    window.clearTimeout(timerRef.current)
    timerRef.current = window.setTimeout(() => {
      storageRef.current.setItem(key, JSON.stringify(values))
    }, DRAFT_DEBOUNCE_MS)
    return () => window.clearTimeout(timerRef.current)
  }, [key, values, enabled, promptOpen])

  const clearDraft = () => {
    window.clearTimeout(timerRef.current)
    storageRef.current.removeItem(key)
  }

  return {
    pendingDraft,
    discardDraft: () => {
      clearDraft()
      setPendingDraft(null)
    },
    acceptDraft: () => setPendingDraft(null),
    clearDraft,
  }
}
