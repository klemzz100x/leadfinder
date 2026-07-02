import { useEffect, useState } from 'react'
import { fetchCategories, fetchDeptStats } from '../api.js'
import DepartementMap from './DepartementMap.jsx'

export default function DepartementStatsView() {
  const [categories, setCategories] = useState({})
  const [activite, setActivite] = useState('')
  const [stats, setStats] = useState([])
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    fetchCategories().then(setCategories)
  }, [])

  useEffect(() => {
    setLoading(true)
    setError('')
    fetchDeptStats(activite)
      .then((data) => { setStats(data); setSelected(null) })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [activite])

  return (
    <div className="dept-stats-view">
      <div className="dept-stats-toolbar">
        <select value={activite} onChange={(e) => setActivite(e.target.value)}>
          <option value="">Toutes activités</option>
          {Object.keys(categories).map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </div>

      {error && <p className="error">{error}</p>}
      {loading && <p className="empty">Chargement…</p>}
      {!loading && !error && stats.length === 0 && (
        <p className="empty">Aucun lead chaud pour ce filtre.</p>
      )}

      {!loading && stats.length > 0 && (
        <div className="dept-stats-layout">
          <DepartementMap stats={stats} selected={selected} onSelect={setSelected} />

          <div className="dept-stats-list">
            {stats.map((d) => (
              <div
                key={d.code}
                className={`dept-stats-row${selected === d.code ? ' active' : ''}`}
                onClick={() => setSelected(d.code)}
              >
                <span className="dept-stats-name">{d.code} — {d.name}</span>
                <span className="dept-stats-count">🔥 {d.chauds}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
