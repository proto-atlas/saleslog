import type { Meta, StoryObj } from '@storybook/react-vite'
import { createBrowserRouter } from 'react-router'
import { RouterProvider } from 'react-router/dom'

import type { VisitListItem } from '../api/client'
import { ActivityTimeline } from './ActivityTimeline'

const items: VisitListItem[] = [
  {
    id: 1,
    customer_id: 1,
    customer_name: '株式会社アオバ製作所',
    owner_id: 2,
    user_id: 2,
    user_name: '営業ユーザーA',
    activity_type: 'visit',
    status: 'planned',
    visited_at: '2026-06-10T01:00:00Z',
    created_at: '2026-06-01T00:00:00Z',
    updated_at: '2026-06-01T00:00:00Z',
  },
  {
    id: 2,
    customer_id: 1,
    customer_name: '株式会社アオバ製作所',
    owner_id: 2,
    user_id: 2,
    user_name: '営業ユーザーA',
    activity_type: 'call',
    status: 'done',
    visited_at: '2026-05-28T05:00:00Z',
    created_at: '2026-05-28T00:00:00Z',
    updated_at: '2026-05-28T00:00:00Z',
  },
]

function TimelineInRouter() {
  // Link を含むため Router コンテキストで包む
  const router = createBrowserRouter([
    {
      path: '*',
      element: (
        <ActivityTimeline items={items} editHref={(item) => `/visits/${item.id}/edit`} />
      ),
    },
  ])
  return <RouterProvider router={router} />
}

const meta = {
  component: TimelineInRouter,
} satisfies Meta<typeof TimelineInRouter>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {}
