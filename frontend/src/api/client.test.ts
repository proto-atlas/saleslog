import { afterEach, describe, expect, test, vi } from 'vitest'

import { ApiError, api } from './client'

describe('api error handling', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  test('error.message_keyをApiError.messageに入れる', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(
          JSON.stringify({ error: { message_key: 'invalid_payload' } }),
          { status: 422 },
        ),
      ),
    )

    await expect(api.get('/api/agent-runs/1')).rejects.toMatchObject({
      name: 'ApiError',
      status: 422,
      message: 'invalid_payload',
    } satisfies Partial<ApiError>)
  })

  test('postWithStatusは202の本文とstatusを返す', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            error: {
              code: 'approval_processing',
              message_key: 'approval_processing',
              retry_with_new_idempotency_key: true,
              requires_reconciliation: false,
            },
          }),
          { status: 202 },
        ),
      ),
    )

    await expect(api.postWithStatus('/api/agent-runs/1/approvals/1/approve', {}))
      .resolves.toMatchObject({
        status: 202,
        body: {
          error: {
            code: 'approval_processing',
          },
        },
      })
  })
})
