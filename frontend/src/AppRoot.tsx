import { Show } from '@clerk/react'
import { RouterProvider } from 'react-router/dom'

import { authEnabled } from './auth/authConfig'
import { SignInScreen } from './auth/SignInScreen'
import { ToastProvider } from './components/Toast'
import { router } from './router'

export function AppRoot() {
  const app = (
    <ToastProvider>
      <RouterProvider router={router} />
    </ToastProvider>
  )
  if (!authEnabled) {
    return app
  }
  // 認証有効時は未サインインでアプリを描画しない
  return (
    <>
      <Show when="signed-in">{app}</Show>
      <Show when="signed-out">
        <SignInScreen />
      </Show>
    </>
  )
}
