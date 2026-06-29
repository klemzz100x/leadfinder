import { useState, useCallback } from 'react'
import { scanCity, fetchLeads, fetchMeta, exportCsvUrl, fetchCategories } from './api.js'
import SearchBar from './components/SearchBar.jsx'
import StatsBar from './components/StatsBar.jsx'
import FilterBar from './components/FilterBar.jsx'
import LeadList from './components/LeadList.jsx'
import CategoryView from './components/CategoryView.jsx'
import CategoryEditor from './components/CategoryEditor.jsx'

export default function App() {
  const [city, setCity]         = useState('')
  const [scanning, setScanning] = useState(false)
  const [summary, setSummary]   = useState(null)
  const [leads, setLeads]       = useState([])
  const [types, setTypes]       = useState([])
  const [filter, setFilter]     = useState({ temperature: '', type: '' })
  const [error, setError]       = useState('')

  // Vue : 'list' | 'categories'
  const [viewMode, setViewMode]             = useState('list')
  const [categories, setCategories]         = useState({})
  const [categoriesLoaded, setCategoriesLoaded] = useState(false)
  const [categoryEditorOpen, setCategoryEditorOpen] = useState(false)

  const loadLeads = useCallback(async (c, f = filter) => {
    const data = await fetchLeads({ city: c, ...f })
    setLeads(data)
    const meta = await fetchMeta(c)
    setTypes(meta.types || [])
  }, [filter])

  const handleScan = async () => {
    const trimmed = city.trim()
    if (!trimmed) return
    setError('')
    setScanning(true)
    setSummary(null)
    setLeads([])
    try {
      const s = await scanCity(trimmed)
      setSummary(s)
      await loadLeads(trimmed, filter)
    } catch (e) {
      setError(e.message)
    } finally {
      setScanning(false)
    }
  }

  const handleFilterChange = async (newFilter) => {
    setFilter(newFilter)
    if (summary) await loadLeads(city.trim(), newFilter)
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

  const handleCategoriesSaved = (newCats) => {
    setCategories(newCats)
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-brand">
          <div className="header-logo">🎯</div>
          <h1>
            <span className="header-title">LeadFinder</span>
            <span className="header-sub">Business sans site web</span>
          </h1>
        </div>
        <SearchBar
          city={city}
          onChange={setCity}
          onScan={handleScan}
          scanning={scanning}
        />
        {error && <p className="error">{error}</p>}
      </header>

      {summary && (
        <>
          <StatsBar summary={summary} />

          <div className="toolbar">
            <FilterBar
              filter={filter}
              types={types}
              onChange={handleFilterChange}
            />

            <div className="toolbar-divider" />

            {/* Toggle Vue liste / Vue catégories */}
            <div className="view-toggle">
              <button
                className={`btn btn-view-toggle${viewMode === 'list' ? ' active' : ''}`}
                onClick={() => handleViewMode('list')}
                title="Vue liste"
              >
                ≡ Liste
              </button>
              <button
                className={`btn btn-view-toggle${viewMode === 'categories' ? ' active' : ''}`}
                onClick={() => handleViewMode('categories')}
                title="Vue catégories"
              >
                ⊞ Catégories
              </button>
            </div>

            {/* Bouton éditeur de catégories */}
            <button className="btn btn-cat-editor" onClick={handleOpenEditor} title="Éditer les catégories">
              ⚙ Catégories
            </button>

            <div className="toolbar-divider" />

            <a className="btn btn-export" href={exportCsvUrl(city.trim())} download>
              ↓ CSV
            </a>
          </div>
        </>
      )}

      <main>
        {leads.length === 0 && summary && !scanning && (
          <p className="empty">Aucun lead pour ces filtres.</p>
        )}

        {viewMode === 'list' && (
          <LeadList leads={leads} onUpdate={handleLeadUpdate} />
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

      {categoryEditorOpen && (
        <CategoryEditor
          categories={categories}
          types={types}
          onClose={() => setCategoryEditorOpen(false)}
          onSave={handleCategoriesSaved}
        />
      )}
    </div>
  )
}
