import { useState, useCallback, useEffect } from 'react'
import {
  scanArea, fetchLeads, fetchMeta, fetchRawTypes, fetchDepartements, exportCsvUrl,
  fetchCategories, fetchLists, fetchRappels, fetchCreneaux, fetchCreneauxMap,
} from './api.js'
import { mergeScanSummaries } from './utils.js'
import SearchBar from './components/SearchBar.jsx'
import StatsBar from './components/StatsBar.jsx'
import FilterBar from './components/FilterBar.jsx'
import LeadList from './components/LeadList.jsx'
import CategoryView from './components/CategoryView.jsx'
import CategoryEditor from './components/CategoryEditor.jsx'
import CreneauxEditor from './components/CreneauxEditor.jsx'
import ListsView from './components/ListsView.jsx'
import RappelsView from './components/RappelsView.jsx'
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
  const [rawTypes, setRawTypes]                 = useState([])
  const [familles, setFamilles]                 = useState({})
  const [famillesLoaded, setFamillesLoaded]     = useState(false)
  const [creneauxEditorOpen, setCreneauxEditorOpen] = useState(false)

  // Onglet principal
  const [tab, setTab] = useState('search')

  // Listes partagées
  const [lists, setLists] = useState([])
  const [rappelsCount, setRappelsCount] = useState(0)
  const [creneauxMap, setCreneauxMap] = useState({})

  useEffect(() => {
    fetchLists().then(setLists)
    fetchDepartements().then(setDepartements)
    fetchMeta().then((meta) => setTypes(meta.types || []))
    fetchRappels().then((r) => setRappelsCount(r.length))
    fetchCreneauxMap().then(setCreneauxMap)
  }, [])

  // Badge de l'onglet à jour même si l'utilisateur ne l'a pas ouvert
  // (résolution par un autre utilisateur sur la base partagée, notamment).
  useEffect(() => {
    const id = setInterval(() => {
      fetchRappels().then((r) => setRappelsCount(r.length))
    }, 15000)
    return () => clearInterval(id)
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
    // Types bruts (non groupés) : /api/leads/meta ne renvoie plus que des
    // catégories déjà groupées, impropres à l'édition des catégories elles-mêmes.
    setRawTypes(await fetchRawTypes())
    setCategoryEditorOpen(true)
  }

  const handleOpenCreneauxEditor = async () => {
    if (!famillesLoaded) {
      setFamilles(await fetchCreneaux())
      setFamillesLoaded(true)
    }
    setRawTypes(await fetchRawTypes())
    setCreneauxEditorOpen(true)
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
              className={`main-tab${tab === 'rappels' ? ' active' : ''}`}
              onClick={() => setTab('rappels')}
            >
              📞 Rappels
              {rappelsCount > 0 && <span className="tab-badge tab-badge-rappels">{rappelsCount}</span>}
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
            <FilterBar
              filter={filter}
              types={types}
              departements={departements}
              onChange={handleFilterChange}
              onSearch={() => loadLeads(city.trim(), filter)}
            />
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
                Filtrez par température et/ou type d'activité puis cliquez sur <strong>🔍 Rechercher</strong> (ex : tous les
                salons de beauté "chauds" de France, sans rien cocher d'autre) — ou affinez par département, ou lancez un
                scan par ville.
              </p>
            )}
            {resultsLoaded && leads.length === 0 && !scanning && (() => {
              // Zéro résultat avec des départements déjà scannés ne veut pas dire
              // "jamais scanné" — juste qu'aucun lead ne correspond à CES filtres
              // (ex : chaud + beauté) dans ces départements. Ne proposer un scan
              // que pour les départements réellement sans données, sinon on pousse
              // vers des rescans redondants (le souci que la couverture partagée
              // est censée éviter).
              const selected = filter.departements
                .map((code) => departements.find((d) => d.code === code) || { code, name: code })
              const neverScanned = selected.filter((d) => !d.last_scanned_at)
              if (city.trim() || selected.length === 0) {
                return <div className="dept-stats-empty"><p>Aucun lead pour ces filtres.</p></div>
              }
              if (neverScanned.length === 0) {
                return (
                  <div className="dept-stats-empty">
                    <p>
                      Aucun lead ne correspond à ces filtres dans {selected.map((d) => d.name).join(', ')} — déjà
                      scanné{selected.length > 1 ? 's' : ''}, essayez d'élargir vos filtres (température, type).
                    </p>
                  </div>
                )
              }
              return (
                <div className="dept-stats-empty">
                  <p>
                    {neverScanned.map((d) => d.name).join(', ')} n'{neverScanned.length > 1 ? 'ont' : 'a'} pas encore
                    été scanné{neverScanned.length > 1 ? 's' : ''}.
                    {neverScanned.length < selected.length && ' Les autres départements sélectionnés sont déjà couverts.'}
                  </p>
                  <DeptScanEstimate codes={neverScanned.map((d) => d.code)} />
                  <button className="btn btn-scan" onClick={handleScan}>
                    🔍 Scanner {neverScanned.length > 1 ? 'ces départements' : 'ce département'}
                  </button>
                </div>
              )
            })()}
            {viewMode === 'list' && (
              <LeadList
                leads={leads}
                onUpdate={handleLeadUpdate}
                lists={lists}
                onListsChange={setLists}
                creneauxMap={creneauxMap}
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

      {tab === 'rappels' && <RappelsView />}

      {tab === 'dashboard' && (
        <Dashboard onEditCategories={handleOpenEditor} onEditCreneaux={handleOpenCreneauxEditor} />
      )}

      {tab === 'carte' && (
        <DepartementStatsView lists={lists} onListsChange={setLists} creneauxMap={creneauxMap} />
      )}

      {categoryEditorOpen && (
        <CategoryEditor
          categories={categories}
          types={rawTypes}
          onClose={() => setCategoryEditorOpen(false)}
          onSave={setCategories}
        />
      )}

      {creneauxEditorOpen && (
        <CreneauxEditor
          familles={familles}
          types={rawTypes}
          onClose={() => setCreneauxEditorOpen(false)}
          onSave={(fams) => {
            setFamilles(fams)
            fetchCreneauxMap().then(setCreneauxMap)
          }}
        />
      )}
    </div>
  )
}
