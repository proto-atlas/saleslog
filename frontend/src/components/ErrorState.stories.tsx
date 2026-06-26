import type { Meta, StoryObj } from '@storybook/react-vite'

import { ErrorState } from './ErrorState'

const meta = {
  component: ErrorState,
  args: { onRetry: () => {} },
} satisfies Meta<typeof ErrorState>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {}

export const CustomMessage: Story = {
  args: { message: '通信状態を確認して、もう一度お試しください' },
}
