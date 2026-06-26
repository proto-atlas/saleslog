import type { Meta, StoryObj } from '@storybook/react-vite'

import { TextField } from './TextField'

const meta = {
  component: TextField,
} satisfies Meta<typeof TextField>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: { label: '顧客名', placeholder: '例: 株式会社アオバ製作所' },
}

export const WithError: Story = {
  args: {
    label: '顧客名',
    defaultValue: '',
    error: '顧客名を入力してください',
  },
}
