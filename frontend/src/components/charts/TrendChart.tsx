import { calcScale } from '../../lib/chartScale'

export type TrendPoint = {
  month: string
  count: number
}

type Props = {
  title: string
  points: TrendPoint[]
}

const CHART_WIDTH = 420
const CHART_HEIGHT = 180
const AXIS_LEFT = 36
const AXIS_BOTTOM = 24
const BAR_GAP = 10

export function TrendChart({ title, points }: Props) {
  const scale = calcScale(Math.max(0, ...points.map((point) => point.count)))
  const plotWidth = CHART_WIDTH - AXIS_LEFT
  const plotHeight = CHART_HEIGHT - AXIS_BOTTOM
  const barWidth =
    points.length > 0 ? plotWidth / points.length - BAR_GAP : plotWidth

  return (
    <svg
      role="img"
      aria-label={title}
      viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
      className="w-full max-w-lg"
    >
      <title>{title}</title>
      {/* グリッドライン */}
      {scale.ticks.map((tick) => {
        const y = plotHeight - (scale.max === 0 ? 0 : (tick / scale.max) * plotHeight)
        return (
          <g key={tick}>
            <line
              x1={AXIS_LEFT}
              x2={CHART_WIDTH}
              y1={y}
              y2={y}
              stroke="#E2E8F0"
              strokeWidth={1}
            />
            <text
              x={AXIS_LEFT - 8}
              y={y}
              textAnchor="end"
              dominantBaseline="central"
              className="fill-slate-400 text-[10px]"
            >
              {tick}
            </text>
          </g>
        )
      })}
      {/* バー */}
      {points.map((point, index) => {
        const x = AXIS_LEFT + index * (barWidth + BAR_GAP) + BAR_GAP / 2
        const barHeight =
          scale.max === 0 ? 0 : (point.count / scale.max) * plotHeight
        return (
          <g key={point.month}>
            <rect
              x={x}
              y={plotHeight - barHeight}
              width={barWidth}
              height={barHeight}
              rx={3}
              fill="#3D6FFF"
              opacity={0.85}
            />
            <text
              x={x + barWidth / 2}
              y={CHART_HEIGHT - 8}
              textAnchor="middle"
              className="fill-slate-400 text-[10px]"
            >
              {point.month.slice(5)}月
            </text>
          </g>
        )
      })}
    </svg>
  )
}
