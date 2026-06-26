import type { Meta, StoryObj } from '@storybook/react-vite'

import { Button } from './Button'
import { Dialog } from './Dialog'

const meta = {
  component: Dialog,
  args: { open: true, onClose: () => {} },
} satisfies Meta<typeof Dialog>

export default meta
type Story = StoryObj<typeof meta>

export const Confirm: Story = {
  args: {
    title: '未保存の変更があります',
    children: (
      <div className="flex flex-col gap-4">
        <p className="text-sm text-gray-600">
          このページを離れると入力した内容は失われます。移動しますか？
        </p>
        <div className="flex justify-end gap-2">
          <Button variant="secondary">とどまる</Button>
          <Button>移動する</Button>
        </div>
      </div>
    ),
  },
}

export const DestructiveConfirm: Story = {
  args: {
    title: '顧客を削除しますか？',
    children: (
      <div className="flex flex-col gap-4">
        <p className="text-sm text-gray-600">
          関連する活動記録もすべて削除されます。この操作は取り消せません。
        </p>
        <div className="flex justify-end gap-2">
          <Button variant="secondary">キャンセル</Button>
          <Button variant="danger">削除する</Button>
        </div>
      </div>
    ),
  },
}
