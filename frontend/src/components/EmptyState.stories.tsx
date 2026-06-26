import type { Meta, StoryObj } from '@storybook/react-vite'

import { Button } from './Button'
import { EmptyState } from './EmptyState'

const meta = {
  component: EmptyState,
} satisfies Meta<typeof EmptyState>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
    title: '該当する顧客がいません',
    description: '検索条件を変更するか、新しい顧客を登録してください。',
  },
}

export const WithAction: Story = {
  args: {
    title: 'まだ顧客が登録されていません',
    action: <Button>顧客を登録する</Button>,
  },
}
