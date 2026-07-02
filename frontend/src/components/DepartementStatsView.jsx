import { useEffect, useState } from 'react'
import { fetchCategories, fetchDepartements, fetchVilleStats, scanArea } from '../api.js'
import DepartementFilter from './DepartementFilter.jsx'
import DeptScanEstimate from './DeptScanEstimate.jsx'
import FranceMap from './FranceMap.jsx'

export default function DepartementStatsView({ lists, onListsChange }) {
  const [categories, setCategories] = useState({})
  const [activite, setActivite] = useState('')
  const [departements, setDepartements] = useState([])
  const [selectedDepts, setSelectedDepts] = useState([])
  const [stats, setStats] = useState([])
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [scanning, setScanning] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    fetchCategories().then(setCategories)
    // Liste officielle complète des départements — toujours sélectionnable,
    // indépendamment des zones déjà scannées (cf. `stats`, qui dépend elle
    // de l'historique réel des scans).
    fetchDepartements().then(setDepartements)
  }, [])

  useEffect(() => {
    setLoading(true)
    setError('')
    fetchVilleStats(activite, selectedDepts)
      .then((data) => { setStats(data); setSelected(null) })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [activite, selectedDepts, refreshKey])

  const handleScanSelected = async () => {
    if (selectedDepts.length === 0) return
    setScanning(true)
    setError('')
    try {
      await scanArea({ departements: selectedDepts })
      setRefreshKey((k) => k + 1)
    } catch (e) {
      setError(e.message)
    } finally {
      setScanning(false)
    }
  }

  const selectedDeptNames = selectedDepts
    .map((code) => departements.find((d) => d.code === code)?.name || code)
    .join(', ')

  return (
    <div className="dept-stats-view">
      <div className="dept-stats-toolbar">
        <select value={activite} onChange={(e) => setActivite(e.target.value)}>
          <option value="">Toutes activités</option>
          {Object.keys(categories).map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        <DepartementFilter
          departements={departements}
          selected={selectedDepts}
          onChange={setSelectedDepts}
        />
      </div>

      {error && <p className="error">{error}</p>}
      {loading && <p className="empty">Chargement…</p>}

      {!loading && !error && stats.length === 0 && (
        <div className="dept-stats-empty">
          {selectedDepts.length > 0 ? (
            <>
              <p>Aucune donnée pour {selectedDeptNames} pour l'instant.</p>
              <DeptScanEstimate codes={selectedDepts} />
              <button className="btn btn-scan" onClick={handleScanSelected} disabled={scanning}>
                {scanning
                  ? 'Scan en cours…'
                  : `🔍 Scanner ${selectedDepts.length > 1 ? 'ces départements' : 'ce département'}`}
              </button>
            </>
          ) : (
            <p>Aucun lead chaud pour ce filtre.</p>
          )}
        </div>
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
