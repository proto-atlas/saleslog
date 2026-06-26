import type { Meta, StoryObj } from '@storybook/react-vite'

import { Button } from './Button'

const meta = {
  component: Button,
} satisfies Meta<typeof Button>

export default meta
type Story = StoryObj<typeof meta>

export const Primary: Story = {
  args: { children: '保存する', variant: 'primary' },
}

export const Secondary: Story = {
  args: { children: 'キャンセル', variant: 'secondary' },
}

export const Danger: Story = {
  args: { children: '削除する', variant: 'danger' },
}

export const Disabled: Story = {
  args: { children: '保存する', disabled: true },
}
