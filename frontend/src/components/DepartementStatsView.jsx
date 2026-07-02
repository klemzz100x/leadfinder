import { useEffect, useState } from 'react'
import { fetchCategories, fetchDepartements, fetchVilleStats } from '../api.js'
import DepartementFilter from './DepartementFilter.jsx'
import DeptScanEstimate from './DeptScanEstimate.jsx'
import BatchScanPanel from './BatchScanPanel.jsx'
import FranceMap from './FranceMap.jsx'
import EstimatedRevenue from './EstimatedRevenue.jsx'

export default function DepartementStatsView({ lists, onListsChange, creneauxMap }) {
  const [categories, setCategories] = useState({})
  const [activite, setActivite] = useState('')
  const [departements, setDepartements] = useState([])
  const [selectedDepts, setSelectedDepts] = useState([])
  const [stats, setStats] = useState([])
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [batchCodes, setBatchCodes] = useState(null)
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

  const handleScanSelected = () => {
    if (selectedDepts.length === 0) return
    // Base partagée : signale si un département sélectionné a déjà été
    // scanné récemment (par soi ou par quelqu'un d'autre) avant de relancer.
    const RESCAN_FRESHNESS_DAYS = 30
    const now = Date.now()
    const alreadyCovered = selectedDepts
      .map((code) => departements.find((d) => d.code === code))
      .filter((d) => d?.last_scanned_at && (now - new Date(d.last_scanned_at).getTime()) < RESCAN_FRESHNESS_DAYS * 86400000)
    if (alreadyCovered.length > 0) {
      const list = alreadyCovered
        .map((d) => `${d.name} (${d.last_scanned_at.slice(0, 10).split('-').reverse().join('/')}${d.last_scanned_by ? ' par ' + d.last_scanned_by : ''})`)
        .join(', ')
      if (!window.confirm(`Déjà scanné récemment : ${list}.\n\nRelancer quand même ?`)) return
    }
    setError('')
    setBatchCodes(selectedDepts)
  }

  const handleBatchComplete = () => {
    setRefreshKey((k) => k + 1)
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
          onChange={(codes) => { setSelectedDepts(codes); setBatchCodes(null) }}
        />
        {stats.length > 0 && (
          <EstimatedRevenue count={stats.reduce((sum, v) => sum + (v.chauds || 0), 0)} />
        )}
      </div>

      {error && <p className="error">{error}</p>}
      {loading && <p className="empty">Chargement…</p>}

      {!loading && !error && stats.length === 0 && (
        <div className="dept-stats-empty">
          {selectedDepts.length > 0 ? (
            batchCodes ? (
              <BatchScanPanel
                codes={batchCodes}
                departements={departements}
                onComplete={handleBatchComplete}
              />
            ) : (
              <>
                <p>Aucune donnée pour {selectedDeptNames} pour l'instant.</p>
                <DeptScanEstimate codes={selectedDepts} />
                <button className="btn btn-scan" onClick={handleScanSelected}>
                  🔍 Scanner {selectedDepts.length > 1 ? 'ces départements' : 'ce département'}
                </button>
              </>
            )
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
            creneauxMap={creneauxMap}
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
                <EstimatedRevenue count={v.chauds} compact />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
