import { calcScale } from '../../lib/chartScale'

export type BarListItem = {
  label: string
  count: number
}

type Props = {
  title: string
  items: BarListItem[]
}

const BAR_HEIGHT = 22
const ROW_GAP = 10
const LABEL_WIDTH = 110
const COUNT_WIDTH = 36
const CHART_WIDTH = 420

export function BarList({ title, items }: Props) {
  const scale = calcScale(Math.max(0, ...items.map((item) => item.count)))
  const height = items.length * (BAR_HEIGHT + ROW_GAP)
  const barAreaWidth = CHART_WIDTH - LABEL_WIDTH - COUNT_WIDTH

  if (items.length === 0) {
    return <p className="text-sm text-slate-600">データがありません</p>
  }

  return (
    <svg
      role="img"
      aria-label={title}
      viewBox={`0 0 ${CHART_WIDTH} ${height}`}
      className="w-full max-w-lg"
    >
      <title>{title}</title>
      {items.map((item, index) => {
        const y = index * (BAR_HEIGHT + ROW_GAP)
        const width = scale.max === 0 ? 0 : (item.count / scale.max) * barAreaWidth
        return (
          <g key={item.label}>
            <text
              x={LABEL_WIDTH - 10}
              y={y + BAR_HEIGHT / 2}
              textAnchor="end"
              dominantBaseline="central"
              className="fill-slate-500 text-[12px]"
            >
              {item.label}
            </text>
            {/* 背景バー */}
            <rect
              x={LABEL_WIDTH}
              y={y}
              width={barAreaWidth}
              height={BAR_HEIGHT}
              rx={4}
              className="fill-slate-100"
            />
            {/* 値バー */}
            {item.count > 0 && (
              <rect
                x={LABEL_WIDTH}
                y={y}
                width={width}
                height={BAR_HEIGHT}
                rx={4}
                fill="#3D6FFF"
              />
            )}
            <text
              x={LABEL_WIDTH + width + 8}
              y={y + BAR_HEIGHT / 2}
              dominantBaseline="central"
              className="fill-slate-600 text-[12px] font-semibold"
            >
              {item.count}
            </text>
          </g>
        )
      })}
    </svg>
  )
}
