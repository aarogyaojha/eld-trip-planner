import React, { useEffect, useState } from 'react'
import { listTrips, getTrip } from '../api.js'

export default function TripHistory({ onSelect, refreshKey }) {
  const [trips, setTrips] = useState([])
  const [loadingId, setLoadingId] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    listTrips()
      .then((data) => {
        if (active) setTrips(data)
      })
      .catch(() => {
        if (active) setError('Could not load trip history.')
      })
    return () => {
      active = false
    }
  }, [refreshKey])

  async function handleSelect(id) {
    setLoadingId(id)
    try {
      const detail = await getTrip(id)
      onSelect(detail)
    } catch {
      setError('Could not load that trip.')
    } finally {
      setLoadingId(null)
    }
  }

  return (
    <div className="panel">
      <h3>Trip history</h3>
      {error && <p className="field-error">{error}</p>}
      {trips.length === 0 && !error && <p className="history-empty">Planned trips will appear here.</p>}
      <ul className="history-list">
        {trips.map((trip) => (
          <li key={trip.id}>
            <button
              type="button"
              className="history-item"
              onClick={() => handleSelect(trip.id)}
              disabled={loadingId === trip.id}
            >
              <span className="history-route">
                {trip.pickup_location} &rarr; {trip.dropoff_location}
              </span>
              <span className="history-meta">
                {trip.total_miles} mi · {trip.total_days}d ·{' '}
                {new Date(trip.created_at).toLocaleDateString()}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
