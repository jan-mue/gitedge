import { useRef, useState } from "react"
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import type { ActivitySeriesPoint } from "@/client"

export type ActivityMetric = "commits" | "additions" | "deletions"

interface ActivityChartProps {
  series: ActivitySeriesPoint[]
  metric?: ActivityMetric
  variant?: "area" | "bar" | "frequency"
  height?: number
  daily?: boolean
  interactive?: boolean
  label: string
}

const formatTick = (value: string, daily: boolean) =>
  new Date(`${value}T00:00:00Z`).toLocaleDateString("en-US", {
    ...(daily ? { weekday: "short" } : { month: "short", year: "2-digit" }),
    timeZone: "UTC",
  })

const ActivityChart = ({
  series,
  metric = "commits",
  variant = "bar",
  height = 208,
  daily = false,
  interactive = false,
  label,
}: ActivityChartProps) => {
  const [range, setRange] = useState<[number, number] | null>(null)
  const drag = useRef<{ start: number; range: [number, number]; pan: boolean } | null>(null)
  const visibleRange = range ?? [0, Math.max(0, series.length - 1)]
  const visible = series.slice(visibleRange[0], visibleRange[1] + 1).map((point) => ({
    ...point,
    deletions: variant === "frequency" ? -point.deletions : point.deletions,
  }))
  const Chart = variant === "area" ? AreaChart : BarChart
  const reset = () => setRange(null)

  return (
    <fieldset
      aria-label={label}
      tabIndex={interactive ? 0 : undefined}
      className="min-w-0 select-none rounded focus-visible:outline-2 focus-visible:outline-ring"
      style={{ height, touchAction: interactive ? "pan-y" : undefined }}
      onDoubleClick={interactive ? reset : undefined}
      onKeyDown={
        interactive
          ? (event) => {
              if (event.key === "Escape") reset()
              if (event.key === "+" || event.key === "=") {
                const width = visibleRange[1] - visibleRange[0]
                const inset = Math.max(1, Math.floor(width / 4))
                if (width > 2) setRange([visibleRange[0] + inset, visibleRange[1] - inset])
              }
              if (event.key === "-") reset()
            }
          : undefined
      }
      onPointerDown={
        interactive
          ? (event) => {
              if (event.button !== 0 || series.length < 2) return
              event.currentTarget.setPointerCapture(event.pointerId)
              drag.current = { start: event.clientX, range: [visibleRange[0], visibleRange[1]], pan: event.shiftKey }
            }
          : undefined
      }
      onPointerCancel={() => {
        drag.current = null
      }}
      onPointerUp={
        interactive
          ? (event) => {
              const selection = drag.current
              drag.current = null
              if (!selection || Math.abs(event.clientX - selection.start) < 5) return
              const bounds = event.currentTarget.getBoundingClientRect()
              const width = Math.max(1, bounds.width - 76)
              const [left, right] = selection.range
              if (selection.pan) {
                const delta = Math.round(((selection.start - event.clientX) / width) * (right - left))
                const start = Math.max(0, Math.min(series.length - (right - left + 1), left + delta))
                setRange([start, start + right - left])
              } else {
                const index = (x: number) =>
                  Math.max(left, Math.min(right, left + Math.round(((x - bounds.left - 60) / width) * (right - left))))
                const start = index(Math.min(selection.start, event.clientX))
                const end = index(Math.max(selection.start, event.clientX))
                if (end > start) setRange([start, end])
              }
            }
          : undefined
      }
    >
      <ResponsiveContainer width="100%" height="100%" minWidth={0}>
        <Chart data={visible} margin={{ top: 5, right: 16, bottom: 0, left: 0 }} accessibilityLayer>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis
            dataKey="date"
            tickFormatter={(value: string) => formatTick(value, daily)}
            tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
            minTickGap={20}
          />
          <YAxis width={60} allowDecimals={false} tick={{ fontSize: 10, fill: "var(--muted-foreground)" }} />
          <Tooltip
            contentStyle={{
              background: "var(--popover)",
              border: "1px solid var(--border)",
              color: "var(--foreground)",
            }}
            labelFormatter={(value) => `${daily ? "Date" : "Week of"} ${value}`}
            formatter={(value, name) => [Math.abs(Number(value)).toLocaleString(), name]}
            cursor={variant === "area" ? undefined : { fill: "var(--accent)", opacity: 0.4 }}
          />
          {variant === "area" ? (
            <Area type="monotone" dataKey={metric} stroke="var(--primary)" fill="var(--primary)" fillOpacity={0.3} />
          ) : variant === "frequency" ? (
            <>
              <ReferenceLine y={0} stroke="var(--border)" />
              <Bar dataKey="additions" fill="var(--success)" stackId="changes" />
              <Bar dataKey="deletions" fill="var(--destructive)" stackId="changes" />
            </>
          ) : (
            <Bar dataKey={metric} fill="var(--primary)" />
          )}
        </Chart>
      </ResponsiveContainer>
    </fieldset>
  )
}

export default ActivityChart
