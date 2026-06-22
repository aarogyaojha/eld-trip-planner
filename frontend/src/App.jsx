import React, { useState } from 'react'
import TripForm from './components/TripForm.jsx'
import RouteMap from './components/RouteMap.jsx'
import DailyLogsView from './components/DailyLogsView.jsx'
import TripHistory from './components/TripHistory.jsx'
import { planTrip } from './api.js'
import useCountUp from './useCountUp.js'

export default function App() {
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [historyKey, setHistoryKey] = useState(0)

  const milesDisplay = useCountUp(result ? result.trip_summary.total_miles : null)
  const daysDisplay = useCountUp(result ? result.trip_summary.total_days : null)

  async function handleSubmit(formValues) {
    setLoading(true)
    setError(null)
    try {
      const data = await planTrip(formValues)
      setResult(data)
      setHistoryKey((k) => k + 1)
    } catch (err) {
      const message =
        err?.response?.data?.detail ||
        'Could not plan this trip. Check the locations and try again.'
      setError(message)
      setResult(null)
    } finally {
      setLoading(false)
    }
  }

  function handleHistorySelect(detail) {
    setResult(detail)
    setError(null)
  }

  return (
    <div className="app-shell">
      <header className="dispatch-header">
        <div className="wordmark">
          <span className="wordmark-mark">
            FREIGHT<span>LINE</span>
          </span>
          <span className="wordmark-tagline">route + HOS log planner</span>
        </div>

        {result && (
          <div className="dash-readout" aria-live="polite">
            <div className="stat">
              <span className="stat-value">{milesDisplay.toFixed(0)}</span>
              <span className="stat-label">Miles</span>
            </div>
            <div className="stat">
              <span className="stat-value">{daysDisplay.toFixed(0)}</span>
              <span className="stat-label">Days</span>
            </div>
            <div className="stat">
              <span className="stat-value">
                {new Date(result.trip_summary.estimated_end).toLocaleDateString(undefined, {
                  month: 'short',
                  day: 'numeric',
                })}
              </span>
              <span className="stat-label">ETA</span>
            </div>
          </div>
        )}
      </header>

      <div className="app-body">
        <aside className="app-sidebar">
          <div className="panel">
            <TripForm onSubmit={handleSubmit} loading={loading} />
            {error && <div className="error-banner">{error}</div>}
          </div>
          <TripHistory onSelect={handleHistorySelect} refreshKey={historyKey} />
        </aside>

        <main className="app-main">
          <RouteMap route={result?.route} stops={result?.stops} locations={result?.locations} />
          {result && (
            <DailyLogsView
              dailyLogs={result.daily_logs}
              tripSummary={result.trip_summary}
              assumptions={result.assumptions}
            />
          )}
        </main>
      </div>
    </div>
  )
}
