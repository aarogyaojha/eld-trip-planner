import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api'

export async function planTrip(params) {
  const response = await axios.post(`${API_BASE_URL}/plan-trip/`, {
    current_location: params.currentLocation,
    current_coords: params.currentLocationCoords || null,
    pickup_location: params.pickupLocation,
    pickup_coords: params.pickupLocationCoords || null,
    dropoff_location: params.dropoffLocation,
    dropoff_coords: params.dropoffLocationCoords || null,
    current_cycle_used_hours: params.currentCycleUsedHours,
  })
  return response.data
}

export async function suggestLocations(query, signal) {
  if (!query || query.trim().length < 3) return []
  try {
    const response = await axios.get(`${API_BASE_URL}/locations/suggest/`, {
      params: { q: query.trim() },
      signal,
      timeout: 8000,
    })
    return response.data
  } catch (err) {
    if (err.code !== 'ERR_CANCELED' && err.name !== 'CanceledError') {
      // Surface the real cause in the console instead of failing silently -
      // a CORS error, a 500, a timeout, and "backend not running" all look
      // identical to the user otherwise.
      console.error('[suggestLocations] request failed:', err.message, err.response?.data)
    }
    throw err
  }
}

export async function listTrips() {
  const response = await axios.get(`${API_BASE_URL}/trips/`)
  return response.data.results || response.data
}

export async function getTrip(id) {
  const response = await axios.get(`${API_BASE_URL}/trips/${id}/`)
  const detail = response.data
  return {
    trip_id: detail.id,
    route: detail.route_geometry,
    locations: detail.locations,
    stops: detail.stops,
    daily_logs: detail.daily_logs,
    trip_summary: {
      total_miles: detail.total_miles,
      total_days: detail.total_days,
      estimated_start: detail.estimated_start,
      estimated_end: detail.estimated_end,
    },
    assumptions: detail.assumptions,
  }
}
