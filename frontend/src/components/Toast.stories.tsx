import type { Meta, StoryObj } from '@storybook/react-vite'

import { ToastView } from './Toast'

const meta = {
  component: ToastView,
} satisfies Meta<typeof ToastView>

export default meta
type Story = StoryObj<typeof meta>

export const Success: Story = {
  args: { message: '顧客を登録しました', variant: 'success' },
}

export const ErrorCase: Story = {
  args: { message: '保存に失敗しました。もう一度お試しください', variant: 'error' },
}
