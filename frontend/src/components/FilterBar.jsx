import DepartementFilter from './DepartementFilter.jsx'

const TEMPS = [
  { value: '', label: 'Toutes températures' },
  { value: 'chaud', label: '🔥 Chauds' },
  { value: 'tiede', label: '🟠 Tièdes' },
  { value: 'froid', label: '⚪ Froids' },
  { value: 'a_verifier', label: '❓ À vérifier' },
]

export default function FilterBar({ filter, types, departements = [], onChange, onSearch }) {
  const set = (key, value) => onChange({ ...filter, [key]: value })

  return (
    <div className="filter-bar">
      <select
        value={filter.temperature}
        onChange={(e) => set('temperature', e.target.value)}
      >
        {TEMPS.map((t) => (
          <option key={t.value} value={t.value}>{t.label}</option>
        ))}
      </select>

      <select
        value={filter.type}
        onChange={(e) => set('type', e.target.value)}
      >
        <option value="">Tous les types</option>
        {types.map((t) => (
          <option key={t} value={t}>{t}</option>
        ))}
      </select>

      <DepartementFilter
        departements={departements}
        selected={filter.departements || []}
        onChange={(deps) => set('departements', deps)}
      />

      <label className="filter-toggle">
        <input
          type="checkbox"
          checked={Boolean(filter.showEquipped)}
          onChange={(e) => set('showEquipped', e.target.checked)}
        />
        Afficher les déjà équipés
      </label>

      <label className="filter-toggle">
        <input
          type="checkbox"
          checked={Boolean(filter.showClosed)}
          onChange={(e) => set('showClosed', e.target.checked)}
        />
        Afficher les fermés
      </label>

      {onSearch && (
        <button
          type="button"
          className="btn btn-filter-search"
          onClick={onSearch}
          title="Cherche parmi les leads déjà en base avec ces filtres — sur toute la France si aucun département n'est coché"
        >
          🔍 Rechercher
        </button>
      )}
    </div>
  )
}
