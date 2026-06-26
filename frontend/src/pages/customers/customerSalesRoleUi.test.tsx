import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, test, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router'
import type { ReactNode } from 'react'

import type { CustomerOut } from '../../api/client'
import { ToastProvider } from '../../components/Toast'
import { VisitsListPage } from '../visits/VisitsListPage'
import { MapBoardPage } from '../map/MapBoardPage'
import { CustomerCreateDialog } from './CustomerCreateDialog'
import { CustomerDetailPage } from './CustomerDetailPage'
import { CustomersListPage } from './CustomersListPage'

const SALES_USER = {
  id: 2,
  name: '営業ユーザー',
  role: 'sales',
  linked: null,
}

const MANAGER_USER = {
  id: 1,
  name: '管理ユーザー',
  role: 'manager',
  linked: null,
}

const CUSTOMER: CustomerOut = {
  id: 1,
  name: '株式会社テスト',
  address: null,
  area: 'tokyo',
  status: 'prospect',
  owner_id: 2,
  created_at: '2026-06-19T00:00:00Z',
  updated_at: '2026-06-19T00:00:00Z',
}

const CUSTOMER_LIST_ITEM = {
  ...CUSTOMER,
  last_visited_at: null,
}

function renderWithProviders(element: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>{element}</ToastProvider>
    </QueryClientProvider>,
  )
}

