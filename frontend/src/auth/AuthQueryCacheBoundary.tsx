import { useMemo, type ReactNode } from 'react'
import { useAuth } from '@clerk/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

function authIdentity(
  isSignedIn: boolean | undefined,
  userId: string | null | undefined,
  sessionId: string | null | undefined,
) {
  if (isSignedIn !== true) {
    return 'signed-out'
  }
  return `${userId ?? 'unknown'}:${sessionId ?? 'unknown'}`
}

type AuthQueryCacheBoundaryProps = {
  children: ReactNode
  createQueryClient?: () => QueryClient
}

function createDefaultQueryClient() {
  return new QueryClient()
}

export function AuthQueryCacheBoundary({
  children,
  createQueryClient = createDefaultQueryClient,
}: AuthQueryCacheBoundaryProps) {
  const { isLoaded, isSignedIn, sessionId, userId } = useAuth()
  const identity = isLoaded ? authIdentity(isSignedIn, userId, sessionId) : null
  const queryClient = useMemo(
    () => (identity === null ? null : createQueryClient()),
    [createQueryClient, identity],
  )

  if (queryClient === null) {
    return null
  }
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}
