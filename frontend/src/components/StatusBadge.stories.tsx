import type { Meta, StoryObj } from '@storybook/react-vite'

import { CUSTOMER_STATUS } from '../api/enums'
import { CustomerStatusBadge } from './StatusBadge'

const meta = {
  component: CustomerStatusBadge,
} satisfies Meta<typeof CustomerStatusBadge>

export default meta
type Story = StoryObj<typeof meta>

export const AllStatuses: Story = {
  args: { status: 'prospect' },
  render: () => (
    <div className="flex gap-2">
      {CUSTOMER_STATUS.map((status) => (
        <CustomerStatusBadge key={status} status={status} />
      ))}
    </div>
  ),
}
