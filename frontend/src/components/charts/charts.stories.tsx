import type { Meta, StoryObj } from '@storybook/react-vite'

import { BarList } from './BarList'
import { TrendChart } from './TrendChart'

function ChartsShowcase() {
  return (
    <div className="flex flex-col gap-8">
      <BarList
        title="エリア別の顧客件数"
        items={[
          { label: '東京', count: 18 },
          { label: '神奈川', count: 12 },
          { label: '埼玉', count: 7 },
          { label: '千葉', count: 9 },
          { label: 'その他', count: 3 },
        ]}
      />
      <TrendChart
        title="月次の活動件数の推移"
        points={[
          { month: '2026-01', count: 32 },
          { month: '2026-02', count: 41 },
          { month: '2026-03', count: 28 },
          { month: '2026-04', count: 51 },
          { month: '2026-05', count: 46 },
          { month: '2026-06', count: 12 },
        ]}
      />
    </div>
  )
}

const meta = {
  component: ChartsShowcase,
} satisfies Meta<typeof ChartsShowcase>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {}
