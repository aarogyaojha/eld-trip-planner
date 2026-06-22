import React, { useState, useEffect } from 'react'
import ELDLogSheet from './ELDLogSheet.jsx'

export default function DailyLogsView({ dailyLogs, tripSummary, assumptions }) {
  const [activeDay, setActiveDay] = useState(0)

  useEffect(() => {
    setActiveDay(0)
  }, [dailyLogs])

  if (!dailyLogs || dailyLogs.length === 0) return null

  const day = dailyLogs[Math.min(activeDay, dailyLogs.length - 1)]

  return (
    <div className="daily-logs">
      <div className="panel">
        <h3>Trip summary</h3>
        <div className="trip-summary-row">
          <div className="metric">
            <div className="metric-value">{tripSummary.total_miles} mi</div>
            <div className="metric-label">Total distance</div>
          </div>
          <div className="metric">
            <div className="metric-value">{tripSummary.total_days}</div>
            <div className="metric-label">Days on the road</div>
          </div>
        </div>
        <details className="assumptions-toggle">
          <summary>Trip parameters</summary>
          <ul>
            {assumptions.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
        </details>
      </div>

      <div className="panel">
        <h3>Driver's daily logs</h3>
        <div className="day-tabs">
          {dailyLogs.map((d, i) => (
            <button
              key={d.date}
              type="button"
              className={`day-tab ${i === activeDay ? 'active' : ''}`}
              onClick={() => setActiveDay(i)}
            >
              Day {i + 1} · {d.date}
            </button>
          ))}
        </div>
        <ELDLogSheet day={day} meta={{ carrierName: '', vehicleId: '' }} />
      </div>
    </div>
  )
}
