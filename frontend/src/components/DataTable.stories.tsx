import type { Meta, StoryObj } from '@storybook/react-vite'

import { DataTable, type DataTableColumn } from './DataTable'
import { EmptyState } from './EmptyState'

type SampleRow = { id: number; name: string; area: string }

const columns: DataTableColumn<SampleRow>[] = [
  { key: 'name', header: '名前', render: (row) => row.name, sortKey: 'name' },
  { key: 'area', header: 'エリア', render: (row) => row.area },
]

const rows: SampleRow[] = [
  { id: 1, name: '株式会社アオバ製作所', area: '東京' },
  { id: 2, name: 'ミナト物流', area: '神奈川' },
]

const meta = {
  component: DataTable,
  args: {
    columns: columns as DataTableColumn<unknown>[],
    rows: rows as unknown[],
    rowKey: (row) => (row as SampleRow).id,
  },
} satisfies Meta<typeof DataTable>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {}

export const Loading: Story = {
  args: { rows: [], isLoading: true },
}

export const Empty: Story = {
  args: {
    rows: [],
    emptyState: <EmptyState title="該当する顧客がいません" />,
  },
}

export const ErrorCase: Story = {
  args: {
    rows: [],
    errorMessage: 'データの取得に失敗しました',
    onRetry: () => {},
  },
}
