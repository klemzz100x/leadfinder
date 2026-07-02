import { useState, useRef, useEffect, useCallback } from 'react'
import { suggestCities } from '../api.js'

export default function SearchBar({ city, onChange, onScan, scanning, canScan = true }) {
  const [suggestions, setSuggestions] = useState([])
  const [open, setOpen] = useState(false)
  const [activeIdx, setActiveIdx] = useState(-1)
  const debounceRef = useRef(null)
  const wrapperRef = useRef(null)

  const fetchSuggestions = useCallback((q) => {
    clearTimeout(debounceRef.current)
    if (q.length < 2) {
      setSuggestions([])
      setOpen(false)
      return
    }
    debounceRef.current = setTimeout(async () => {
      const data = await suggestCities(q)
      setSuggestions(data)
      setOpen(data.length > 0)
      setActiveIdx(-1)
    }, 350)
  }, [])

  const handleChange = (e) => {
    const v = e.target.value
    onChange(v)
    fetchSuggestions(v)
  }

  const select = (s) => {
    onChange(s.name)
    setSuggestions([])
    setOpen(false)
    setActiveIdx(-1)
  }

  const handleKeyDown = (e) => {
    if (!open) {
      if (e.key === 'Enter') onScan()
      return
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIdx((i) => Math.min(i + 1, suggestions.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIdx((i) => Math.max(i - 1, -1))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (activeIdx >= 0 && suggestions[activeIdx]) {
        select(suggestions[activeIdx])
      } else {
        setOpen(false)
        onScan()
      }
    } else if (e.key === 'Escape') {
      setOpen(false)
      setActiveIdx(-1)
    }
  }

  // Fermer si clic en dehors
  useEffect(() => {
    const handler = (e) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <div className="search-bar" ref={wrapperRef}>
      <div className="search-input-wrap">
        <input
          type="text"
          className="search-input"
          placeholder="Nom d'une ville (ex : Bordeaux)"
          value={city}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          disabled={scanning}
          autoComplete="off"
          spellCheck={false}
        />
        {open && (
          <ul className="suggestions-list" role="listbox">
            {suggestions.map((s, i) => (
              <li
                key={s.place_id || i}
                className={`suggestion-item${i === activeIdx ? ' active' : ''}`}
                onMouseDown={() => select(s)}
                onMouseEnter={() => setActiveIdx(i)}
                role="option"
                aria-selected={i === activeIdx}
              >
                <span className="sug-name">{s.name}</span>
                {s.detail && <span className="sug-detail">{s.detail}</span>}
              </li>
            ))}
          </ul>
        )}
      </div>
      <button
        className="btn btn-scan"
        onClick={onScan}
        disabled={scanning || !canScan}
        title={canScan ? undefined : 'Tapez une ville ou sélectionnez au moins un département'}
      >
        {scanning ? 'Scan en cours…' : 'Scanner'}
      </button>
    </div>
  )
}
