import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import { AppRoot } from './AppRoot'
import { AppAuthProvider } from './auth/AuthProvider'
import { authEnabled } from './auth/authConfig'
import { AuthQueryCacheBoundary } from './auth/AuthQueryCacheBoundary'
import './index.css'

const queryClient = new QueryClient()
const app = authEnabled ? (
  <AuthQueryCacheBoundary>
    <AppRoot />
  </AuthQueryCacheBoundary>
) : (
  <QueryClientProvider client={queryClient}>
    <AppRoot />
  </QueryClientProvider>
)

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AppAuthProvider>{app}</AppAuthProvider>
  </StrictMode>,
)
