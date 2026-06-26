import { useEffect, useRef, type ReactNode } from 'react'
import { ClerkProvider, useAuth } from '@clerk/react'

import { setTokenProvider } from '../api/client'
import { authEnabled, clerkPublishableKey } from './authConfig'

// API クライアントへ Bearer token の取得手段を渡す（ClerkProvider の内側で使う）
function ApiTokenBridge() {
  const { getToken } = useAuth()
  useEffect(() => {
    setTokenProvider(() => getToken())
    return () => setTokenProvider(null)
  }, [getToken])
  return null
}

// サインアウト完了時に下書きを走査削除する
function DraftCleanupOnSignOut() {
  const { isSignedIn } = useAuth()
  const previousRef = useRef(isSignedIn)
  useEffect(() => {
    if (previousRef.current === true && isSignedIn === false) {
      const keys = Object.keys(window.localStorage).filter((key) =>
        key.startsWith('draft:visit:'),
      )
      for (const key of keys) {
        window.localStorage.removeItem(key)
      }
    }
    previousRef.current = isSignedIn
  }, [isSignedIn])
  return null
}

export function AppAuthProvider({ children }: { children: ReactNode }) {
  if (!authEnabled) {
    return <>{children}</>
  }
  return (
    <ClerkProvider
      publishableKey={clerkPublishableKey as string}
      afterSignOutUrl="/"
    >
      <ApiTokenBridge />
      <DraftCleanupOnSignOut />
      {children}
    </ClerkProvider>
  )
}
