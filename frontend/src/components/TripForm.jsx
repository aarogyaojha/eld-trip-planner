import React, { useState } from 'react'
import LocationAutocomplete from './LocationAutocomplete.jsx'

const initialState = {
  currentLocation: '',
  currentLocationCoords: null,
  pickupLocation: '',
  pickupLocationCoords: null,
  dropoffLocation: '',
  dropoffLocationCoords: null,
  currentCycleUsedHours: '',
}

export default function TripForm({ onSubmit, loading }) {
  const [form, setForm] = useState(initialState)
  const [errors, setErrors] = useState({})

  function update(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  function validate() {
    const next = {}
    if (!form.currentLocation.trim()) next.currentLocation = 'Required'
    if (!form.pickupLocation.trim()) next.pickupLocation = 'Required'
    if (!form.dropoffLocation.trim()) next.dropoffLocation = 'Required'
    const cycle = Number(form.currentCycleUsedHours)
    if (form.currentCycleUsedHours === '' || Number.isNaN(cycle) || cycle < 0 || cycle > 70) {
      next.currentCycleUsedHours = 'Enter a number between 0 and 70'
    }
    setErrors(next)
    return Object.keys(next).length === 0
  }

  function handleSubmit(e) {
    e.preventDefault()
    if (!validate()) return
    onSubmit({
      currentLocation: form.currentLocation.trim(),
      currentLocationCoords: form.currentLocationCoords,
      pickupLocation: form.pickupLocation.trim(),
      pickupLocationCoords: form.pickupLocationCoords,
      dropoffLocation: form.dropoffLocation.trim(),
      dropoffLocationCoords: form.dropoffLocationCoords,
      currentCycleUsedHours: Number(form.currentCycleUsedHours),
    })
  }

  return (
    <form className="trip-form" onSubmit={handleSubmit}>
      <h2>Plan a trip</h2>

      <LocationAutocomplete
        label="Current location"
        placeholder="Start typing a city…"
        value={form.currentLocation}
        onChange={(v) => update('currentLocation', v)}
        onSelect={(s) => update('currentLocationCoords', s)}
        error={errors.currentLocation}
      />

      <LocationAutocomplete
        label="Pickup location"
        placeholder="Start typing a city…"
        value={form.pickupLocation}
        onChange={(v) => update('pickupLocation', v)}
        onSelect={(s) => update('pickupLocationCoords', s)}
        error={errors.pickupLocation}
      />

      <LocationAutocomplete
        label="Drop-off location"
        placeholder="Start typing a city…"
        value={form.dropoffLocation}
        onChange={(v) => update('dropoffLocation', v)}
        onSelect={(s) => update('dropoffLocationCoords', s)}
        error={errors.dropoffLocation}
      />

      <label>
        Current cycle used (hrs)
        <input
          type="number"
          min="0"
          max="70"
          step="0.25"
          placeholder="e.g. 12"
          value={form.currentCycleUsedHours}
          onChange={(e) => update('currentCycleUsedHours', e.target.value)}
        />
        {errors.currentCycleUsedHours && <span className="field-error">{errors.currentCycleUsedHours}</span>}
      </label>

      <button type="submit" disabled={loading}>
        {loading ? 'Planning trip…' : 'Plan trip'}
      </button>

      <p className="form-note">
        Assumes a property-carrying driver on the 70-hour/8-day rule, no adverse driving
        conditions, a fuel stop every 1,000 miles, and 1 hour each for pickup and drop-off.
      </p>
    </form>
  )
}
