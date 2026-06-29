const TEMPS = [
  { value: '', label: 'Toutes températures' },
  { value: 'chaud', label: '🔥 Chauds' },
  { value: 'tiede', label: '🟠 Tièdes' },
  { value: 'froid', label: '⚪ Froids' },
  { value: 'a_verifier', label: '❓ À vérifier' },
]

export default function FilterBar({ filter, types, onChange }) {
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
    </div>
  )
}
