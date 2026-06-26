import {
  QueryClient,
  useQueryClient,
  type QueryKey,
} from '@tanstack/react-query'
import { cleanup, render, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, test, vi } from 'vitest'
import type { ReactNode } from 'react'
import type { RenderResult } from '@testing-library/react'

import { AuthQueryCacheBoundary } from './AuthQueryCacheBoundary'

type MockAuthState = {
  isLoaded: boolean
  isSignedIn: boolean
  userId: string | null
  sessionId: string | null
}

const authMock = vi.hoisted(() => ({
  state: {
    isLoaded: true,
    isSignedIn: true,
    userId: 'manager-user',
    sessionId: 'manager-session',
  } as MockAuthState,
}))

vi.mock('@clerk/react', () => ({
  useAuth: () => authMock.state,
}))

function renderWithBoundary(
  children: ReactNode,
  createQueryClient: () => QueryClient,
) {
  return render(
    <AuthQueryCacheBoundary createQueryClient={createQueryClient}>
      {children}
    </AuthQueryCacheBoundary>,
  )
}

function queryClientFactory(clients: QueryClient[]) {
  let index = 0
  return vi.fn(() => {
    const client = clients[index]
    index += 1
    return client ?? new QueryClient()
  })
}

function CacheProbe({
  onRender,
  queryKey,
}: {
  onRender: (value: unknown) => void
  queryKey: QueryKey
}) {
  const queryClient = useQueryClient()
  onRender(queryClient.getQueryData(queryKey))
  return null
}

describe('AuthQueryCacheBoundary', () => {
  afterEach(() => {
    cleanup()
    authMock.state = {
      isLoaded: true,
      isSignedIn: true,
      userId: 'manager-user',
      sessionId: 'manager-session',
    }
  })

  test('認証主体が変わったら新しいQueryClientに切り替える', async () => {
    const firstClient = new QueryClient()
    const secondClient = new QueryClient()
    firstClient.setQueryData(['customers', 'list'], [{ id: 1 }])
    const createQueryClient = queryClientFactory([firstClient, secondClient])
    const renderedValues: unknown[] = []

    const view: RenderResult = renderWithBoundary(
      <CacheProbe
        queryKey={['customers', 'list']}
        onRender={(value) => renderedValues.push(value)}
      />,
      createQueryClient,
    )

    await waitFor(() => expect(renderedValues).toHaveLength(1))
    expect(renderedValues[0]).toEqual([{ id: 1 }])
    renderedValues.length = 0
    authMock.state = {
      isLoaded: true,
      isSignedIn: true,
      userId: 'sales-user',
      sessionId: 'sales-session',
    }
    view.rerender(
      <AuthQueryCacheBoundary createQueryClient={createQueryClient}>
        <CacheProbe
          queryKey={['customers', 'list']}
          onRender={(value) => renderedValues.push(value)}
        />
      </AuthQueryCacheBoundary>,
    )

    await waitFor(() => expect(renderedValues).toEqual([undefined]))
    expect(createQueryClient).toHaveBeenCalledTimes(2)
  })

  test('サインアウト時にも新しいQueryClientに切り替える', async () => {
    const firstClient = new QueryClient()
    const secondClient = new QueryClient()
    firstClient.setQueryData(['users', 'me'], { id: 1, role: 'manager' })
    const createQueryClient = queryClientFactory([firstClient, secondClient])
    const renderedValues: unknown[] = []
    const view = renderWithBoundary(
      <CacheProbe
        queryKey={['users', 'me']}
        onRender={(value) => renderedValues.push(value)}
      />,
      createQueryClient,
    )

    await waitFor(() =>
      expect(renderedValues).toEqual([{ id: 1, role: 'manager' }]),
    )
    renderedValues.length = 0
    authMock.state = {
      isLoaded: true,
      isSignedIn: false,
      userId: null,
      sessionId: null,
    }
    view.rerender(
      <AuthQueryCacheBoundary createQueryClient={createQueryClient}>
        <CacheProbe
          queryKey={['users', 'me']}
          onRender={(value) => renderedValues.push(value)}
        />
      </AuthQueryCacheBoundary>,
    )

    await waitFor(() => expect(renderedValues).toEqual([undefined]))
    expect(createQueryClient).toHaveBeenCalledTimes(2)
  })

  test('認証主体が読み込み中の間は子を描画しない', () => {
    authMock.state = {
      isLoaded: false,
      isSignedIn: false,
      userId: null,
      sessionId: null,
    }
    const createQueryClient = queryClientFactory([new QueryClient()])
    const renderedValues: unknown[] = []

    renderWithBoundary(
      <CacheProbe
        queryKey={['users', 'me']}
        onRender={(value) => renderedValues.push(value)}
      />,
      createQueryClient,
    )

    expect(renderedValues).toEqual([])
    expect(createQueryClient).not.toHaveBeenCalled()
  })
})
