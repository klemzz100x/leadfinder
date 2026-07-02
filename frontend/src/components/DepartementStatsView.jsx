import { useEffect, useState } from 'react'
import { fetchCategories, fetchVilleStats } from '../api.js'
import FranceMap from './FranceMap.jsx'

export default function DepartementStatsView({ lists, onListsChange }) {
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
    fetchVilleStats(activite)
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
          <FranceMap
            villeStats={stats}
            activite={activite}
            selectedVille={selected}
            onSelectVille={setSelected}
            lists={lists}
            onListsChange={onListsChange}
          />

          <div className="dept-stats-list">
            {stats.map((v) => (
              <div
                key={v.name}
                className={`dept-stats-row${selected === v.name ? ' active' : ''}`}
                onClick={() => setSelected(v.name)}
              >
                <span className="dept-stats-name">{v.name}</span>
                <span className="dept-stats-count">🔥 {v.chauds}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
