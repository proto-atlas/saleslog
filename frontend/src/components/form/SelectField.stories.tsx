import type { Meta, StoryObj } from '@storybook/react-vite'

import { CUSTOMER_AREA, customerAreaLabels } from '../../api/enums'
import { SelectField } from './SelectField'

const meta = {
  component: SelectField,
  args: {
    label: 'エリア',
    children: CUSTOMER_AREA.map((area) => (
      <option key={area} value={area}>
        {customerAreaLabels[area]}
      </option>
    )),
  },
} satisfies Meta<typeof SelectField>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {}

export const WithError: Story = {
  args: { error: 'エリアを選択してください' },
}