function jsonResponse(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('sales role UI', () => {
  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  test('salesで顧客詳細を開いたら削除ボタンを表示しない', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input)
        if (path === '/api/me') {
          return jsonResponse(SALES_USER)
        }
        if (path === '/api/customers/1') {
          return jsonResponse(CUSTOMER)
        }
        if (path.startsWith('/api/customers/1/visits')) {
          return jsonResponse({ items: [], total: 0, page: 1, page_size: 10 })
        }
        return jsonResponse({ detail: 'Not Found' }, 404)
      }),
    )

    renderWithProviders(
      <MemoryRouter initialEntries={['/customers/1']}>
        <Routes>
          <Route path="/customers/:id" element={<CustomerDetailPage />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByRole('heading', { name: '株式会社テスト' })).toBeDefined()
    expect(screen.queryByRole('button', { name: '削除' })).toBeNull()
  })

  test('salesで顧客を登録したらowner_idを送信しない', async () => {
    const requests: { path: string; body: unknown }[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = String(input)
        if (path === '/api/me') {
          return jsonResponse(SALES_USER)
        }
        if (path === '/api/customers' && init?.method === 'POST') {
          requests.push({
            path,
            body:
              typeof init.body === 'string'
                ? (JSON.parse(init.body) as unknown)
                : null,
          })
          return jsonResponse(CUSTOMER)
        }
        return jsonResponse({ detail: 'Not Found' }, 404)
      }),
    )

    renderWithProviders(
      <CustomerCreateDialog open={true} onClose={() => undefined} onCreated={() => undefined} />,
    )

    fireEvent.change(await screen.findByLabelText('顧客名'), {
      target: { value: '株式会社テスト' },
    })
    const submitButton = await screen.findByRole('button', { name: '登録する' })
    await waitFor(() => expect((submitButton as HTMLButtonElement).disabled).toBe(false))
    fireEvent.click(submitButton)

    await waitFor(() => expect(requests).toHaveLength(1))
    expect(requests[0]).toEqual({
      path: '/api/customers',
      body: {
        name: '株式会社テスト',
        address: null,
        area: 'tokyo',
        status: 'prospect',
      },
    })
    expect(screen.queryByLabelText('担当者')).toBeNull()
  })

  test('managerでは担当者一覧の読み込み完了まで登録できない', async () => {
    let resolveUsers: ((response: Response) => void) | undefined
    const usersResponse = new Promise<Response>((resolve) => {
      resolveUsers = resolve
    })
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input)
        if (path === '/api/me') {
          return jsonResponse(MANAGER_USER)
        }
        if (path.startsWith('/api/users')) {
          return usersResponse
        }
        return jsonResponse({ detail: 'Not Found' }, 404)
      }),
    )

    renderWithProviders(
      <CustomerCreateDialog open={true} onClose={() => undefined} onCreated={() => undefined} />,
    )

    const submitButton = await screen.findByRole('button', { name: '登録する' })
    expect((submitButton as HTMLButtonElement).disabled).toBe(true)

    resolveUsers?.(
      jsonResponse({
        items: [MANAGER_USER, SALES_USER],
        total: 2,
        page: 1,
        page_size: 50,
      }),
    )

    await waitFor(() => expect((submitButton as HTMLButtonElement).disabled).toBe(false))
  })

  test('salesの顧客一覧では担当者フィルタを出さずowner_idを送信しない', async () => {
    const paths: string[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input)
        paths.push(path)
        if (path === '/api/me') {
          return jsonResponse(SALES_USER)
        }
        if (path.startsWith('/api/customers')) {
          return jsonResponse({
            items: [CUSTOMER_LIST_ITEM],
            total: 1,
            page: 1,
            page_size: 20,
          })
        }
        return jsonResponse({ detail: 'Not Found' }, 404)
      }),
    )

    renderWithProviders(
      <MemoryRouter initialEntries={['/customers?owner_id=1']}>
        <Routes>
          <Route path="/customers" element={<CustomersListPage />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByRole('heading', { name: '顧客一覧' })).toBeDefined()
    await waitFor(() =>
      expect(paths.some((path) => path.startsWith('/api/customers'))).toBe(true),
    )

    expect(screen.queryByLabelText('担当者')).toBeNull()
    expect(paths.some((path) => path.startsWith('/api/users'))).toBe(false)
    expect(
      paths
        .filter((path) => path.startsWith('/api/customers'))
        .some((path) => path.includes('owner_id=')),
    ).toBe(false)
  })

  test('salesの活動記録一覧では担当者フィルタを出さずuser_idを送信しない', async () => {
    const paths: string[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input)
        paths.push(path)
        if (path === '/api/me') {
          return jsonResponse(SALES_USER)
        }
        if (path.startsWith('/api/visits')) {
          return jsonResponse({
            items: [],
            total: 0,
            page: 1,
            page_size: 20,
          })
        }
        return jsonResponse({ detail: 'Not Found' }, 404)
      }),
    )

    renderWithProviders(
      <MemoryRouter initialEntries={['/visits?user_id=1']}>
        <Routes>
          <Route path="/visits" element={<VisitsListPage />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByRole('heading', { name: '活動記録一覧' })).toBeDefined()
    await waitFor(() =>
      expect(paths.some((path) => path.startsWith('/api/visits'))).toBe(true),
    )

    expect(screen.queryByLabelText('担当者')).toBeNull()
    expect(paths.some((path) => path.startsWith('/api/users'))).toBe(false)
    expect(
      paths
        .filter((path) => path.startsWith('/api/visits'))
        .some((path) => path.includes('user_id=')),
    ).toBe(false)
  })

  test('salesのエリア別ボードでは担当者一覧を取得しない', async () => {
    const paths: string[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const path = String(input)
        paths.push(path)
        if (path === '/api/me') {
          return jsonResponse(SALES_USER)
        }
        if (path.startsWith('/api/customers')) {
          return jsonResponse({
            items: [CUSTOMER_LIST_ITEM],
            total: 1,
            page: 1,
            page_size: 100,
          })
        }
        return jsonResponse({ detail: 'Not Found' }, 404)
      }),
    )

    renderWithProviders(
      <MemoryRouter initialEntries={['/map']}>
        <Routes>
          <Route path="/map" element={<MapBoardPage />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByRole('heading', { name: 'エリア別ボード' })).toBeDefined()
    await waitFor(() =>
      expect(paths.some((path) => path.startsWith('/api/customers'))).toBe(true),
    )
    expect(paths.some((path) => path.startsWith('/api/users'))).toBe(false)
  })
})
