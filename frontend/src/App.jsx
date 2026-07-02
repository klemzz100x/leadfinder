import { useState, useCallback, useEffect } from 'react'
import {
  scanArea, fetchLeads, fetchMeta, fetchDepartements, exportCsvUrl,
  fetchCategories, fetchLists,
} from './api.js'
import { mergeScanSummaries } from './utils.js'
import SearchBar from './components/SearchBar.jsx'
import StatsBar from './components/StatsBar.jsx'
import FilterBar from './components/FilterBar.jsx'
import LeadList from './components/LeadList.jsx'
import CategoryView from './components/CategoryView.jsx'
import CategoryEditor from './components/CategoryEditor.jsx'
import ListsView from './components/ListsView.jsx'
import Dashboard from './components/Dashboard.jsx'
import DepartementStatsView from './components/DepartementStatsView.jsx'
import DeptScanEstimate from './components/DeptScanEstimate.jsx'
import BatchScanPanel from './components/BatchScanPanel.jsx'
import IdentityPicker from './components/IdentityPicker.jsx'
import { getCurrentUser } from './identity.js'

export default function App() {
  const [city, setCity]         = useState('')
  const [scanning, setScanning] = useState(false)
  const [summary, setSummary]   = useState(null)
  const [leads, setLeads]       = useState([])
  const [types, setTypes]       = useState([])
  const [filter, setFilter]     = useState({ temperature: '', type: '', showEquipped: false, showClosed: false, departements: [] })
  const [departements, setDepartements] = useState([])
  const [resultsLoaded, setResultsLoaded] = useState(false)
  const [error, setError]       = useState('')
  const [batchCodes, setBatchCodes] = useState(null)

  const [viewMode, setViewMode]                 = useState('list')
  const [categories, setCategories]             = useState({})
  const [categoriesLoaded, setCategoriesLoaded] = useState(false)
  const [categoryEditorOpen, setCategoryEditorOpen] = useState(false)

  // Onglet principal
  const [tab, setTab] = useState('search')

  // Listes partagées
  const [lists, setLists] = useState([])

  useEffect(() => {
    fetchLists().then(setLists)
    fetchDepartements().then(setDepartements)
    fetchMeta().then((meta) => setTypes(meta.types || []))
  }, [])

  const loadLeads = useCallback(async (c, f = filter) => {
    const data = await fetchLeads({ city: c, ...f })
    setLeads(data)
    setResultsLoaded(true)
    const meta = await fetchMeta(c)
    setTypes(meta.types || [])
  }, [filter])

  // La ville prime si elle est renseignée (comportement historique inchangé) ;
  // sans ville, on scanne le(s) département(s) sélectionné(s) en entier.
  const canScan = city.trim().length > 0 || filter.departements.length > 0

  const handleScan = async () => {
    const trimmed = city.trim()
    if (!canScan) return

    if (!trimmed) {
      // Département(s) seuls : base partagée entre plusieurs utilisateurs —
      // si un département a déjà été scanné récemment (par soi ou par
      // quelqu'un d'autre), on le signale avant de relancer un scan
      // redondant (coût Overpass/Google Places).
      const RESCAN_FRESHNESS_DAYS = 30
      const now = Date.now()
      const alreadyCovered = filter.departements
        .map((code) => departements.find((d) => d.code === code))
        .filter((d) => d?.last_scanned_at && (now - new Date(d.last_scanned_at).getTime()) < RESCAN_FRESHNESS_DAYS * 86400000)
      if (alreadyCovered.length > 0) {
        const list = alreadyCovered
          .map((d) => `${d.name} (${d.last_scanned_at.slice(0, 10).split('-').reverse().join('/')}${d.last_scanned_by ? ' par ' + d.last_scanned_by : ''})`)
          .join(', ')
        if (!window.confirm(`Déjà scanné récemment : ${list}.\n\nRelancer quand même ?`)) return
      }
      // Scan par lot piloté (un département à la fois, résilient, avec
      // suivi) plutôt qu'une seule requête bloquante — évite les timeouts.
      setError('')
      setBatchCodes(filter.departements)
      return
    }

    setError('')
    setScanning(true)
    setSummary(null)
    setLeads([])
    try {
      const summaries = await scanArea({ city: trimmed, scannedBy: getCurrentUser() || undefined })
      const merged = mergeScanSummaries(summaries)
      if (!merged) {
        setError('Le scan n\'a ramené aucun résultat exploitable.')
      } else {
        setSummary(merged)
      }
      await loadLeads(trimmed, filter)
    } catch (e) {
      setError(e.message)
    } finally {
      setScanning(false)
    }
  }

  const handleBatchComplete = async () => {
    await loadLeads('', filter)
  }

  // Le filtre (notamment le sélecteur de département) est utilisable dès
  // l'arrivée sur la page, sans attendre un scan : il interroge directement
  // les leads déjà en base. Combiné à une ville tapée (scannée ou non), les
  // deux critères s'appliquent ensemble via /api/leads.
  const handleFilterChange = async (newFilter) => {
    setFilter(newFilter)
    setBatchCodes(null)
    await loadLeads(city.trim(), newFilter)
  }

  const handleLeadUpdate = (updated) => {
    setLeads((prev) => prev.map((l) => l.id === updated.id ? { ...l, ...updated } : l))
  }

  const handleViewMode = async (mode) => {
    setViewMode(mode)
    if (mode === 'categories' && !categoriesLoaded) {
      const cats = await fetchCategories()
      setCategories(cats)
      setCategoriesLoaded(true)
    }
  }

  const handleOpenEditor = async () => {
    if (!categoriesLoaded) {
      const cats = await fetchCategories()
      setCategories(cats)
      setCategoriesLoaded(true)
    }
    setCategoryEditorOpen(true)
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-top">
          <div className="header-brand">
            <div className="header-logo">🎯</div>
            <h1>
              <span className="header-title">LeadFinder</span>
              <span className="header-sub">Business sans site web</span>
            </h1>
          </div>
          <nav className="main-tabs">
            <button
              className={`main-tab${tab === 'search' ? ' active' : ''}`}
              onClick={() => setTab('search')}
            >
              🔍 Recherche
            </button>
            <button
              className={`main-tab${tab === 'lists' ? ' active' : ''}`}
              onClick={() => setTab('lists')}
            >
              📋 Mes Listes
              {lists.length > 0 && <span className="tab-badge">{lists.length}</span>}
            </button>
            <button
              className={`main-tab${tab === 'dashboard' ? ' active' : ''}`}
              onClick={() => setTab('dashboard')}
            >
              📊 Dashboard
            </button>
            <button
              className={`main-tab${tab === 'carte' ? ' active' : ''}`}
              onClick={() => setTab('carte')}
            >
              🗺️ Carte
            </button>
          </nav>
          <IdentityPicker />
        </div>

        {tab === 'search' && (
          <>
            <SearchBar
              city={city}
              onChange={setCity}
              onScan={handleScan}
              scanning={scanning}
              canScan={canScan}
            />
            {!city.trim() && !batchCodes && <DeptScanEstimate codes={filter.departements} />}
            {batchCodes && (
              <div className="batch-scan-wrap">
                <button
                  className="modal-close batch-scan-close"
                  onClick={() => setBatchCodes(null)}
                  title="Fermer"
                >
                  ✕
                </button>
                <BatchScanPanel
                  codes={batchCodes}
                  departements={departements}
                  onComplete={handleBatchComplete}
                />
              </div>
            )}
          </>
        )}
        {error && <p className="error">{error}</p>}
      </header>

      {tab === 'search' && (
        <>
          {summary && <StatsBar summary={summary} />}

          <div className="toolbar">
            <FilterBar filter={filter} types={types} departements={departements} onChange={handleFilterChange} />
            <div className="toolbar-divider" />
            <div className="view-toggle">
              <button
                className={`btn btn-view-toggle${viewMode === 'list' ? ' active' : ''}`}
                onClick={() => handleViewMode('list')}
              >
                ≡ Liste
              </button>
              <button
                className={`btn btn-view-toggle${viewMode === 'categories' ? ' active' : ''}`}
                onClick={() => handleViewMode('categories')}
              >
                ⊞ Catégories
              </button>
            </div>
            <button className="btn btn-cat-editor" onClick={handleOpenEditor}>
              ⚙ Catégories
            </button>
            <div className="toolbar-divider" />
            <a className="btn btn-export" href={exportCsvUrl(city.trim())} download>
              ↓ CSV
            </a>
          </div>

          <main>
            {!resultsLoaded && !scanning && (
              <p className="empty">
                Sélectionnez un ou plusieurs départements, ou lancez une recherche par ville.
              </p>
            )}
            {resultsLoaded && leads.length === 0 && !scanning && (
              <div className="dept-stats-empty">
                {!city.trim() && filter.departements.length > 0 ? (
                  <>
                    <p>
                      Aucun lead pour {filter.departements
                        .map((code) => departements.find((d) => d.code === code)?.name || code)
                        .join(', ')} — ce département n'a peut-être jamais été scanné.
                    </p>
                    <DeptScanEstimate codes={filter.departements} />
                    <button className="btn btn-scan" onClick={handleScan}>
                      🔍 Scanner {filter.departements.length > 1 ? 'ces départements' : 'ce département'}
                    </button>
                  </>
                ) : (
                  <p>Aucun lead pour ces filtres.</p>
                )}
              </div>
            )}
            {viewMode === 'list' && (
              <LeadList
                leads={leads}
                onUpdate={handleLeadUpdate}
                lists={lists}
                onListsChange={setLists}
              />
            )}
            {viewMode === 'categories' && leads.length > 0 && (
              <CategoryView
                leads={leads}
                categories={categories}
                onUpdate={handleLeadUpdate}
              />
            )}
          </main>

          <footer className="app-footer">
            {summary
              ? `Appels API : ${summary.api_calls} | Scan en ${summary.duration_seconds}s | 0 € garanti`
              : 'Aucun scan — 0 appel API | 0 € garanti'}
          </footer>
        </>
      )}

      {tab === 'lists' && (
        <ListsView lists={lists} onListsChange={setLists} />
      )}

      {tab === 'dashboard' && (
        <Dashboard onEditCategories={handleOpenEditor} />
      )}

      {tab === 'carte' && (
        <DepartementStatsView lists={lists} onListsChange={setLists} />
      )}

      {categoryEditorOpen && (
        <CategoryEditor
          categories={categories}
          types={types}
          onClose={() => setCategoryEditorOpen(false)}
          onSave={setCategories}
        />
      )}
    </div>
  )
}
