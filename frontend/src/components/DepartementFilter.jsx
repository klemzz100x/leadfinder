import { useEffect, useRef, useState } from 'react'

export default function DepartementFilter({ departements, selected, onChange }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    const onClickOutside = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [])

  const toggle = (code) => {
    const next = selected.includes(code)
      ? selected.filter((c) => c !== code)
      : [...selected, code]
    onChange(next)
  }

  const label = selected.length === 0
    ? 'Tous les départements'
    : `${selected.length} département${selected.length > 1 ? 's' : ''}`

  return (
    <div className="dept-filter" ref={ref}>
      <button type="button" className="dept-filter-btn" onClick={() => setOpen((v) => !v)}>
        {label} {open ? '▲' : '▼'}
      </button>
      {open && (
        <div className="dept-filter-panel">
          {selected.length > 0 && (
            <button type="button" className="dept-filter-clear" onClick={() => onChange([])}>
              Effacer la sélection
            </button>
          )}
          {departements.length === 0 && (
            <p className="dept-filter-empty">Liste des départements indisponible pour le moment.</p>
          )}
          {departements.map((d) => (
            <label key={d.code} className="dept-filter-item">
              <input
                type="checkbox"
                checked={selected.includes(d.code)}
                onChange={() => toggle(d.code)}
              />
              {d.code} — {d.name}
            </label>
          ))}
        </div>
      )}
    </div>
  )
}
