import React from 'react'

const ROWS = [
  { key: 'OFF_DUTY', label: 'Off Duty' },
  { key: 'SLEEPER_BERTH', label: 'Sleeper Berth' },
  { key: 'DRIVING', label: 'Driving' },
  { key: 'ON_DUTY_NOT_DRIVING', label: 'On Duty (Not Driving)' },
]

const LEFT_MARGIN = 150
const RIGHT_MARGIN = 20
const TOP_MARGIN = 28
const ROW_HEIGHT = 42
const GRID_WIDTH = 960
const HOUR_WIDTH = GRID_WIDTH / 24

function rowIndex(status) {
  return ROWS.findIndex((r) => r.key === status)
}

function rowY(idx) {
  return TOP_MARGIN + idx * ROW_HEIGHT + ROW_HEIGHT / 2
}

export default function ELDLogSheet({ day, meta }) {
  const segments = day.segments
  const width = LEFT_MARGIN + GRID_WIDTH + RIGHT_MARGIN
  const gridHeight = ROWS.length * ROW_HEIGHT
  const height = TOP_MARGIN + gridHeight + 30

  const hourLines = []
  for (let h = 0; h <= 24; h++) {
    const x = LEFT_MARGIN + h * HOUR_WIDTH
    hourLines.push(
      <line
        key={`h-${h}`}
        x1={x}
        y1={TOP_MARGIN}
        x2={x}
        y2={TOP_MARGIN + gridHeight}
        stroke={h % 6 === 0 ? '#2A2316' : '#9c8a5e'}
        strokeWidth={h % 6 === 0 ? 1.4 : 0.7}
      />
    )
    // quarter-hour tick marks
    if (h < 24) {
      for (let q = 1; q < 4; q++) {
        const qx = x + (q * HOUR_WIDTH) / 4
        hourLines.push(
          <line
            key={`h-${h}-q-${q}`}
            x1={qx}
            y1={TOP_MARGIN}
            x2={qx}
            y2={TOP_MARGIN + gridHeight}
            stroke="#ddd2af"
            strokeWidth={0.5}
          />
        )
      }
    }
  }

  const rowLines = ROWS.map((row, idx) => (
    <line
      key={`row-${row.key}`}
      x1={LEFT_MARGIN}
      y1={TOP_MARGIN + idx * ROW_HEIGHT}
      x2={LEFT_MARGIN + GRID_WIDTH}
      y2={TOP_MARGIN + idx * ROW_HEIGHT}
      stroke="#2A2316"
      strokeWidth={1}
    />
  ))
  rowLines.push(
    <line
      key="row-bottom"
      x1={LEFT_MARGIN}
      y1={TOP_MARGIN + gridHeight}
      x2={LEFT_MARGIN + GRID_WIDTH}
      y2={TOP_MARGIN + gridHeight}
      stroke="#2A2316"
      strokeWidth={1}
    />
  )

  const statusPath = []
  segments.forEach((seg, i) => {
    const y = rowY(rowIndex(seg.status))
    const x1 = LEFT_MARGIN + seg.start_hr * HOUR_WIDTH
    const x2 = LEFT_MARGIN + seg.end_hr * HOUR_WIDTH
    statusPath.push(
      <line key={`seg-${i}`} x1={x1} y1={y} x2={x2} y2={y} stroke="#C75A1F" strokeWidth={3} />
    )
    const prev = segments[i - 1]
    if (prev) {
      const prevY = rowY(rowIndex(prev.status))
      statusPath.push(
        <line
          key={`conn-${i}`}
          x1={x1}
          y1={prevY}
          x2={x1}
          y2={y}
          stroke="#C75A1F"
          strokeWidth={3}
        />
      )
    }
  })

  return (
    <div className="log-sheet">
      <div className="log-sheet-header">
        <div>
          <strong>Driver's Daily Log</strong> — {day.date}
        </div>
        <div className="log-sheet-meta">
          {meta?.carrierName || 'Carrier name'} · Vehicle: {meta?.vehicleId || '—'} · Total miles
          today: {day.miles_today}
        </div>
      </div>
      <div className="log-sheet-scroll">
        <svg viewBox={`0 0 ${width} ${height}`} className="log-sheet-svg">
        {Array.from({ length: 25 }, (_, h) => (
          <text
            key={`label-${h}`}
            x={LEFT_MARGIN + h * HOUR_WIDTH}
            y={TOP_MARGIN - 8}
            fontSize="9"
            textAnchor="middle"
            fill="#5b4f37"
          >
            {h === 0 ? 'Mid' : h === 12 ? 'Noon' : h % 12}
          </text>
        ))}

        {ROWS.map((row, idx) => (
          <text
            key={`rowlabel-${row.key}`}
            x={LEFT_MARGIN - 10}
            y={rowY(idx) + 3}
            fontSize="11"
            textAnchor="end"
            fill="#2A2316"
          >
            {row.label}
          </text>
        ))}

        {ROWS.map((row, idx) => (
          <text
            key={`total-${row.key}`}
            x={LEFT_MARGIN + GRID_WIDTH + 8}
            y={rowY(idx) + 3}
            fontSize="11"
            fill="#2A2316"
          >
            {day.totals[row.key]?.toFixed(2)}h
          </text>
        ))}

        {hourLines}
        {rowLines}
        {statusPath}
      </svg>
      </div>

      <div className="log-sheet-remarks">
        <strong>Remarks</strong>
        <ul>
          {day.remarks.map((r, i) => (
            <li key={i}>
              <span className="remark-time">{formatHour(r.time_hr)}</span> {r.text}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

function formatHour(hr) {
  const h = Math.floor(hr)
  const m = Math.round((hr - h) * 60)
  const period = h < 12 ? 'AM' : 'PM'
  const displayHour = h % 12 === 0 ? 12 : h % 12
  return `${displayHour}:${String(m).padStart(2, '0')} ${period}`
}
