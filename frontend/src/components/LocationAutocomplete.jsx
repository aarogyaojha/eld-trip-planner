import React, { useEffect, useRef, useState } from 'react'
import { suggestLocations } from '../api.js'

const DEBOUNCE_MS = 400

export default function LocationAutocomplete({ label, placeholder, value, onChange, onSelect, error }) {
  const [query, setQuery] = useState(value || '')
  const [suggestions, setSuggestions] = useState([])
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const [loading, setLoading] = useState(false)
  const [searchError, setSearchError] = useState(null)

  const debounceRef = useRef(null)
  const abortRef = useRef(null)
  const containerRef = useRef(null)

  // Keep the visible text in sync if the parent resets the form.
  useEffect(() => {
    setQuery(value || '')
  }, [value])

  // Close the dropdown when clicking outside.
  useEffect(() => {
    function handleClickOutside(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  function handleInputChange(e) {
    const text = e.target.value
    setQuery(text)
    onChange(text) // keep parent form state in sync as the user types too
    setActiveIndex(-1)

    if (debounceRef.current) clearTimeout(debounceRef.current)
    if (abortRef.current) abortRef.current.abort()

    if (text.trim().length < 3) {
      setSuggestions([])
      setOpen(false)
      return
    }

    debounceRef.current = setTimeout(async () => {
      const controller = new AbortController()
      abortRef.current = controller
      setLoading(true)
      setSearchError(null)
      try {
        const results = await suggestLocations(text, controller.signal)
        setSuggestions(results)
        setOpen(true)
      } catch (err) {
        if (err.name !== 'CanceledError' && err.code !== 'ERR_CANCELED') {
          setSuggestions([])
          setOpen(true)
          setSearchError('Could not load suggestions right now.')
        }
      } finally {
        setLoading(false)
      }
    }, DEBOUNCE_MS)
  }

  function selectSuggestion(suggestion) {
    setQuery(suggestion.label)
    onChange(suggestion.label)
    if (onSelect) onSelect(suggestion)
    setSuggestions([])
    setOpen(false)
    setActiveIndex(-1)
  }

  function handleKeyDown(e) {
    if (!open || suggestions.length === 0) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIndex((i) => Math.min(i + 1, suggestions.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIndex((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Enter') {
      if (activeIndex >= 0) {
        e.preventDefault()
        selectSuggestion(suggestions[activeIndex])
      }
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  return (
    <div className="autocomplete" ref={containerRef}>
      <label>
        {label}
        <div className="autocomplete-input-wrap">
          <input
            type="text"
            placeholder={placeholder}
            value={query}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            onFocus={() => suggestions.length > 0 && setOpen(true)}
            autoComplete="off"
          />
          {loading && <span className="autocomplete-spinner" aria-hidden="true" />}
        </div>
        {error && <span className="field-error">{error}</span>}
      </label>

      {open && (
        <ul className="autocomplete-dropdown">
          {searchError && <li className="autocomplete-status">{searchError}</li>}
          {!searchError && suggestions.length === 0 && !loading && (
            <li className="autocomplete-status">No matches found</li>
          )}
          {suggestions.map((s, i) => (
            <li
              key={`${s.label}-${i}`}
              className={i === activeIndex ? 'active' : ''}
              onMouseDown={() => selectSuggestion(s)}
              onMouseEnter={() => setActiveIndex(i)}
            >
              {s.label}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
